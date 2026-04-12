"""
Historial de recorridos del usuario (inicio / fin de sendero) — app móvil.
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from quart import Blueprint, jsonify, request

from db import get_conn
from routes.favorites import _TRAILS_SELECT, _serialize_trail_row
from routes.trails import require_auth

trail_history_bp = Blueprint('trail_history', __name__)
log = logging.getLogger(__name__)

_DEBUG_TRAIL_CLOCK = os.getenv('TRAIL_HISTORY_DEBUG', '').lower() in ('1', 'true', 'yes')


def _utc_iso(dt) -> str | None:
    """ISO-8601 UTC con sufijo Z (evita ambigüedad con datetime sin zona en JS)."""
    if dt is None:
        return None
    if getattr(dt, 'tzinfo', None) is None:
        log.warning('trail_history: naive datetime en TIMESTAMPTZ (se asume UTC): %s', dt)
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _server_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _ensure_aware_utc(dt):
    """Evita comparar datetimes naive vs aware (asyncpg / TIMESTAMPTZ según conexión)."""
    if dt is None:
        return None
    if getattr(dt, 'tzinfo', None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialize_entry(row) -> dict:
    d = dict(row)
    started = d.get('started_at')
    finished = d.get('finished_at')
    return {
        'id': str(d['id']),
        'trail_id': str(d['trail_id']),
        'started_at': _utc_iso(started),
        'completed_at': _utc_iso(finished),
        'status': 'completed' if d.get('completed') else 'in_progress',
    }


def _entry_response(row_with_db_now: dict):
    """
    Extrae db_now del RETURNING, serializa entry y devuelve payload extendido para el cliente.
    """
    d = dict(row_with_db_now)
    db_now = d.pop('db_now', None)
    entry = _serialize_entry(d)

    db_now_utc = _ensure_aware_utc(db_now)
    db_now_ms = int(db_now_utc.timestamp() * 1000) if db_now_utc else None
    server_now_ms = _server_now_ms()

    started = d.get('started_at')
    started_utc = _ensure_aware_utc(started)
    if started_utc and db_now_utc and started_utc > db_now_utc + timedelta(seconds=3):
        log.warning(
            'trail_history: started_at (%s) > db_now (%s) fila id=%s — revisar reloj BD / zona',
            started,
            db_now,
            d.get('id'),
        )

    if _DEBUG_TRAIL_CLOCK:
        log.info(
            'trail_history debug: entry id=%s started_at=%s db_now_ms=%s server_now_ms=%s',
            d.get('id'),
            entry.get('started_at'),
            db_now_ms,
            server_now_ms,
        )

    payload = {
        'entry': entry,
        'server_now_ms': server_now_ms,
        'db_now_ms': db_now_ms,
    }
    return payload, db_now_ms


@trail_history_bp.route('/me/trail-history/start', methods=['POST'])
@require_auth
async def trail_history_start(user_id: str):
    data = await request.get_json()
    trail_id = (data or {}).get('trail_id')
    if not trail_id:
        return jsonify({'error': 'trail_id requerido'}), 400
    try:
        uid = uuid.UUID(user_id)
        tid = uuid.UUID(str(trail_id))
    except ValueError:
        return jsonify({'error': 'ID inválido'}), 400

    async with get_conn() as conn:
        trail = await conn.fetchrow('SELECT id FROM trails WHERE id = $1', tid)
        if not trail:
            return jsonify({'error': 'Sendero no encontrado'}), 404

        row = await conn.fetchrow(
            """
            INSERT INTO user_trail_history (user_id, trail_id, completed, started_at)
            VALUES ($1, $2, FALSE, NOW())
            RETURNING id, trail_id, started_at, finished_at, completed, NOW() AS db_now
            """,
            uid,
            tid,
        )

    payload, _ = _entry_response(dict(row))
    return jsonify(payload), 200


@trail_history_bp.route('/me/trail-history/<history_id>/begin-recorrido', methods=['POST'])
@require_auth
async def trail_history_begin_recorrido(user_id: str, history_id: str):
    """
    Marca el instante real de inicio del recorrido en el mapa (app móvil).
    Actualiza started_at a NOW() solo para filas en curso del usuario.
    """
    try:
        uid = uuid.UUID(user_id)
        hid = uuid.UUID(history_id)
    except ValueError:
        return jsonify({'error': 'ID inválido'}), 400

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE user_trail_history
            SET started_at = NOW()
            WHERE id = $1 AND user_id = $2 AND completed = FALSE
            RETURNING id, trail_id, started_at, finished_at, completed, NOW() AS db_now
            """,
            hid,
            uid,
        )
        if not row:
            return jsonify({'error': 'Entrada no encontrada o ya completada'}), 404

    payload, _ = _entry_response(dict(row))
    return jsonify(payload), 200


@trail_history_bp.route('/me/trail-history/<history_id>/complete', methods=['POST'])
@require_auth
async def trail_history_complete(user_id: str, history_id: str):
    try:
        uid = uuid.UUID(user_id)
        hid = uuid.UUID(history_id)
    except ValueError:
        return jsonify({'error': 'ID inválido'}), 400

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE user_trail_history
            SET completed = TRUE,
                finished_at = COALESCE(finished_at, NOW())
            WHERE id = $1 AND user_id = $2
            RETURNING id, trail_id, started_at, finished_at, completed, NOW() AS db_now
            """,
            hid,
            uid,
        )
        if not row:
            return jsonify({'error': 'Entrada no encontrada'}), 404

    payload, _ = _entry_response(dict(row))
    return jsonify(payload), 200


@trail_history_bp.route('/me/completed-trails', methods=['GET'])
@require_auth
async def list_completed_trails(user_id: str):
    """Senderos marcados como completados (mismo formato que GET /me/favorite-trails)."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'ID inválido'}), 400

    async with get_conn() as conn:
        rows = await conn.fetch(
            _TRAILS_SELECT
            + """
INNER JOIN (
    SELECT DISTINCT ON (trail_id)
        trail_id,
        finished_at AS last_completed_at
    FROM user_trail_history
    WHERE user_id = $1 AND completed = TRUE
    ORDER BY trail_id, finished_at DESC NULLS LAST
) lp ON lp.trail_id = t.id
ORDER BY lp.last_completed_at DESC
""",
            uid,
        )
        total = len(rows)

    trails_list = [_serialize_trail_row(dict(row)) for row in rows]
    return (
        jsonify(
            {
                'trails': trails_list,
                'total': total,
                'limit': total,
                'offset': 0,
            }
        ),
        200,
    )


@trail_history_bp.route('/me/trail-history', methods=['GET'])
@require_auth
async def trail_history_list(user_id: str):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({'error': 'ID inválido'}), 400

    limit = request.args.get('limit', default='50')
    offset = request.args.get('offset', default='0')
    try:
        lim = max(1, min(100, int(limit)))
        off = max(0, int(offset))
    except ValueError:
        return jsonify({'error': 'limit u offset inválido'}), 400

    async with get_conn() as conn:
        total = await conn.fetchval(
            'SELECT COUNT(*)::bigint FROM user_trail_history WHERE user_id = $1',
            uid,
        )
        rows = await conn.fetch(
            """
            SELECT id, trail_id, started_at, finished_at, completed
            FROM user_trail_history
            WHERE user_id = $1
            ORDER BY started_at DESC
            LIMIT $2 OFFSET $3
            """,
            uid,
            lim,
            off,
        )

    entries = [_serialize_entry(r) for r in rows]
    return jsonify({
        'entries': entries,
        'total': int(total or 0),
        'server_now_ms': _server_now_ms(),
    }), 200

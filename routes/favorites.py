"""
Favoritos del usuario (senderos / trails)
"""
import json as _json
import uuid
from decimal import Decimal

import asyncpg
from quart import Blueprint, jsonify
from db import get_conn
from routes.trails import require_auth

favorites_bp = Blueprint("favorites", __name__)


def _serialize_trail_row(trail_dict: dict) -> dict:
    if trail_dict.get("id"):
        trail_dict["id"] = str(trail_dict["id"])
    if trail_dict.get("created_by"):
        trail_dict["created_by"] = str(trail_dict["created_by"])
    if isinstance(trail_dict.get("distance_km"), Decimal):
        trail_dict["distance_km"] = float(trail_dict["distance_km"])
    if trail_dict.get("map_point"):
        try:
            trail_dict["map_point"] = _json.loads(trail_dict["map_point"])
        except Exception:
            trail_dict["map_point"] = None
    else:
        trail_dict["map_point"] = None
    for dt_field in ("created_at", "updated_at"):
        if trail_dict.get(dt_field):
            trail_dict[dt_field] = trail_dict[dt_field].isoformat()
    if trail_dict.get("image_urls") is None:
        trail_dict["image_urls"] = []
    else:
        trail_dict["image_urls"] = list(trail_dict["image_urls"])
    return trail_dict


_TRAILS_SELECT = """
    SELECT
        t.id, t.slug, t.name, t.difficulty, t.route_type, t.region,
        t.distance_km, t.elevation_gain, t.elevation_loss,
        t.max_altitude, t.min_altitude, t.duration_minutes,
        t.is_featured, t.is_premium, t.status_id, t.created_by,
        t.created_at, t.updated_at, t.description,
        t.map_point::text AS map_point,
        (SELECT url FROM trail_media
            WHERE trail_id = t.id
            AND media_type IN ('image', 'photo_360', 'photo_180')
            ORDER BY order_index ASC, created_at ASC
            LIMIT 1) AS thumbnail_url,
        ARRAY(SELECT url FROM trail_media
            WHERE trail_id = t.id
            AND media_type IN ('image', 'photo_360', 'photo_180')
            ORDER BY order_index ASC, created_at ASC) AS image_urls
    FROM trails t
"""


@favorites_bp.route("/me/favorite-trails", methods=["GET"])
@require_auth
async def list_favorite_trails(user_id: str):
    """Lista los senderos marcados como favoritos por el usuario (mismo formato que GET /trails)."""
    uid = uuid.UUID(user_id)
    async with get_conn() as conn:
        rows = await conn.fetch(
            f"""
            {_TRAILS_SELECT}
            INNER JOIN user_favorites uf
                ON uf.entity_id = t.id
                AND uf.entity_type = 'trail'
                AND uf.user_id = $1
            ORDER BY uf.created_at DESC
            """,
            uid,
        )
        total = len(rows)

    trails_list = [_serialize_trail_row(dict(row)) for row in rows]
    return (
        jsonify(
            {
                "trails": trails_list,
                "total": total,
                "limit": total,
                "offset": 0,
            }
        ),
        200,
    )


@favorites_bp.route("/me/favorite-trails/<trail_id>", methods=["POST"])
@require_auth
async def add_favorite_trail(user_id: str, trail_id: str):
    """Agrega un sendero a favoritos (idempotente)."""
    try:
        tid = uuid.UUID(trail_id)
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "ID de sendero inválido"}), 400

    async with get_conn() as conn:
        exists = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", tid)
        if not exists:
            return jsonify({"error": "Sendero no encontrado"}), 404
        await conn.execute(
            """
            INSERT INTO user_favorites (user_id, entity_type, entity_id)
            VALUES ($1, 'trail', $2)
            ON CONFLICT (user_id, entity_type, entity_id) DO NOTHING
            """,
            uid,
            tid,
        )
    return jsonify({"favorited": True}), 200


@favorites_bp.route("/me/favorite-trails/<trail_id>", methods=["DELETE"])
@require_auth
async def remove_favorite_trail(user_id: str, trail_id: str):
    """Quita un sendero de favoritos."""
    try:
        tid = uuid.UUID(trail_id)
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "ID de sendero inválido"}), 400

    async with get_conn() as conn:
        await conn.execute(
            """
            DELETE FROM user_favorites
            WHERE user_id = $1 AND entity_type = 'trail' AND entity_id = $2
            """,
            uid,
            tid,
        )
    return jsonify({"favorited": False}), 200


@favorites_bp.route("/me/favorite-trails/ids", methods=["GET"])
@require_auth
async def list_favorite_trail_ids(user_id: str):
    """IDs de senderos favoritos (sincronización ligera en la app)."""
    uid = uuid.UUID(user_id)
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT entity_id::text AS id
            FROM user_favorites
            WHERE user_id = $1 AND entity_type = 'trail'
            ORDER BY created_at DESC
            """,
            uid,
        )
    return jsonify({"trail_ids": [r["id"] for r in rows]}), 200


@favorites_bp.route("/me/favorite-places/ids", methods=["GET"])
@require_auth
async def list_favorite_place_ids(user_id: str):
    """IDs de lugares favoritos (sincronización ligera en la app). Debe ir antes de /<place_id>."""
    uid = uuid.UUID(user_id)
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT entity_id::text AS id
            FROM user_favorites
            WHERE user_id = $1 AND entity_type = 'place'
            ORDER BY created_at DESC
            """,
            uid,
        )
    return jsonify({"place_ids": [r["id"] for r in rows]}), 200


@favorites_bp.route("/me/favorite-places", methods=["GET"])
@require_auth
async def list_favorite_places_unimplemented():
    """Reservado: listado de lugares (la app solo sincroniza IDs)."""
    return jsonify({"error": "use /me/favorite-places/ids o admin"}), 501


@favorites_bp.route("/me/favorite-places/<place_id>", methods=["POST"])
@require_auth
async def add_favorite_place(user_id: str, place_id: str):
    try:
        pid = uuid.UUID(place_id)
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "ID de lugar inválido"}), 400

    async with get_conn() as conn:
        exists = await conn.fetchrow("SELECT id FROM tourist_places WHERE id = $1", pid)
        if not exists:
            return jsonify({"error": "Lugar no encontrado"}), 404
        await conn.execute(
            """
            INSERT INTO user_favorites (user_id, entity_type, entity_id)
            VALUES ($1, 'place', $2)
            ON CONFLICT (user_id, entity_type, entity_id) DO NOTHING
            """,
            uid,
            pid,
        )
    return jsonify({"favorited": True}), 200


@favorites_bp.route("/me/favorite-places/<place_id>", methods=["DELETE"])
@require_auth
async def remove_favorite_place(user_id: str, place_id: str):
    try:
        pid = uuid.UUID(place_id)
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "ID de lugar inválido"}), 400

    async with get_conn() as conn:
        await conn.execute(
            """
            DELETE FROM user_favorites
            WHERE user_id = $1 AND entity_type = 'place' AND entity_id = $2
            """,
            uid,
            pid,
        )
    return jsonify({"favorited": False}), 200


async def _safe_count(conn, sql: str, uid: uuid.UUID) -> int:
    try:
        n = await conn.fetchval(sql, uid)
        return int(n) if n is not None else 0
    except asyncpg.exceptions.PostgresError as e:
        if e.sqlstate in ("42P01", "42703"):
            return 0
        raise


@favorites_bp.route("/me/profile-stats", methods=["GET"])
@require_auth
async def profile_stats(user_id: str):
    """
    Contadores para el perfil: senderos completados, reseñas, favoritos.
    Tablas opcionales (trail_reviews, user_trail_history) → 0 si no existen.
    """
    uid = uuid.UUID(user_id)
    async with get_conn() as conn:
        favorites_n = await _safe_count(
            conn,
            "SELECT COUNT(*)::bigint FROM user_favorites WHERE user_id = $1",
            uid,
        )
        reviews_n = await _safe_count(
            conn,
            "SELECT COUNT(*)::bigint FROM trail_reviews WHERE user_id = $1",
            uid,
        )
        completed_n = await _safe_count(
            conn,
            """
            SELECT COUNT(DISTINCT trail_id)::bigint
            FROM user_trail_history
            WHERE user_id = $1 AND completed = true
            """,
            uid,
        )

    return (
        jsonify(
            {
                "completed_trails_count": completed_n,
                "reviews_count": reviews_n,
                "favorites_count": favorites_n,
            }
        ),
        200,
    )

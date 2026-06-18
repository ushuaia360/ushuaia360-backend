"""
Reportes — enviados desde la app móvil, gestionados desde el panel admin
"""
from quart import Blueprint, request, jsonify
from functools import wraps
from db import get_conn
from routes.auth import decode_jwt_token
import uuid

reports_bp = Blueprint("reports", __name__)

VALID_TARGET_TYPES = {"trail", "place", "review"}
VALID_STATUSES = {"pending", "reviewed", "dismissed"}


def _optional_user_id() -> str | None:
    """Extrae el user_id del JWT si está presente, sin fallar si no hay token."""
    token = request.cookies.get("token")
    if not token:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            token = authz.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_jwt_token(token)
        return payload.get("user_id")
    except (ValueError, Exception):
        return None


def require_admin(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            authz = request.headers.get("Authorization", "")
            if authz.startswith("Bearer "):
                token = authz.split(" ", 1)[1].strip()
        if not token:
            return jsonify({"error": "No autenticado"}), 401
        try:
            payload = decode_jwt_token(token)
            user_id = payload["user_id"]
        except ValueError as e:
            return jsonify({"error": str(e)}), 401
        async with get_conn() as conn:
            row = await conn.fetchrow("SELECT is_admin FROM users WHERE id = $1", user_id)
            if not row or not row["is_admin"]:
                return jsonify({"error": "Se requieren permisos de administrador"}), 403
        kwargs["user_id"] = user_id
        return await f(*args, **kwargs)
    return decorated


# ── Endpoint público (app móvil) ──────────────────────────────────────────────

@reports_bp.route("/reports", methods=["POST"])
async def create_report():
    user_id = _optional_user_id()
    data = await request.get_json(silent=True) or {}

    target_type = data.get("target_type", "").strip()
    target_id_raw = data.get("target_id", "")
    reason = data.get("reason", "").strip() or "sin motivo"
    context_id_raw = data.get("context_id")

    if target_type not in VALID_TARGET_TYPES:
        return jsonify({"error": "target_type inválido"}), 400
    if not target_id_raw:
        return jsonify({"error": "target_id requerido"}), 400

    try:
        target_uuid = uuid.UUID(str(target_id_raw))
    except ValueError:
        return jsonify({"error": "target_id inválido"}), 400

    context_uuid = None
    if context_id_raw:
        try:
            context_uuid = uuid.UUID(str(context_id_raw))
        except ValueError:
            pass

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO reports (target_type, target_id, reported_by, reason, context_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, created_at
            """,
            target_type,
            target_uuid,
            user_id,
            reason,
            context_uuid,
        )

    return jsonify({
        "message": "Reporte enviado correctamente",
        "report": {
            "id": str(row["id"]),
            "created_at": row["created_at"].isoformat(),
        },
    }), 201


# ── Endpoints admin ───────────────────────────────────────────────────────────

@reports_bp.route("/admin/reports", methods=["GET"])
@require_admin
async def list_reports(user_id: str):
    status_filter = request.args.get("status", "pending").strip()
    type_filter = request.args.get("target_type", "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    conditions = []
    params: list = []
    idx = 1

    if status_filter and status_filter != "all":
        conditions.append(f"r.status = ${idx}")
        params.append(status_filter)
        idx += 1

    if type_filter and type_filter in VALID_TARGET_TYPES:
        conditions.append(f"r.target_type = ${idx}")
        params.append(type_filter)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_params = params.copy()
    params.extend([limit, offset])

    async with get_conn() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                r.id,
                r.target_type,
                r.target_id,
                r.reason,
                r.status,
                r.context_id,
                r.created_at,
                u.full_name  AS reporter_name,
                u.email      AS reporter_email,
                CASE
                    WHEN r.target_type = 'trail'
                        THEN (SELECT name FROM trails WHERE id = r.target_id)
                    WHEN r.target_type = 'place'
                        THEN (SELECT name FROM tourist_places WHERE id = r.target_id)
                    WHEN r.target_type = 'review'
                        THEN COALESCE(
                            (SELECT LEFT(comment, 120) FROM trail_reviews  WHERE id = r.target_id),
                            (SELECT LEFT(comment, 120) FROM place_reviews WHERE id = r.target_id)
                        )
                    ELSE NULL
                END AS target_name
            FROM reports r
            LEFT JOIN users u ON u.id = r.reported_by
            {where}
            ORDER BY r.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )

        total_row = await conn.fetchrow(
            f"SELECT COUNT(*) FROM reports r {where}",
            *count_params,
        )

    reports = [
        {
            "id": str(r["id"]),
            "target_type": r["target_type"],
            "target_id": str(r["target_id"]),
            "reason": r["reason"],
            "status": r["status"],
            "context_id": str(r["context_id"]) if r["context_id"] else None,
            "created_at": r["created_at"].isoformat(),
            "reporter_name": r["reporter_name"],
            "reporter_email": r["reporter_email"],
            "target_name": r["target_name"],
        }
        for r in rows
    ]

    return jsonify({
        "reports": reports,
        "total": total_row["count"],
        "limit": limit,
        "offset": offset,
    })


@reports_bp.route("/admin/reports/<report_id>", methods=["PATCH"])
@require_admin
async def update_report(report_id: str, user_id: str):
    data = await request.get_json(silent=True) or {}
    new_status = data.get("status", "").strip()

    if new_status not in VALID_STATUSES:
        return jsonify({"error": "status inválido. Debe ser pending, reviewed o dismissed"}), 400

    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        return jsonify({"error": "ID de reporte inválido"}), 400

    async with get_conn() as conn:
        row = await conn.fetchrow(
            "UPDATE reports SET status = $1 WHERE id = $2 RETURNING id, status",
            new_status,
            report_uuid,
        )

    if not row:
        return jsonify({"error": "Reporte no encontrado"}), 404

    return jsonify({"message": "Reporte actualizado", "status": row["status"]})

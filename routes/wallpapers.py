import uuid

import asyncpg
from quart import Blueprint, jsonify, request

from db import get_conn
from routes.trails import require_admin

wallpapers_bp = Blueprint("wallpapers", __name__)


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    return d


@wallpapers_bp.route("/wallpapers", methods=["GET"])
async def list_wallpapers():
    """Lista todos los wallpapers ordenados."""
    limit = request.args.get("limit", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = min(max(limit or 100, 1), 200)
    offset = max(offset or 0, 0)

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT id, url, title, order_index, created_at
                FROM wallpapers
                ORDER BY order_index ASC, created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM wallpapers")
    except asyncpg.exceptions.PostgresError as e:
        if e.sqlstate == "42P01":
            return jsonify({"wallpapers": [], "total": 0}), 200
        raise

    return jsonify({
        "wallpapers": [_row_to_dict(r) for r in rows],
        "total": int(total or 0),
    }), 200


@wallpapers_bp.route("/wallpapers", methods=["POST"])
@require_admin
async def create_wallpaper(user_id: str):
    """
    Registrar un wallpaper (URL ya subida a Storage por el cliente).

    Body:
    {
        "url": string (requerido),
        "title": string (opcional),
        "order_index": int (opcional, default 0)
    }
    """
    data = await request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "El campo 'url' es requerido"}), 400

    url = data["url"].strip()
    title = (data.get("title") or "").strip() or None
    order_index = int(data.get("order_index") or 0)

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO wallpapers (url, title, order_index)
                VALUES ($1, $2, $3)
                RETURNING id, url, title, order_index, created_at
                """,
                url,
                title,
                order_index,
            )
    except asyncpg.exceptions.PostgresError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "Wallpaper creado exitosamente",
        "wallpaper": _row_to_dict(row),
    }), 201


@wallpapers_bp.route("/wallpapers/<wallpaper_id>", methods=["PATCH"])
@require_admin
async def update_wallpaper(wallpaper_id: str, user_id: str):
    """Actualizar título u orden de un wallpaper."""
    try:
        wp_uuid = uuid.UUID(wallpaper_id)
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400

    data = await request.get_json()
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400

    updates = {}
    if "title" in data:
        updates["title"] = (data["title"] or "").strip() or None
    if "order_index" in data:
        updates["order_index"] = int(data["order_index"] or 0)

    if not updates:
        return jsonify({"error": "Sin campos a actualizar"}), 400

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    values = [wp_uuid] + list(updates.values())

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE wallpapers SET {set_clause}
                WHERE id = $1
                RETURNING id, url, title, order_index, created_at
                """,
                *values,
            )
    except asyncpg.exceptions.PostgresError as e:
        return jsonify({"error": str(e)}), 400

    if not row:
        return jsonify({"error": "Wallpaper no encontrado"}), 404

    return jsonify({"message": "Actualizado", "wallpaper": _row_to_dict(row)}), 200


@wallpapers_bp.route("/wallpapers/<wallpaper_id>", methods=["DELETE"])
@require_admin
async def delete_wallpaper(wallpaper_id: str, user_id: str):
    """Eliminar un wallpaper."""
    try:
        wp_uuid = uuid.UUID(wallpaper_id)
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400

    try:
        async with get_conn() as conn:
            result = await conn.execute(
                "DELETE FROM wallpapers WHERE id = $1", wp_uuid
            )
    except asyncpg.exceptions.PostgresError as e:
        return jsonify({"error": str(e)}), 400

    if result == "DELETE 0":
        return jsonify({"error": "Wallpaper no encontrado"}), 404

    return jsonify({"message": "Wallpaper eliminado"}), 200

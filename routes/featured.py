"""
Ítems destacados (senderos + puntos turísticos) — gestionados desde el panel admin (Partners).
"""
import uuid

import asyncpg
from quart import Blueprint, jsonify, request
from db import get_conn
from routes.trails import require_admin

featured_bp = Blueprint("featured", __name__)

VALID_ENTITY_TYPES = {"trail", "place"}


@featured_bp.route("/featured", methods=["GET"])
async def list_featured():
    """Lista de destacados (senderos + puntos turísticos), ordenada por order_index."""
    async with get_conn() as conn:
        featured_rows = await conn.fetch(
            "SELECT id, entity_type, entity_id, order_index FROM featured_items ORDER BY order_index ASC"
        )

        trail_ids = [r["entity_id"] for r in featured_rows if r["entity_type"] == "trail"]
        place_ids = [r["entity_id"] for r in featured_rows if r["entity_type"] == "place"]

        trails_by_id: dict = {}
        if trail_ids:
            trail_rows = await conn.fetch(
                """
                SELECT
                    t.id, t.slug, t.name, t.difficulty, t.route_type, t.region,
                    t.distance_km, t.duration_minutes, t.description,
                    (SELECT url FROM trail_media
                        WHERE trail_id = t.id
                        AND media_type IN ('image', 'photo_360', 'photo_180')
                        ORDER BY order_index ASC, created_at ASC
                        LIMIT 1) AS thumbnail_url
                FROM trails t
                WHERE t.id = ANY($1::uuid[])
                """,
                trail_ids,
            )
            trails_by_id = {row["id"]: row for row in trail_rows}

        places_by_id: dict = {}
        try:
            if place_ids:
                place_rows = await conn.fetch(
                    """
                    SELECT
                        p.id, p.slug, p.name, p.category, p.region, p.country, p.description,
                        (SELECT url FROM place_media
                            WHERE place_id = p.id
                            AND media_type IN ('image', 'photo_360', 'photo_180')
                            ORDER BY order_index ASC, created_at ASC
                            LIMIT 1) AS thumbnail_url
                    FROM tourist_places p
                    WHERE p.id = ANY($1::uuid[])
                    """,
                    place_ids,
                )
                places_by_id = {row["id"]: row for row in place_rows}
        except asyncpg.exceptions.PostgresError as e:
            # 42P01 = undefined_table, 42703 = undefined_column (esquema distinto)
            if e.sqlstate in ("42P01", "42703"):
                places_by_id = {}
            else:
                raise

    items = []
    for r in featured_rows:
        if r["entity_type"] == "trail":
            row = trails_by_id.get(r["entity_id"])
            if not row:
                continue
            dkm = row["distance_km"]
            items.append(
                {
                    "featured_item_id": str(r["id"]),
                    "order_index": r["order_index"],
                    "kind": "trail",
                    "id": str(row["id"]),
                    "slug": row["slug"],
                    "name": row["name"] or row["slug"] or "Sendero",
                    "difficulty": row["difficulty"],
                    "route_type": row["route_type"],
                    "region": row["region"],
                    "distance_km": float(dkm) if dkm is not None else None,
                    "duration_minutes": row["duration_minutes"],
                    "description": row["description"],
                    "thumbnail_url": row["thumbnail_url"],
                }
            )
        else:
            row = places_by_id.get(r["entity_id"])
            if not row:
                continue
            items.append(
                {
                    "featured_item_id": str(r["id"]),
                    "order_index": r["order_index"],
                    "kind": "place",
                    "id": str(row["id"]),
                    "slug": row["slug"],
                    "name": row["name"] or row["slug"] or "Lugar",
                    "category": row["category"],
                    "region": row["region"],
                    "country": row["country"],
                    "description": row["description"],
                    "thumbnail_url": row["thumbnail_url"],
                }
            )

    return jsonify({"items": items}), 200


@featured_bp.route("/featured", methods=["POST"])
@require_admin
async def add_featured(user_id: str):
    data = await request.get_json(silent=True) or {}
    entity_type = data.get("entity_type", "").strip()
    entity_id_raw = data.get("entity_id", "")

    if entity_type not in VALID_ENTITY_TYPES:
        return jsonify({"error": "entity_type inválido"}), 400
    try:
        entity_uuid = uuid.UUID(str(entity_id_raw))
    except ValueError:
        return jsonify({"error": "entity_id inválido"}), 400

    async with get_conn() as conn:
        table = "trails" if entity_type == "trail" else "tourist_places"
        exists = await conn.fetchval(f"SELECT 1 FROM {table} WHERE id = $1", entity_uuid)
        if not exists:
            return jsonify({"error": "El sendero/punto turístico no existe"}), 404

        try:
            row = await conn.fetchrow(
                """
                INSERT INTO featured_items (entity_type, entity_id, order_index)
                VALUES ($1, $2, COALESCE((SELECT MAX(order_index) + 1 FROM featured_items), 0))
                RETURNING id, order_index
                """,
                entity_type,
                entity_uuid,
            )
        except asyncpg.exceptions.UniqueViolationError:
            return jsonify({"error": "Ya está destacado"}), 409

    return jsonify({
        "message": "Agregado a destacados",
        "featured_item_id": str(row["id"]),
        "order_index": row["order_index"],
    }), 201


@featured_bp.route("/featured/<featured_item_id>", methods=["DELETE"])
@require_admin
async def remove_featured(featured_item_id: str, user_id: str):
    try:
        item_uuid = uuid.UUID(featured_item_id)
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400

    async with get_conn() as conn:
        row = await conn.fetchrow("DELETE FROM featured_items WHERE id = $1 RETURNING id", item_uuid)

    if not row:
        return jsonify({"error": "No encontrado"}), 404

    return jsonify({"message": "Eliminado de destacados"}), 200


@featured_bp.route("/featured/<featured_item_id>/move", methods=["PATCH"])
@require_admin
async def move_featured(featured_item_id: str, user_id: str):
    data = await request.get_json(silent=True) or {}
    direction = data.get("direction", "").strip()
    if direction not in ("up", "down"):
        return jsonify({"error": "direction debe ser 'up' o 'down'"}), 400

    try:
        item_uuid = uuid.UUID(featured_item_id)
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400

    async with get_conn() as conn:
        current = await conn.fetchrow(
            "SELECT id, order_index FROM featured_items WHERE id = $1", item_uuid
        )
        if not current:
            return jsonify({"error": "No encontrado"}), 404

        if direction == "up":
            neighbor = await conn.fetchrow(
                "SELECT id, order_index FROM featured_items WHERE order_index < $1 ORDER BY order_index DESC LIMIT 1",
                current["order_index"],
            )
        else:
            neighbor = await conn.fetchrow(
                "SELECT id, order_index FROM featured_items WHERE order_index > $1 ORDER BY order_index ASC LIMIT 1",
                current["order_index"],
            )

        if not neighbor:
            return jsonify({"message": "Sin cambios"}), 200

        async with conn.transaction():
            await conn.execute(
                "UPDATE featured_items SET order_index = $1 WHERE id = $2",
                neighbor["order_index"],
                current["id"],
            )
            await conn.execute(
                "UPDATE featured_items SET order_index = $1 WHERE id = $2",
                current["order_index"],
                neighbor["id"],
            )

    return jsonify({"message": "Orden actualizado"}), 200

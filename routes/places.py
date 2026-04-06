"""
Lugares turísticos (lectura pública para la app).
"""
import json
import uuid

import asyncpg
from quart import Blueprint, jsonify
from db import get_conn

places_bp = Blueprint("places", __name__)


@places_bp.route("/places/<place_id>", methods=["GET"])
async def get_place(place_id: str):
    """Detalle de un lugar turístico."""
    try:
        pid = uuid.UUID(place_id)
    except ValueError:
        return jsonify({"error": "ID de lugar inválido"}), 400

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.id, p.slug, p.name, p.category, p.region, p.country,
                    p.description, p.is_premium,
                    ST_Y(p.location::geometry) AS latitude,
                    ST_X(p.location::geometry) AS longitude,
                    p.created_at, p.updated_at,
                    ARRAY(
                        SELECT url FROM place_media
                        WHERE place_id = p.id
                        AND media_type IN ('image', 'photo_360', 'photo_180')
                        ORDER BY order_index ASC, created_at ASC
                    ) AS image_urls,
                    COALESCE(
                        (
                            SELECT json_agg(
                                json_build_object(
                                    'id', m.id::text,
                                    'media_type', m.media_type,
                                    'url', m.url,
                                    'thumbnail_url', m.thumbnail_url,
                                    'order_index', m.order_index
                                )
                                ORDER BY m.order_index ASC NULLS LAST, m.created_at ASC
                            )
                            FROM place_media m
                            WHERE m.place_id = p.id
                              AND m.media_type IN ('image', 'photo_360', 'photo_180')
                        ),
                        '[]'::json
                    ) AS media
                FROM tourist_places p
                WHERE p.id = $1
                """,
                pid,
            )
    except asyncpg.exceptions.PostgresError as e:
        if e.sqlstate in ("42P01", "42703"):
            return jsonify({"error": "Lugares turísticos no disponibles"}), 503
        raise

    if not row:
        return jsonify({"error": "Lugar no encontrado"}), 404

    d = dict(row)
    d["id"] = str(d["id"])
    d["latitude"] = float(d["latitude"]) if d.get("latitude") is not None else None
    d["longitude"] = float(d["longitude"]) if d.get("longitude") is not None else None
    if d.get("image_urls") is not None:
        d["image_urls"] = list(d["image_urls"])
    else:
        d["image_urls"] = []
    raw_media = d.pop("media", None)
    if raw_media is None:
        d["media"] = []
    elif isinstance(raw_media, str):
        try:
            d["media"] = json.loads(raw_media)
        except json.JSONDecodeError:
            d["media"] = []
    else:
        d["media"] = list(raw_media) if raw_media else []
    for dt_field in ("created_at", "updated_at"):
        if d.get(dt_field):
            d[dt_field] = d[dt_field].isoformat()
    return jsonify({"place": d}), 200

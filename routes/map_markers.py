"""
Marcadores públicos para el mapa (senderos + lugares turísticos).
"""
import json
from decimal import Decimal

import asyncpg
from quart import Blueprint, jsonify
from db import get_conn

map_bp = Blueprint("map", __name__)


def _parse_map_point(raw) -> tuple[float, float] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not isinstance(raw, dict):
        return None
    lat = raw.get("latitude")
    lng = raw.get("longitude")
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


@map_bp.route("/map/markers", methods=["GET"])
async def list_map_markers():
    """
    Senderos con map_point y lugares turísticos con ubicación.
    Si la tabla tourist_places no existe, solo se devuelven senderos.
    """
    markers: list[dict] = []

    async with get_conn() as conn:
        trail_rows = await conn.fetch(
            """
            SELECT
                t.id, t.slug, t.name, t.difficulty, t.route_type, t.region,
                t.distance_km, t.duration_minutes, t.elevation_gain, t.description,
                t.map_point::text AS map_point,
                (SELECT url FROM trail_media
                    WHERE trail_id = t.id
                    AND media_type IN ('image', 'photo_360', 'photo_180')
                    ORDER BY order_index ASC, created_at ASC
                    LIMIT 1) AS thumbnail_url
            FROM trails t
            WHERE t.map_point IS NOT NULL
            """
        )

        for row in trail_rows:
            coords = _parse_map_point(row["map_point"])
            if not coords:
                continue
            lat, lng = coords
            thumb = row["thumbnail_url"]
            dkm = row["distance_km"]
            desc = (row.get("description") or "").strip()
            if len(desc) > 360:
                desc = desc[:357].rsplit(" ", 1)[0] + "…"
            eg = row.get("elevation_gain")
            eg_out = None
            if eg is not None:
                try:
                    eg_out = int(float(eg))
                except (TypeError, ValueError):
                    eg_out = None
            markers.append(
                {
                    "kind": "trail",
                    "id": str(row["id"]),
                    "slug": row["slug"],
                    "name": row["name"] or row["slug"] or "Sendero",
                    "latitude": lat,
                    "longitude": lng,
                    "difficulty": row["difficulty"],
                    "route_type": row.get("route_type"),
                    "region": row.get("region"),
                    "distance_km": float(dkm) if isinstance(dkm, Decimal) else dkm,
                    "duration_minutes": row["duration_minutes"],
                    "elevation_gain": eg_out,
                    "description": desc or None,
                    "thumbnail_url": thumb,
                }
            )

        try:
            place_rows = await conn.fetch(
                """
                SELECT
                    p.id, p.slug, p.name, p.category, p.region, p.description,
                    ST_Y(p.location::geometry) AS latitude,
                    ST_X(p.location::geometry) AS longitude,
                    (SELECT url FROM place_media
                        WHERE place_id = p.id
                        AND media_type IN ('image', 'photo_360', 'photo_180')
                        ORDER BY order_index ASC, created_at ASC
                        LIMIT 1) AS thumbnail_url
                FROM tourist_places p
                WHERE p.location IS NOT NULL
                """
            )
            for row in place_rows:
                lat = row["latitude"]
                lng = row["longitude"]
                if lat is None or lng is None:
                    continue
                pdesc = (row.get("description") or "").strip()
                if len(pdesc) > 420:
                    pdesc = pdesc[:417].rsplit(" ", 1)[0] + "…"
                markers.append(
                    {
                        "kind": "place",
                        "id": str(row["id"]),
                        "slug": row["slug"],
                        "name": row["name"] or row["slug"] or "Lugar",
                        "category": row["category"],
                        "region": row["region"],
                        "description": pdesc or None,
                        "latitude": float(lat),
                        "longitude": float(lng),
                        "thumbnail_url": row["thumbnail_url"],
                    }
                )
        except asyncpg.exceptions.PostgresError as e:
            # 42P01 = undefined_table, 42703 = undefined_column (esquema distinto)
            if e.sqlstate in ("42P01", "42703"):
                pass
            else:
                raise

    return jsonify({"markers": markers}), 200

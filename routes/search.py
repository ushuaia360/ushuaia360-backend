"""
Búsqueda: sugerencias (autocomplete) para la app móvil.

Devuelve una lista combinada de senderos (trails) y puntos turísticos (tourist_places)
en base a un término de búsqueda.
"""

import json

import asyncpg
from quart import Blueprint, jsonify, request

from db import get_conn

search_bp = Blueprint("search", __name__)


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
    lat = raw.get("latitude", raw.get("lat"))
    lng = raw.get("longitude", raw.get("lng", raw.get("lon")))
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def _sort_key(name: str | None, slug: str | None, term: str) -> tuple[int, int]:
    """
    Orden heurístico:
    0) match exacto
    1) empieza con
    2) contiene
    Luego por longitud (más corto primero).
    """
    t = (term or "").strip().lower()
    n = (name or "").strip().lower()
    s = (slug or "").strip().lower()
    if not t:
        return (2, 9999)
    if n == t or s == t:
        return (0, len(n) or len(s))
    if n.startswith(t) or s.startswith(t):
        return (1, len(n) or len(s))
    return (2, len(n) or len(s))


@search_bp.route("/search/suggest", methods=["GET"])
async def suggest():
    """
    Sugerencias para autocompletado.

    Query params:
    - q / search: término
    - limit: máximo de resultados (default 10, max 20)
    - types: "trail,place" (default ambos)
    """
    term = (request.args.get("q") or request.args.get("search") or "").strip()
    limit = request.args.get("limit", default=10, type=int)
    limit = min(max(limit or 10, 1), 20)
    if not term:
        # En modo "sugeridos" (input vacío) mantenemos una lista chica por UX.
        limit = min(limit, 5)
    types_raw = (request.args.get("types") or "").strip().lower()
    types = {t.strip() for t in types_raw.split(",") if t.strip()} if types_raw else {"trail", "place"}
    types = {t for t in types if t in {"trail", "place"}}
    if not types:
        return jsonify({"suggestions": []}), 200

    # Traemos un poco más para ordenar del lado del servidor (Python) con heurística simple.
    fetch_limit = min(limit * 3, 50)
    suggestions: list[dict] = []

    async with get_conn() as conn:
        if "trail" in types:
            try:
                if term:
                    trail_rows = await conn.fetch(
                        """
                        SELECT
                            t.id, t.slug, t.name, t.region,
                            t.distance_km, t.duration_minutes, t.elevation_gain,
                            t.map_point::text AS map_point,
                            (SELECT url FROM trail_media
                                WHERE trail_id = t.id
                                AND media_type IN ('image', 'photo_360', 'photo_180')
                                ORDER BY order_index ASC, created_at ASC
                                LIMIT 1) AS thumbnail_url
                        FROM trails t
                        WHERE
                            (COALESCE(t.name::text,'') || ' ' || COALESCE(t.slug::text,'') || ' ' || COALESCE(t.region::text,'')) ILIKE $1
                        LIMIT $2
                        """,
                        f"%{term}%",
                        fetch_limit,
                    )
                else:
                    # Sugeridos por defecto: primero destacados, luego más recientes.
                    trail_rows = await conn.fetch(
                        """
                        SELECT
                            t.id, t.slug, t.name, t.region,
                            t.distance_km, t.duration_minutes, t.elevation_gain,
                            t.map_point::text AS map_point,
                            (SELECT url FROM trail_media
                                WHERE trail_id = t.id
                                AND media_type IN ('image', 'photo_360', 'photo_180')
                                ORDER BY order_index ASC, created_at ASC
                                LIMIT 1) AS thumbnail_url
                        FROM trails t
                        ORDER BY t.is_featured DESC, t.created_at DESC
                        LIMIT $1
                        """,
                        fetch_limit,
                    )
            except asyncpg.exceptions.PostgresError as e:
                if e.sqlstate in ("42P01", "42703"):
                    trail_rows = []
                else:
                    raise

            for row in trail_rows:
                coords = _parse_map_point(row.get("map_point"))
                lat = coords[0] if coords else None
                lng = coords[1] if coords else None
                distance_km = row.get("distance_km")
                elevation_gain = row.get("elevation_gain")
                duration_minutes = row.get("duration_minutes")
                try:
                    distance_km = float(distance_km) if distance_km is not None else None
                except (TypeError, ValueError):
                    distance_km = None
                try:
                    elevation_gain = int(float(elevation_gain)) if elevation_gain is not None else None
                except (TypeError, ValueError):
                    elevation_gain = None
                try:
                    duration_minutes = int(duration_minutes) if duration_minutes is not None else None
                except (TypeError, ValueError):
                    duration_minutes = None
                suggestions.append(
                    {
                        "type": "trail",
                        "id": str(row["id"]),
                        "slug": row.get("slug"),
                        "name": row.get("name") or row.get("slug") or "Sendero",
                        "region": row.get("region"),
                        "thumbnail_url": row.get("thumbnail_url"),
                        "latitude": lat,
                        "longitude": lng,
                        "distance_km": distance_km,
                        "duration_minutes": duration_minutes,
                        "elevation_gain": elevation_gain,
                    }
                )

        if "place" in types:
            try:
                if term:
                    place_rows = await conn.fetch(
                        """
                        SELECT
                            p.id, p.slug, p.name, p.category, p.region, p.country,
                            p.location::text AS location,
                            (SELECT url FROM place_media
                                WHERE place_id = p.id
                                AND media_type IN ('image', 'photo_360', 'photo_180')
                                ORDER BY order_index ASC, created_at ASC
                                LIMIT 1) AS thumbnail_url
                        FROM tourist_places p
                        WHERE
                            (COALESCE(p.name::text,'') || ' ' || COALESCE(p.slug::text,'') || ' ' || COALESCE(p.region::text,'') || ' ' || COALESCE(p.country::text,'')) ILIKE $1
                        LIMIT $2
                        """,
                        f"%{term}%",
                        fetch_limit,
                    )
                else:
                    place_rows = await conn.fetch(
                        """
                        SELECT
                            p.id, p.slug, p.name, p.category, p.region, p.country,
                            p.location::text AS location,
                            (SELECT url FROM place_media
                                WHERE place_id = p.id
                                AND media_type IN ('image', 'photo_360', 'photo_180')
                                ORDER BY order_index ASC, created_at ASC
                                LIMIT 1) AS thumbnail_url
                        FROM tourist_places p
                        ORDER BY p.created_at DESC
                        LIMIT $1
                        """,
                        fetch_limit,
                    )
            except asyncpg.exceptions.PostgresError as e:
                if e.sqlstate in ("42P01", "42703"):
                    place_rows = []
                else:
                    raise

            for row in place_rows:
                coords = _parse_map_point(row.get("location"))
                lat = coords[0] if coords else None
                lng = coords[1] if coords else None
                suggestions.append(
                    {
                        "type": "place",
                        "id": str(row["id"]),
                        "slug": row.get("slug"),
                        "name": row.get("name") or row.get("slug") or "Lugar",
                        "category": row.get("category"),
                        "region": row.get("region"),
                        "country": row.get("country"),
                        "thumbnail_url": row.get("thumbnail_url"),
                        "latitude": lat,
                        "longitude": lng,
                    }
                )

    suggestions.sort(
        key=lambda s: (
            _sort_key(s.get("name"), s.get("slug"), term),
            (s.get("name") or "").lower(),
            s.get("type"),
        )
    )
    return jsonify({"suggestions": suggestions[:limit]}), 200

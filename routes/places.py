"""
Lugares turísticos (lectura pública para la app, gestión admin).
"""
import json
import uuid

import asyncpg
from quart import Blueprint, jsonify, request
from db import get_conn
from routes.trails import require_admin, generate_slug
from utils.validators import validate_required_fields

places_bp = Blueprint("places", __name__)


VALID_CATEGORIES = {"categoria_1", "categoria_2", "categoria_3"}


def _parse_location(raw):
    """Parsea el campo location (jsonb) a {latitude, longitude}."""
    if raw is None:
        return None, None
    data = raw
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", errors="ignore")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None, None
    if not isinstance(data, dict):
        return None, None
    lat = data.get("latitude", data.get("lat"))
    lng = data.get("longitude", data.get("lng", data.get("lon")))
    try:
        lat_f = float(lat) if lat is not None else None
    except (TypeError, ValueError):
        lat_f = None
    try:
        lng_f = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lng_f = None
    return lat_f, lng_f


@places_bp.route("/places", methods=["GET"])
async def list_places():
    """
    Listar lugares turísticos.

    Query params:
    - category: filtrar por categoría
    - region: filtrar por región
    - country: filtrar por país (default: no filtra)
    - limit: límite de resultados (default: 20)
    - offset: offset para paginación (default: 0)
    """
    category = request.args.get("category")
    region = request.args.get("region")
    country = request.args.get("country")
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)

    conditions = []
    params: list = []
    param_count = 0

    if category:
        param_count += 1
        conditions.append(f"p.category = ${param_count}")
        params.append(category)

    if region:
        param_count += 1
        conditions.append(f"p.region = ${param_count}")
        params.append(region)

    if country:
        param_count += 1
        conditions.append(f"p.country = ${param_count}")
        params.append(country)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    param_count += 1
    limit_param = param_count
    params.append(limit)
    param_count += 1
    offset_param = param_count
    params.append(offset)

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                    p.id, p.slug, p.name, p.category, p.region, p.country,
                    p.description, p.is_premium,
                    p.location::text AS location,
                    p.created_at, p.updated_at,
                    (SELECT url FROM place_media
                        WHERE place_id = p.id
                        AND media_type IN ('image', 'photo_360', 'photo_180')
                        ORDER BY order_index ASC, created_at ASC
                        LIMIT 1) AS thumbnail_url
                FROM tourist_places p
                {where_clause}
                ORDER BY p.created_at DESC
                LIMIT ${limit_param} OFFSET ${offset_param}
                """,
                *params,
            )

            count_params = params[: param_count - 2]
            count_query = f"SELECT COUNT(*) FROM tourist_places p {where_clause}"
            total = (
                await conn.fetchval(count_query, *count_params)
                if count_params
                else await conn.fetchval(count_query)
            )
    except asyncpg.exceptions.PostgresError as e:
        if e.sqlstate in ("42P01", "42703"):
            return jsonify({"error": str(e)}), 503
        raise

    places = []
    for row in rows:
        d = dict(row)
        d["id"] = str(d["id"])
        lat, lng = _parse_location(d.pop("location", None))
        d["latitude"] = lat
        d["longitude"] = lng
        for dt_field in ("created_at", "updated_at"):
            if d.get(dt_field):
                d[dt_field] = d[dt_field].isoformat()
        places.append(d)

    return jsonify({
        "places": places,
        "total": total,
        "limit": limit,
        "offset": offset,
    }), 200


@places_bp.route("/places", methods=["POST"])
@require_admin
async def create_place(user_id: str):
    """
    Crear un lugar turístico.

    Body:
    {
        "name": string (requerido),
        "description": string (opcional),
        "slug": string (opcional, se genera a partir de name),
        "category": "categoria_1" | "categoria_2" | "categoria_3" (requerido),
        "region": string (opcional),
        "country": string (opcional, default 'AR'),
        "location": { "latitude": float, "longitude": float } (requerido),
        "is_premium": boolean (opcional)
    }
    """
    data = await request.get_json()
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400

    required_fields = ["name", "category", "location"]
    error = validate_required_fields(data, required_fields)
    if error:
        return jsonify({"error": error}), 400

    name = data["name"]
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name no puede estar vacío"}), 400

    category = data["category"]
    if category not in VALID_CATEGORIES:
        return jsonify({
            "error": f"category debe ser uno de: {', '.join(sorted(VALID_CATEGORIES))}"
        }), 400

    location = data["location"]
    if not isinstance(location, dict) or "latitude" not in location or "longitude" not in location:
        return jsonify({"error": "location debe tener 'latitude' y 'longitude'"}), 400

    latitude = location["latitude"]
    longitude = location["longitude"]
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return jsonify({"error": "latitude y longitude deben ser números"}), 400

    slug = data.get("slug")
    if not slug or not isinstance(slug, str) or not slug.strip():
        slug = generate_slug(name)
    else:
        slug = generate_slug(slug)

    if not slug:
        slug = "lugar"

    description = data.get("description")
    region = data.get("region")
    country = data.get("country") or "AR"
    is_premium = data.get("is_premium", False)

    try:
        async with get_conn() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM tourist_places WHERE slug = $1", slug
            )
            if existing:
                base_slug = slug
                counter = 1
                while True:
                    candidate = f"{base_slug}-{counter}"
                    existing = await conn.fetchrow(
                        "SELECT id FROM tourist_places WHERE slug = $1", candidate
                    )
                    if not existing:
                        slug = candidate
                        break
                    counter += 1

            location_json = json.dumps({
                "latitude": float(latitude),
                "longitude": float(longitude),
            })
            row = await conn.fetchrow(
                """
                INSERT INTO tourist_places
                    (slug, name, category, region, country, description, is_premium, location)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                RETURNING
                    id, slug, name, category, region, country, description, is_premium,
                    location::text AS location,
                    created_at, updated_at
                """,
                slug,
                name.strip(),
                category,
                region,
                country,
                description,
                bool(is_premium),
                location_json,
            )
    except asyncpg.exceptions.PostgresError as e:
        if e.sqlstate in ("42P01", "42703"):
            return jsonify({"error": str(e)}), 503
        if e.sqlstate == "23505":
            return jsonify({"error": f"El slug '{slug}' ya está en uso"}), 400
        raise

    if not row:
        return jsonify({"error": "Error al crear el lugar"}), 500

    place = dict(row)
    place["id"] = str(place["id"])
    lat, lng = _parse_location(place.pop("location", None))
    place["latitude"] = lat
    place["longitude"] = lng
    for dt_field in ("created_at", "updated_at"):
        if place.get(dt_field):
            place[dt_field] = place[dt_field].isoformat()

    return jsonify({
        "message": "Lugar creado exitosamente",
        "place": place,
    }), 201


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
                    p.location::text AS location,
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
            return jsonify({"error": str(e)}), 503
        raise

    if not row:
        return jsonify({"error": e.message}), 404

    d = dict(row)
    d["id"] = str(d["id"])
    lat, lng = _parse_location(d.pop("location", None))
    d["latitude"] = lat
    d["longitude"] = lng
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

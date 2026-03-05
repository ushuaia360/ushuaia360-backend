"""
Trails routes - Creación y gestión de senderos y sus rutas
"""
from quart import Blueprint, request, jsonify, current_app
from functools import wraps
from db import get_conn
from routes.auth import decode_jwt_token
from models.trail import Trail, TrailRoute, RouteSegment, TrailPoint
from models.media import TrailMedia
from utils.validators import validate_required_fields
from decimal import Decimal
import uuid
import re

trails_bp = Blueprint("trails", __name__)


def require_auth(f):
    """Decorador para proteger rutas que requieren autenticación"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
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
            # Agregar user_id al contexto de kwargs para que esté disponible en la función
            kwargs['user_id'] = user_id
        except ValueError as e:
            return jsonify({"error": str(e)}), 401
        
        return await f(*args, **kwargs)
    
    return decorated_function


def require_admin(f):
    """Decorador para proteger rutas que requieren autenticación de admin"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
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
        
        # Verificar que el usuario es admin
        async with get_conn() as conn:
            user = await conn.fetchrow("SELECT is_admin FROM users WHERE id = $1", user_id)
            if not user or not user["is_admin"]:
                return jsonify({"error": "No autorizado. Se requiere permisos de administrador"}), 403
        
        # Agregar user_id al contexto de kwargs para que esté disponible en la función
        kwargs['user_id'] = user_id
        
        return await f(*args, **kwargs)
    
    return decorated_function


def generate_slug(name: str) -> str:
    """Genera un slug único a partir de un nombre"""
    # Convertir a minúsculas y reemplazar espacios y caracteres especiales
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)  # Remover guiones al inicio y final
    return slug


@trails_bp.route("/trails", methods=["POST"])
@require_admin
async def create_trail(user_id: str):
    """
    Crear un nuevo trail (sendero)
    
    Body:
    {
        "difficulty": "easy" | "medium" | "hard",
        "route_type": "circular" | "lineal" | "ida_vuelta",
        "region": string,
        "distance_km": decimal,
        "elevation_gain": int,
        "elevation_loss": int,
        "max_altitude": int,
        "min_altitude": int,
        "duration_minutes": int,
        "map_point": {
            "longitude": float,
            "latitude": float
        },
        "is_featured": boolean (opcional),
        "is_premium": boolean (opcional),
        "status_id": int (opcional),
        "slug": string (opcional, se genera automáticamente si no se proporciona)
    }
    """
    data = await request.get_json()
    
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar campos requeridos
    required_fields = ["difficulty", "route_type"]
    error = validate_required_fields(data, required_fields)
    if error:
        return jsonify({"error": error}), 400
    
    # Validar difficulty
    if data["difficulty"] not in ["easy", "medium", "hard"]:
        return jsonify({"error": "difficulty debe ser 'easy', 'medium' o 'hard'"}), 400
    
    # Validar route_type
    if data["route_type"] not in ["circular", "lineal", "ida_vuelta"]:
        return jsonify({"error": "route_type debe ser 'circular', 'lineal' o 'ida_vuelta'"}), 400
    
    # Validar map_point si se proporciona
    map_point_coords = None
    if data.get("map_point"):
        map_point = data["map_point"]
        if not isinstance(map_point, dict) or "longitude" not in map_point or "latitude" not in map_point:
            return jsonify({"error": "map_point debe tener 'longitude' y 'latitude'"}), 400
        
        longitude = map_point["longitude"]
        latitude = map_point["latitude"]
        
        if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
            return jsonify({"error": "longitude y latitude deben ser números"}), 400
        
        map_point_coords = (longitude, latitude)
    
    # Generar slug si no se proporciona
    slug = data.get("slug")
    if not slug:
        # Usar region o un valor por defecto para generar el slug
        slug_base = data.get("region", "trail")
        slug = generate_slug(slug_base)
        # Asegurar que el slug sea único agregando un sufijo si es necesario
        async with get_conn() as conn:
            existing = await conn.fetchrow("SELECT id FROM trails WHERE slug = $1", slug)
            if existing:
                counter = 1
                while existing:
                    new_slug = f"{slug}-{counter}"
                    existing = await conn.fetchrow("SELECT id FROM trails WHERE slug = $1", new_slug)
                    if not existing:
                        slug = new_slug
                        break
                    counter += 1
    
    async with get_conn() as conn:
        # Verificar que el slug sea único
        existing = await conn.fetchrow("SELECT id FROM trails WHERE slug = $1", slug)
        if existing:
            return jsonify({"error": f"El slug '{slug}' ya está en uso"}), 400
        
        # Construir la query SQL
        fields = ["slug", "difficulty", "route_type", "created_by"]
        values = [slug, data["difficulty"], data["route_type"], uuid.UUID(user_id)]
        placeholders = ["$1", "$2", "$3", "$4"]
        param_count = 4
        
        # Agregar campos opcionales
        optional_fields = {
            "region": "region",
            "distance_km": "distance_km",
            "elevation_gain": "elevation_gain",
            "elevation_loss": "elevation_loss",
            "max_altitude": "max_altitude",
            "min_altitude": "min_altitude",
            "duration_minutes": "duration_minutes",
            "is_featured": "is_featured",
            "is_premium": "is_premium",
            "status_id": "status_id"
        }
        
        for key, db_field in optional_fields.items():
            if key in data and data[key] is not None:
                param_count += 1
                fields.append(db_field)
                values.append(data[key])
                placeholders.append(f"${param_count}")
        
        # Agregar map_point si existe
        if map_point_coords:
            param_count += 1
            fields.append("map_point")
            placeholders.append(f"ST_SetSRID(ST_MakePoint(${param_count}, ${param_count + 1}), 4326)")
            values.extend(map_point_coords)
            param_count += 1
        
        # Construir y ejecutar la query
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO trails ({fields_str})
            VALUES ({placeholders_str})
            RETURNING *
        """
        
        trail = await conn.fetchrow(query, *values)
        
        if not trail:
            return jsonify({"error": "Error al crear el trail"}), 500
        
        # Convertir a modelo
        trail_model = Trail.from_row(trail)
        
        return jsonify({
            "message": "Trail creado exitosamente",
            "trail": trail_model.to_dict()
        }), 201


@trails_bp.route("/trails/<trail_id>/routes", methods=["POST"])
@require_admin
async def create_trail_route(trail_id: str, user_id: str):
    """
    Crear una nueva ruta para un trail
    
    Body:
    {
        "version": int (opcional, default: 1),
        "is_active": boolean (opcional, default: true),
        "total_distance_km": decimal (opcional),
        "elevation_gain": int (opcional),
        "elevation_loss": int (opcional)
    }
    """
    data = await request.get_json() or {}
    
    # Validar que el trail existe
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400
    
    async with get_conn() as conn:
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Si is_active es true, desactivar otras rutas activas del mismo trail
        is_active = data.get("is_active", True)
        if is_active:
            await conn.execute(
                "UPDATE trail_routes SET is_active = false WHERE trail_id = $1",
                trail_uuid
            )
        
        # Obtener la siguiente versión si no se proporciona
        version = data.get("version")
        if not version:
            max_version = await conn.fetchval(
                "SELECT COALESCE(MAX(version), 0) FROM trail_routes WHERE trail_id = $1",
                trail_uuid
            )
            version = max_version + 1
        
        # Construir la query
        fields = ["trail_id", "version", "is_active"]
        values = [trail_uuid, version, is_active]
        placeholders = ["$1", "$2", "$3"]
        param_count = 3
        
        optional_fields = {
            "total_distance_km": "total_distance_km",
            "elevation_gain": "elevation_gain",
            "elevation_loss": "elevation_loss"
        }
        
        for key, db_field in optional_fields.items():
            if key in data and data[key] is not None:
                param_count += 1
                fields.append(db_field)
                values.append(data[key])
                placeholders.append(f"${param_count}")
        
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO trail_routes ({fields_str})
            VALUES ({placeholders_str})
            RETURNING *
        """
        
        route = await conn.fetchrow(query, *values)
        
        if not route:
            return jsonify({"error": "Error al crear la ruta"}), 500
        
        route_model = TrailRoute.from_row(route)
        
        return jsonify({
            "message": "Ruta creada exitosamente",
            "route": route_model.to_dict()
        }), 201


@trails_bp.route("/trails/<trail_id>/routes/<route_id>/segments", methods=["POST"])
@require_admin
async def create_route_segment(trail_id: str, route_id: str, user_id: str):
    """
    Crear un segmento de ruta
    
    Body:
    {
        "path": [
            [longitude, latitude, elevation],  // Array de puntos [lon, lat, elevation]
            ...
        ],
        "segment_order": int,
        "distance_km": decimal (opcional)
    }
    """
    data = await request.get_json()
    
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar campos requeridos
    required_fields = ["path", "segment_order"]
    error = validate_required_fields(data, required_fields)
    if error:
        return jsonify({"error": error}), 400
    
    # Validar que path es un array de puntos
    path = data["path"]
    if not isinstance(path, list) or len(path) < 2:
        return jsonify({"error": "path debe ser un array con al menos 2 puntos"}), 400
    
    # Validar cada punto
    for i, point in enumerate(path):
        if not isinstance(point, list) or len(point) < 2:
            return jsonify({"error": f"El punto {i} debe ser un array [longitude, latitude] o [longitude, latitude, elevation]"}), 400
        
        if len(point) == 2:
            lon, lat = point
            elevation = 0  # Default elevation
        else:
            lon, lat, elevation = point[0], point[1], point[2]
        
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            return jsonify({"error": f"El punto {i} tiene coordenadas inválidas"}), 400
        
        if not isinstance(elevation, (int, float)):
            elevation = 0
    
    # Validar IDs
    try:
        trail_uuid = uuid.UUID(trail_id)
        route_uuid = uuid.UUID(route_id)
    except ValueError:
        return jsonify({"error": "ID de trail o ruta inválido"}), 400
    
    async with get_conn() as conn:
        # Validar que el trail existe
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Validar que la ruta existe y pertenece al trail
        route = await conn.fetchrow(
            "SELECT id FROM trail_routes WHERE id = $1 AND trail_id = $2",
            route_uuid, trail_uuid
        )
        if not route:
            return jsonify({"error": "Ruta no encontrada o no pertenece al trail"}), 404
        
        # Construir el LineStringZ para PostGIS usando WKT
        # Formato WKT: LINESTRINGZ(lon lat elevation, lon lat elevation, ...)
        points_wkt = []
        for point in path:
            if len(point) == 2:
                lon, lat = point
                elevation = 0
            else:
                lon, lat, elevation = point[0], point[1], point[2]
            points_wkt.append(f"{lon} {lat} {elevation}")
        
        wkt_string = f"LINESTRINGZ({', '.join(points_wkt)})"
        
        # Construir la query usando ST_GeomFromText con parámetro
        fields = ["route_id", "path", "segment_order"]
        placeholders = ["$1", "ST_SetSRID(ST_GeomFromText($2, 4326), 4326)::geography", "$3"]
        values = [route_uuid, wkt_string, data["segment_order"]]
        param_count = 3
        
        if "distance_km" in data and data["distance_km"] is not None:
            param_count += 1
            fields.append("distance_km")
            placeholders.append(f"${param_count}")
            values.append(data["distance_km"])
        
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO route_segments ({fields_str})
            VALUES ({placeholders_str})
            RETURNING *
        """
        
        segment = await conn.fetchrow(query, *values)
        
        if not segment:
            return jsonify({"error": "Error al crear el segmento"}), 500
        
        segment_model = RouteSegment.from_row(segment)
        
        return jsonify({
            "message": "Segmento creado exitosamente",
            "segment": segment_model.to_dict()
        }), 201


@trails_bp.route("/trails/<trail_id>/points", methods=["POST"])
@require_admin
async def create_trail_point(trail_id: str, user_id: str):
    """
    Crear un trail_point (punto de interés en el sendero)
    
    Body:
    {
        "name": string (opcional),
        "description": string (opcional),
        "type": "mirador" | "peligro" | "agua" | "descanso" (opcional),
        "location": {
            "longitude": float,
            "latitude": float,
            "elevation": float (opcional, default: 0)
        } (opcional),
        "km_marker": decimal (opcional),
        "order_index": int (opcional)
    }
    """
    data = await request.get_json() or {}
    
    # Validar tipo si se proporciona
    if data.get("type"):
        valid_types = ["mirador", "peligro", "agua", "descanso"]
        if data["type"] not in valid_types:
            return jsonify({"error": f"type debe ser uno de: {', '.join(valid_types)}"}), 400
    
    # Validar location si se proporciona
    location_coords = None
    if data.get("location"):
        location = data["location"]
        if not isinstance(location, dict) or "longitude" not in location or "latitude" not in location:
            return jsonify({"error": "location debe tener 'longitude' y 'latitude'"}), 400
        
        longitude = location["longitude"]
        latitude = location["latitude"]
        elevation = location.get("elevation", 0)
        
        if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
            return jsonify({"error": "longitude y latitude deben ser números"}), 400
        
        if not isinstance(elevation, (int, float)):
            elevation = 0
        
        location_coords = (longitude, latitude, elevation)
    
    # Validar ID
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400
    
    async with get_conn() as conn:
        # Validar que el trail existe
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Construir la query
        fields = ["trail_id"]
        values = [trail_uuid]
        placeholders = ["$1"]
        param_count = 1
        
        optional_fields = {
            "name": "name",
            "description": "description",
            "type": "type",
            "km_marker": "km_marker",
            "order_index": "order_index"
        }
        
        for key, db_field in optional_fields.items():
            if key in data and data[key] is not None:
                param_count += 1
                fields.append(db_field)
                values.append(data[key])
                placeholders.append(f"${param_count}")
        
        # Agregar location si existe
        if location_coords:
            param_count += 1
            fields.append("location")
            placeholders.append(f"ST_SetSRID(ST_MakePoint(${param_count}, ${param_count + 1}, ${param_count + 2}), 4326)::geography")
            values.extend(location_coords)
            param_count += 2
        
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO trail_points ({fields_str})
            VALUES ({placeholders_str})
            RETURNING *
        """
        
        point = await conn.fetchrow(query, *values)
        
        if not point:
            return jsonify({"error": "Error al crear el trail point"}), 500
        
        point_model = TrailPoint.from_row(point)
        
        return jsonify({
            "message": "Trail point creado exitosamente",
            "point": point_model.to_dict()
        }), 201


@trails_bp.route("/trails/<trail_id>/media", methods=["POST"])
@require_admin
async def create_trail_media(trail_id: str, user_id: str):
    """
    Crear media asociada a un trail
    
    Body:
    {
        "media_type": "image" | "photo_360" | "photo_180" | "video",
        "url": string (requerido),
        "thumbnail_url": string (opcional),
        "order_index": int (opcional)
    }
    """
    data = await request.get_json()
    
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar campos requeridos
    required_fields = ["media_type", "url"]
    error = validate_required_fields(data, required_fields)
    if error:
        return jsonify({"error": error}), 400
    
    # Validar media_type
    valid_types = ["image", "photo_360", "photo_180", "video"]
    if data["media_type"] not in valid_types:
        return jsonify({"error": f"media_type debe ser uno de: {', '.join(valid_types)}"}), 400
    
    # Validar ID
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400
    
    async with get_conn() as conn:
        # Validar que el trail existe
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Construir la query
        fields = ["trail_id", "media_type", "url"]
        values = [trail_uuid, data["media_type"], data["url"]]
        placeholders = ["$1", "$2", "$3"]
        param_count = 3
        
        optional_fields = {
            "thumbnail_url": "thumbnail_url",
            "order_index": "order_index"
        }
        
        for key, db_field in optional_fields.items():
            if key in data and data[key] is not None:
                param_count += 1
                fields.append(db_field)
                values.append(data[key])
                placeholders.append(f"${param_count}")
        
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO trail_media ({fields_str})
            VALUES ({placeholders_str})
            RETURNING *
        """
        
        media = await conn.fetchrow(query, *values)
        
        if not media:
            return jsonify({"error": "Error al crear el media"}), 500
        
        media_model = TrailMedia.from_row(media)
        
        return jsonify({
            "message": "Media creado exitosamente",
            "media": media_model.to_dict()
        }), 201


@trails_bp.route("/trails/<trail_id>/points/<point_id>/media", methods=["POST"])
@require_admin
async def create_trail_point_media(trail_id: str, point_id: str, user_id: str):
    """
    Crear media asociada a un trail_point
    
    Body:
    {
        "media_type": "image" | "photo_360" | "photo_180" | "video",
        "url": string (requerido),
        "thumbnail_url": string (opcional),
        "order_index": int (opcional)
    }
    """
    data = await request.get_json()
    
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar campos requeridos
    required_fields = ["media_type", "url"]
    error = validate_required_fields(data, required_fields)
    if error:
        return jsonify({"error": error}), 400
    
    # Validar media_type
    valid_types = ["image", "photo_360", "photo_180", "video"]
    if data["media_type"] not in valid_types:
        return jsonify({"error": f"media_type debe ser uno de: {', '.join(valid_types)}"}), 400
    
    # Validar IDs
    try:
        trail_uuid = uuid.UUID(trail_id)
        point_uuid = uuid.UUID(point_id)
    except ValueError:
        return jsonify({"error": "ID de trail o point inválido"}), 400
    
    async with get_conn() as conn:
        # Validar que el trail existe
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Validar que el trail_point existe y pertenece al trail
        point = await conn.fetchrow(
            "SELECT id FROM trail_points WHERE id = $1 AND trail_id = $2",
            point_uuid, trail_uuid
        )
        if not point:
            return jsonify({"error": "Trail point no encontrado o no pertenece al trail"}), 404
        
        # Construir la query
        fields = ["trail_point_id", "media_type", "url"]
        values = [point_uuid, data["media_type"], data["url"]]
        placeholders = ["$1", "$2", "$3"]
        param_count = 3
        
        optional_fields = {
            "thumbnail_url": "thumbnail_url",
            "order_index": "order_index"
        }
        
        for key, db_field in optional_fields.items():
            if key in data and data[key] is not None:
                param_count += 1
                fields.append(db_field)
                values.append(data[key])
                placeholders.append(f"${param_count}")
        
        fields_str = ", ".join(fields)
        placeholders_str = ", ".join(placeholders)
        
        query = f"""
            INSERT INTO trail_media ({fields_str})
            VALUES ({placeholders_str})
            RETURNING *
        """
        
        media = await conn.fetchrow(query, *values)
        
        if not media:
            return jsonify({"error": "Error al crear el media"}), 500
        
        media_model = TrailMedia.from_row(media)
        
        return jsonify({
            "message": "Media creado exitosamente",
            "media": media_model.to_dict()
        }), 201

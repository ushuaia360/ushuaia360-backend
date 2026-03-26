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
import json

trails_bp = Blueprint("trails", __name__)


def _normalize_route_segment_path(path_raw):
    """
    Convierte path de route_segments (jsonb, GeoJSON, string JSON) en [[a,b], ...].
    El cliente decide si el par es [lat,lng] o [lng,lat].
    """
    if path_raw is None:
        return []
    data = path_raw
    if isinstance(data, memoryview):
        data = data.tobytes().decode("utf-8", errors="ignore")
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", errors="ignore")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        if data.get("type") == "LineString" and isinstance(data.get("coordinates"), list):
            # GeoJSON positions son [lng, lat]; unificamos a [lat, lng] como el resto del API / Leaflet admin
            out = []
            for item in data["coordinates"]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    try:
                        lng = float(item[0])
                        lat = float(item[1])
                    except (TypeError, ValueError):
                        continue
                    out.append([lat, lng])
            return out
        else:
            return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                a = float(item[0])
                b = float(item[1])
            except (TypeError, ValueError):
                continue
            out.append([a, b])
        elif isinstance(item, dict):
            lat = item.get("latitude", item.get("lat"))
            lon = item.get("longitude", item.get("lng", item.get("lon")))
            if lat is not None and lon is not None:
                try:
                    out.append([float(lat), float(lon)])
                except (TypeError, ValueError):
                    pass
    return out


def _normalize_trail_point_location(location_raw):
    """Unifica location a {latitude, longitude, elevation?} para JSON de detalle."""
    if location_raw is None:
        return None
    data = location_raw
    if isinstance(data, memoryview):
        data = data.tobytes().decode("utf-8", errors="ignore")
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", errors="ignore")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            m = re.search(r"POINTZ?\s*\(\s*([-\d.]+)\s+([-\d.]+)", data, re.I)
            if m:
                try:
                    lon, lat = float(m.group(1)), float(m.group(2))
                    return {"latitude": lat, "longitude": lon, "elevation": 0}
                except ValueError:
                    return None
            return None
    if not isinstance(data, dict):
        return None
    if "latitude" in data and "longitude" in data:
        try:
            return {
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "elevation": float(data.get("elevation", 0)),
            }
        except (TypeError, ValueError):
            return None
    if data.get("type") == "Point" and isinstance(data.get("coordinates"), list):
        c = data["coordinates"]
        if len(c) >= 2:
            try:
                return {
                    "longitude": float(c[0]),
                    "latitude": float(c[1]),
                    "elevation": float(c[2]) if len(c) > 2 else 0,
                }
            except (TypeError, ValueError):
                return None
    return None


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


@trails_bp.route("/trails", methods=["GET"])
# @require_auth  # Comentado temporalmente - descomentar cuando se necesite autenticación
async def list_trails(user_id: str = None):  # user_id es opcional cuando no se requiere auth
    """
    Listar todos los trails (senderos)
    
    Query params:
    - difficulty: filtrar por dificultad (easy, medium, hard)
    - status_id: filtrar por estado
    - is_featured: filtrar por destacados (true/false)
    - limit: límite de resultados (default: 20)
    - offset: offset para paginación (default: 0)
    """
    import json as _json

    difficulty = request.args.get("difficulty")
    status_id = request.args.get("status_id", type=int)
    is_featured_str = request.args.get("is_featured")
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)

    is_featured = None
    if is_featured_str is not None:
        is_featured = is_featured_str.lower() in ("true", "1", "yes")
    
    async with get_conn() as conn:
        # Construir la query con filtros
        conditions = []
        params = []
        param_count = 0
        
        if difficulty:
            param_count += 1
            conditions.append(f"t.difficulty = ${param_count}")
            params.append(difficulty)
        
        if status_id is not None:
            param_count += 1
            conditions.append(f"t.status_id = ${param_count}")
            params.append(status_id)

        if is_featured is not None:
            param_count += 1
            conditions.append(f"t.is_featured = ${param_count}")
            params.append(is_featured)
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        # Agregar limit y offset
        param_count += 1
        limit_param = param_count
        params.append(limit)
        param_count += 1
        offset_param = param_count
        params.append(offset)
        
        query = f"""
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
            {where_clause}
            ORDER BY t.created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """
        
        trails = await conn.fetch(query, *params)
        
        # Obtener el total para paginación (sin limit y offset)
        count_filter_params = params[:param_count - 2]
        count_query = f"SELECT COUNT(*) FROM trails t {where_clause}"
        total = await conn.fetchval(count_query, *count_filter_params) if count_filter_params else await conn.fetchval(count_query)
        
        # Serializar manualmente para incluir map_point y arrays
        trails_list = []
        for row in trails:
            trail_dict = dict(row)
            # Convertir UUIDs y Decimals
            if trail_dict.get('id'):
                trail_dict['id'] = str(trail_dict['id'])
            if trail_dict.get('created_by'):
                trail_dict['created_by'] = str(trail_dict['created_by'])
            if isinstance(trail_dict.get('distance_km'), Decimal):
                trail_dict['distance_km'] = float(trail_dict['distance_km'])
            # Parsear map_point JSON
            if trail_dict.get('map_point'):
                try:
                    trail_dict['map_point'] = _json.loads(trail_dict['map_point'])
                except Exception:
                    trail_dict['map_point'] = None
            else:
                trail_dict['map_point'] = None
            # Convertir datetimes
            for dt_field in ('created_at', 'updated_at'):
                if trail_dict.get(dt_field):
                    trail_dict[dt_field] = trail_dict[dt_field].isoformat()
            # image_urls puede ser una lista de asyncpg
            if trail_dict.get('image_urls') is None:
                trail_dict['image_urls'] = []
            else:
                trail_dict['image_urls'] = list(trail_dict['image_urls'])
            trails_list.append(trail_dict)
        
        return jsonify({
            "trails": trails_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }), 200


@trails_bp.route("/trails", methods=["POST"])
@require_admin
async def create_trail(user_id: str):
    """
    Crear un nuevo trail (sendero)
    
    Body:
    {
        "difficulty": "easy" | "medium" | "hard",
        "route_type": "circular" | "lineal" | "ida_vuelta",
        "description": string (opcional),
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
        fields = ["slug", "difficulty", "route_type"]
        values = [slug, data["difficulty"], data["route_type"]]
        placeholders = ["$1", "$2", "$3"]
        param_count = 3
        
        # Agregar created_by solo si user_id está disponible
        # if user_id:
        #     param_count += 1
        #     fields.append("created_by")
        #     values.append(uuid.UUID(user_id))
        #     placeholders.append(f"${param_count}")
        
        # Agregar campos opcionales
        optional_fields = {
            "name": "name",
            "description": "description",
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
        
        # Agregar map_point si existe (guardar como JSON en lugar de geography)
        if map_point_coords:
            param_count += 1
            fields.append("map_point")
            # Guardar como JSON: {"latitude": lat, "longitude": lon}
            import json
            map_point_json = json.dumps({
                "latitude": map_point_coords[1],
                "longitude": map_point_coords[0]
            })
            placeholders.append(f"${param_count}::jsonb")
            values.append(map_point_json)
        
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


@trails_bp.route("/trails/<trail_id>", methods=["GET"])
# @require_auth  # Comentado temporalmente - descomentar cuando se necesite autenticación
async def get_trail(trail_id: str, user_id: str = None):
    """
    Obtener un trail específico por ID
    """
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400
    
    async with get_conn() as conn:
        # Obtener trail con map_point como JSON
        trail = await conn.fetchrow("""
            SELECT 
                t.id, t.slug, t.name, t.difficulty, t.route_type, t.region,
                t.distance_km, t.elevation_gain, t.elevation_loss, t.max_altitude, t.min_altitude,
                t.duration_minutes, t.is_featured, t.is_premium, t.status_id, t.created_by,
                t.created_at, t.updated_at, t.description,
                t.map_point::text AS map_point,
                ARRAY(SELECT url FROM trail_media
                    WHERE trail_id = t.id
                    AND media_type IN ('image', 'photo_360', 'photo_180')
                    ORDER BY order_index ASC, created_at ASC) AS image_urls
            FROM trails t
            WHERE t.id = $1
        """, trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        trail_model = Trail.from_row(trail)
        trail_dict = trail_model.to_dict()
        
        # Convertir map_point de JSON si existe
        if trail_dict.get('map_point'):
            map_point_data = trail_dict['map_point']
            if isinstance(map_point_data, str):
                try:
                    map_point_data = json.loads(map_point_data)
                except json.JSONDecodeError:
                    map_point_data = None
            if isinstance(map_point_data, dict):
                trail_dict['map_point'] = map_point_data
            else:
                trail_dict['map_point'] = None
        else:
            trail_dict['map_point'] = None

        if trail_dict.get('image_urls') is None:
            trail_dict['image_urls'] = []
        else:
            trail_dict['image_urls'] = list(trail_dict['image_urls'])
        
        # Obtener rutas activas y sus segmentos
        routes_query = """
            SELECT id, trail_id, version, is_active, total_distance_km, 
                   elevation_gain, elevation_loss, created_at
            FROM trail_routes 
            WHERE trail_id = $1 AND is_active = true
            ORDER BY version DESC
            LIMIT 1
        """
        route = await conn.fetchrow(routes_query, trail_uuid)
        trail_dict['route'] = None
        trail_dict['route_segments'] = []
        
        if route:
            route_id = route['id']
            route_dict = {
                'id': str(route['id']),
                'trail_id': str(route['trail_id']),
                'version': route['version'],
                'is_active': route['is_active'],
                'total_distance_km': float(route['total_distance_km']) if route.get('total_distance_km') else None,
                'elevation_gain': route.get('elevation_gain'),
                'elevation_loss': route.get('elevation_loss'),
            }
            trail_dict['route'] = route_dict
            
            # Obtener segmentos de la ruta (path ahora es JSON)
            segments_query = """
                SELECT 
                    id, route_id, segment_order, distance_km,
                    path
                FROM route_segments 
                WHERE route_id = $1
                ORDER BY segment_order ASC
            """
            segments = await conn.fetch(segments_query, route_id)
            
            for segment in segments:
                segment_dict = dict(segment)
                path_coords = _normalize_route_segment_path(segment_dict.get('path'))
                segment_dict['path'] = path_coords
                segment_dict['id'] = str(segment_dict['id'])
                segment_dict['route_id'] = str(segment_dict['route_id'])
                if isinstance(segment_dict.get('distance_km'), Decimal):
                    segment_dict['distance_km'] = float(segment_dict['distance_km'])
                trail_dict['route_segments'].append(segment_dict)
        
        # Obtener media del sendero
        trail_media_rows = await conn.fetch("""
            SELECT id, trail_id, trail_point_id, media_type, url, thumbnail_url, order_index, created_at
            FROM trail_media
            WHERE trail_id = $1 AND trail_point_id IS NULL
            ORDER BY order_index ASC NULLS LAST, created_at ASC
        """, trail_uuid)
        trail_dict['media'] = []
        for row in trail_media_rows:
            m = dict(row)
            if m.get('id'): m['id'] = str(m['id'])
            if m.get('trail_id'): m['trail_id'] = str(m['trail_id'])
            if m.get('created_at'): m['created_at'] = m['created_at'].isoformat()
            trail_dict['media'].append(m)

        # Obtener puntos de interés (location ahora es JSON)
        points_query = """
            SELECT 
                id, trail_id, name, description, type, 
                km_marker, order_index,
                location
            FROM trail_points 
            WHERE trail_id = $1
            ORDER BY order_index ASC
        """
        points = await conn.fetch(points_query, trail_uuid)
        trail_dict['points'] = []
        for point in points:
            point_dict = dict(point)
            location_obj = _normalize_trail_point_location(point_dict.get('location'))
            point_dict['location'] = location_obj
            # Convertir UUIDs y Decimal
            if point_dict.get('id'):
                point_dict['id'] = str(point_dict['id'])
            if point_dict.get('trail_id'):
                point_dict['trail_id'] = str(point_dict['trail_id'])
            if isinstance(point_dict.get('km_marker'), Decimal):
                point_dict['km_marker'] = float(point_dict['km_marker'])

            # Obtener media del punto
            point_uuid_val = uuid.UUID(point_dict['id'])
            point_media_rows = await conn.fetch("""
                SELECT id, trail_point_id, media_type, url, thumbnail_url, order_index, created_at
                FROM trail_media
                WHERE trail_point_id = $1
                ORDER BY order_index ASC NULLS LAST, created_at ASC
            """, point_uuid_val)
            point_dict['media'] = []
            for pm in point_media_rows:
                pm_dict = dict(pm)
                if pm_dict.get('id'): pm_dict['id'] = str(pm_dict['id'])
                if pm_dict.get('trail_point_id'): pm_dict['trail_point_id'] = str(pm_dict['trail_point_id'])
                if pm_dict.get('created_at'): pm_dict['created_at'] = pm_dict['created_at'].isoformat()
                point_dict['media'].append(pm_dict)

            trail_dict['points'].append(point_dict)
        
        return jsonify({
            "trail": trail_dict
        }), 200


@trails_bp.route("/trails/<trail_id>", methods=["PUT", "PATCH"])
@require_admin
async def update_trail(trail_id: str, user_id: str):
    """
    Actualizar un trail existente
    
    Body: Mismos campos que en POST, pero todos opcionales excepto los requeridos
    """
    data = await request.get_json()
    
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400
    
    # Validar ID
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400
    
    async with get_conn() as conn:
        # Verificar que el trail existe
        existing_trail = await conn.fetchrow("SELECT * FROM trails WHERE id = $1", trail_uuid)
        if not existing_trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Validar difficulty si se proporciona
        if "difficulty" in data:
            if data["difficulty"] not in ["easy", "medium", "hard"]:
                return jsonify({"error": "difficulty debe ser 'easy', 'medium' o 'hard'"}), 400
        
        # Validar route_type si se proporciona
        if "route_type" in data:
            if data["route_type"] not in ["circular", "lineal", "ida_vuelta"]:
                return jsonify({"error": "route_type debe ser 'circular', 'lineal' o 'ida_vuelta'"}), 400
        
        # Validar map_point si se proporciona (ahora se guarda como JSON)
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
        
        # Construir la query UPDATE
        updates = []
        values = []
        param_count = 0
        
        # Campos que se pueden actualizar
        updatable_fields = {
            "name": "name",
            "difficulty": "difficulty",
            "route_type": "route_type",
            "description": "description",
            "region": "region",
            "distance_km": "distance_km",
            "elevation_gain": "elevation_gain",
            "elevation_loss": "elevation_loss",
            "max_altitude": "max_altitude",
            "min_altitude": "min_altitude",
            "duration_minutes": "duration_minutes",
            "is_featured": "is_featured",
            "is_premium": "is_premium",
            "status_id": "status_id",
            "slug": "slug"
        }
        
        for key, db_field in updatable_fields.items():
            if key in data and data[key] is not None:
                param_count += 1
                updates.append(f"{db_field} = ${param_count}")
                values.append(data[key])
        
        # Agregar map_point si existe (guardar como JSON)
        if map_point_coords:
            param_count += 1
            import json
            map_point_json = json.dumps({
                "latitude": map_point_coords[1],
                "longitude": map_point_coords[0]
            })
            updates.append(f"map_point = ${param_count}::jsonb")
            values.append(map_point_json)
        
        # Agregar updated_at (no necesita parámetro)
        updates.append("updated_at = NOW()")
        
        if not updates:
            return jsonify({"error": "No hay campos para actualizar"}), 400
        
        # Agregar el ID al final para el WHERE
        param_count += 1
        where_param = param_count
        values.append(trail_uuid)
        
        query = f"""
            UPDATE trails
            SET {', '.join(updates)}
            WHERE id = ${where_param}
            RETURNING *
        """
        
        trail = await conn.fetchrow(query, *values)
        
        if not trail:
            return jsonify({"error": "Error al actualizar el trail"}), 500
        
        trail_model = Trail.from_row(trail)
        
        return jsonify({
            "message": "Trail actualizado exitosamente",
            "trail": trail_model.to_dict()
        }), 200


@trails_bp.route("/trails/<trail_id>", methods=["DELETE"])
@require_admin
async def delete_trail(trail_id: str, user_id: str):
    """
    Eliminar un trail
    """
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400
    
    async with get_conn() as conn:
        # Verificar que el trail existe
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404
        
        # Eliminar el trail (las foreign keys deberían manejar las relaciones)
        await conn.execute("DELETE FROM trails WHERE id = $1", trail_uuid)
        
        return jsonify({
            "message": "Trail eliminado exitosamente"
        }), 200


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
    
    # Validar cada punto (ahora viene como [lon, lat] o [lon, lat, elevation])
    for i, point in enumerate(path):
        if not isinstance(point, list) or len(point) < 2:
            return jsonify({"error": f"El punto {i} debe ser un array [longitude, latitude] o [longitude, latitude, elevation]"}), 400
        
        lon, lat = point[0], point[1]
        
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            return jsonify({"error": f"El punto {i} tiene coordenadas inválidas"}), 400
    
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
        
        # Convertir path a JSON (guardar como JSON en lugar de geography)
        # path viene como [[lon, lat, elevation], ...] del frontend
        # Lo guardamos como [[lat, lon], ...] para Leaflet
        import json
        path_json = []
        for point in path:
            if len(point) >= 2:
                lon, lat = point[0], point[1]
                # Guardar como [lat, lon] para Leaflet
                path_json.append([lat, lon])
        
        path_json_str = json.dumps(path_json)
        
        # Construir la query usando JSONB
        fields = ["route_id", "path", "segment_order"]
        placeholders = ["$1", "$2::jsonb", "$3"]
        values = [route_uuid, path_json_str, data["segment_order"]]
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


@trails_bp.route("/trails/<trail_id>/routes/<route_id>/segments", methods=["DELETE"])
@require_admin
async def delete_all_route_segments(trail_id: str, route_id: str, user_id: str):
    """
    Eliminar todos los segmentos de una ruta (p. ej. antes de reemplazar el trazado).
    """
    try:
        trail_uuid = uuid.UUID(trail_id)
        route_uuid = uuid.UUID(route_id)
    except ValueError:
        return jsonify({"error": "ID de trail o ruta inválido"}), 400

    async with get_conn() as conn:
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404

        route = await conn.fetchrow(
            "SELECT id FROM trail_routes WHERE id = $1 AND trail_id = $2",
            route_uuid, trail_uuid
        )
        if not route:
            return jsonify({"error": "Ruta no encontrada o no pertenece al trail"}), 404

        await conn.execute("DELETE FROM route_segments WHERE route_id = $1", route_uuid)

    return jsonify({"message": "Segmentos eliminados exitosamente"}), 200


@trails_bp.route("/trails/<trail_id>/points", methods=["POST"])
@require_admin
async def create_trail_point(trail_id: str, user_id: str):
    """
    Crear un trail_point (punto de interés en el sendero)
    
    Body:
    {
        "name": string (opcional),
        "description": string (opcional),
        "type": "inicio" | "fin" | "mirador" | "peligro" | "agua" | "descanso" | "refugio" | "cruce" | "campamento" | "cascada" | "vista" | "informacion" (opcional),
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
        valid_types = ["inicio", "fin", "mirador", "peligro", "agua", "descanso", "refugio", "cruce", "campamento", "cascada", "vista", "informacion"]
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
        
        # Agregar location si existe (guardar como JSON)
        if location_coords:
            param_count += 1
            fields.append("location")
            import json
            location_json = json.dumps({
                "longitude": location_coords[0],
                "latitude": location_coords[1],
                "elevation": location_coords[2] if len(location_coords) > 2 else 0
            })
            placeholders.append(f"${param_count}::jsonb")
            values.append(location_json)
        
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


@trails_bp.route("/trails/<trail_id>/points/<point_id>", methods=["PUT", "PATCH"])
@require_admin
async def update_trail_point(trail_id: str, point_id: str, user_id: str):
    """
    Actualizar un trail_point existente (mismos campos opcionales que POST).
    """
    data = await request.get_json()
    if not data:
        return jsonify({"error": "Datos requeridos"}), 400

    try:
        trail_uuid = uuid.UUID(trail_id)
        point_uuid = uuid.UUID(point_id)
    except ValueError:
        return jsonify({"error": "ID de trail o point inválido"}), 400

    if data.get("type"):
        valid_types = ["inicio", "fin", "mirador", "peligro", "agua", "descanso", "refugio", "cruce", "campamento", "cascada", "vista", "informacion"]
        if data["type"] not in valid_types:
            return jsonify({"error": f"type debe ser uno de: {', '.join(valid_types)}"}), 400

    location_json = None
    if "location" in data:
        loc = data["location"]
        if loc is None:
            location_json = None
        else:
            if not isinstance(loc, dict) or "longitude" not in loc or "latitude" not in loc:
                return jsonify({"error": "location debe tener 'longitude' y 'latitude'"}), 400
            longitude = loc["longitude"]
            latitude = loc["latitude"]
            elevation = loc.get("elevation", 0)
            if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
                return jsonify({"error": "longitude y latitude deben ser números"}), 400
            if not isinstance(elevation, (int, float)):
                elevation = 0
            location_json = json.dumps({
                "longitude": longitude,
                "latitude": latitude,
                "elevation": elevation,
            })

    async with get_conn() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM trail_points WHERE id = $1 AND trail_id = $2",
            point_uuid, trail_uuid,
        )
        if not existing:
            return jsonify({"error": "Punto no encontrado o no pertenece al trail"}), 404

        updates = []
        values = []
        param_count = 0

        if "name" in data:
            param_count += 1
            updates.append(f"name = ${param_count}")
            values.append(data["name"])
        if "description" in data:
            param_count += 1
            updates.append(f"description = ${param_count}")
            values.append(data["description"])
        if "type" in data:
            param_count += 1
            updates.append(f"type = ${param_count}")
            values.append(data["type"])
        if "km_marker" in data:
            param_count += 1
            updates.append(f"km_marker = ${param_count}")
            values.append(data["km_marker"])
        if "order_index" in data:
            param_count += 1
            updates.append(f"order_index = ${param_count}")
            values.append(data["order_index"])
        if "location" in data:
            if location_json is None:
                updates.append("location = NULL")
            else:
                param_count += 1
                updates.append(f"location = ${param_count}::jsonb")
                values.append(location_json)

        if not updates:
            return jsonify({"error": "No hay campos para actualizar"}), 400

        param_count += 1
        values.append(point_uuid)
        where_param = param_count

        query = f"""
            UPDATE trail_points
            SET {', '.join(updates)}
            WHERE id = ${where_param}
            RETURNING *
        """
        point = await conn.fetchrow(query, *values)

        if not point:
            return jsonify({"error": "Error al actualizar el punto"}), 500

        point_model = TrailPoint.from_row(point)
        return jsonify({
            "message": "Trail point actualizado exitosamente",
            "point": point_model.to_dict(),
        }), 200


@trails_bp.route("/trails/<trail_id>/points/<point_id>", methods=["DELETE"])
@require_admin
async def delete_trail_point(trail_id: str, point_id: str, user_id: str):
    """Eliminar un trail_point y su media asociada."""
    try:
        trail_uuid = uuid.UUID(trail_id)
        point_uuid = uuid.UUID(point_id)
    except ValueError:
        return jsonify({"error": "ID de trail o point inválido"}), 400

    async with get_conn() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM trail_points WHERE id = $1 AND trail_id = $2",
            point_uuid, trail_uuid,
        )
        if not existing:
            return jsonify({"error": "Punto no encontrado o no pertenece al trail"}), 404

        await conn.execute(
            "DELETE FROM trail_media WHERE trail_point_id = $1",
            point_uuid,
        )
        await conn.execute(
            "DELETE FROM trail_points WHERE id = $1 AND trail_id = $2",
            point_uuid, trail_uuid,
        )

    return jsonify({"message": "Punto eliminado exitosamente"}), 200


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


@trails_bp.route("/trails/<trail_id>/media/<media_id>", methods=["DELETE"])
@require_admin
async def delete_trail_media(trail_id: str, media_id: str, user_id: str):
    """Eliminar media del sendero (trail_point_id IS NULL)"""
    try:
        trail_uuid = uuid.UUID(trail_id)
        media_uuid = uuid.UUID(media_id)
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400

    async with get_conn() as conn:
        result = await conn.execute("""
            DELETE FROM trail_media
            WHERE id = $1 AND trail_id = $2 AND trail_point_id IS NULL
        """, media_uuid, trail_uuid)
        if result == "DELETE 0":
            return jsonify({"error": "Media no encontrado o no pertenece al sendero"}), 404
    return jsonify({"message": "Media eliminado"}), 200


@trails_bp.route("/trails/<trail_id>/media", methods=["GET"])
async def get_trail_media(trail_id: str):
    """
    Listar todos los archivos media de un trail.
    
    Query params:
    - media_type: filtrar por tipo (image, photo_360, photo_180, video)
    """
    try:
        trail_uuid = uuid.UUID(trail_id)
    except ValueError:
        return jsonify({"error": "ID de trail inválido"}), 400

    media_type_filter = request.args.get("media_type")

    async with get_conn() as conn:
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404

        conditions = ["trail_id = $1", "trail_point_id IS NULL"]
        params = [trail_uuid]
        if media_type_filter:
            params.append(media_type_filter)
            conditions.append(f"media_type = ${len(params)}")

        where = " AND ".join(conditions)
        rows = await conn.fetch(
            f"""
            SELECT id, trail_id, trail_point_id, media_type, url, thumbnail_url, order_index, created_at
            FROM trail_media
            WHERE {where}
            ORDER BY order_index ASC NULLS LAST, created_at ASC
            """,
            *params,
        )

        media_list = []
        for row in rows:
            m = dict(row)
            if m.get("id"): m["id"] = str(m["id"])
            if m.get("trail_id"): m["trail_id"] = str(m["trail_id"])
            if m.get("created_at"): m["created_at"] = m["created_at"].isoformat()
            media_list.append(m)

        return jsonify({"media": media_list}), 200


@trails_bp.route("/trails/<trail_id>/points/<point_id>/media", methods=["GET"])
async def get_trail_point_media(trail_id: str, point_id: str):
    """
    Listar todos los archivos media de un punto de interés.
    
    Query params:
    - media_type: filtrar por tipo (image, photo_360, photo_180, video)
    """
    try:
        trail_uuid = uuid.UUID(trail_id)
        point_uuid = uuid.UUID(point_id)
    except ValueError:
        return jsonify({"error": "ID de trail o punto inválido"}), 400

    media_type_filter = request.args.get("media_type")

    async with get_conn() as conn:
        trail = await conn.fetchrow("SELECT id FROM trails WHERE id = $1", trail_uuid)
        if not trail:
            return jsonify({"error": "Trail no encontrado"}), 404

        point = await conn.fetchrow(
            "SELECT id FROM trail_points WHERE id = $1 AND trail_id = $2",
            point_uuid, trail_uuid,
        )
        if not point:
            return jsonify({"error": "Punto de interés no encontrado o no pertenece al trail"}), 404

        conditions = ["trail_point_id = $1"]
        params = [point_uuid]
        if media_type_filter:
            params.append(media_type_filter)
            conditions.append(f"media_type = ${len(params)}")

        where = " AND ".join(conditions)
        rows = await conn.fetch(
            f"""
            SELECT id, trail_point_id, media_type, url, thumbnail_url, order_index, created_at
            FROM trail_media
            WHERE {where}
            ORDER BY order_index ASC NULLS LAST, created_at ASC
            """,
            *params,
        )

        media_list = []
        for row in rows:
            m = dict(row)
            if m.get("id"): m["id"] = str(m["id"])
            if m.get("trail_point_id"): m["trail_point_id"] = str(m["trail_point_id"])
            if m.get("created_at"): m["created_at"] = m["created_at"].isoformat()
            media_list.append(m)

        return jsonify({"media": media_list}), 200


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
        
        # Construir la query para point media
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


@trails_bp.route("/trails/<trail_id>/points/<point_id>/media/<media_id>", methods=["DELETE"])
@require_admin
async def delete_trail_point_media(trail_id: str, point_id: str, media_id: str, user_id: str):
    """Eliminar media de un punto de interés"""
    try:
        trail_uuid = uuid.UUID(trail_id)
        point_uuid = uuid.UUID(point_id)
        media_uuid = uuid.UUID(media_id)
    except ValueError:
        return jsonify({"error": "ID inválido"}), 400

    async with get_conn() as conn:
        result = await conn.execute("""
            DELETE FROM trail_media
            WHERE id = $1 AND trail_point_id = $2
            AND EXISTS (SELECT 1 FROM trail_points WHERE id = $2 AND trail_id = $3)
        """, media_uuid, point_uuid, trail_uuid)
        if result == "DELETE 0":
            return jsonify({"error": "Media no encontrado o no pertenece al punto"}), 404
    return jsonify({"message": "Media eliminado"}), 200

"""
Trail models
"""
from models.base import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal


class Trail(BaseModel):
    """Modelo para trails"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.slug = kwargs.get('slug')
        self.description = kwargs.get('description')
        self.difficulty = kwargs.get('difficulty')  # 'easy', 'medium', 'hard'
        self.route_type = kwargs.get('route_type')  # 'circular', 'lineal', 'ida_vuelta'
        self.region = kwargs.get('region')
        self.distance_km = kwargs.get('distance_km')
        self.elevation_gain = kwargs.get('elevation_gain')
        self.elevation_loss = kwargs.get('elevation_loss')
        self.max_altitude = kwargs.get('max_altitude')
        self.min_altitude = kwargs.get('min_altitude')
        self.duration_minutes = kwargs.get('duration_minutes')
        self.map_point = kwargs.get('map_point')  # GEOGRAPHY(Point, 4326)
        self.is_featured = kwargs.get('is_featured', False)
        self.is_premium = kwargs.get('is_premium', False)
        self.status_id = kwargs.get('status_id')
        self.created_by = kwargs.get('created_by')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('created_by'):
            result['created_by'] = str(result['created_by'])
        # Convertir Decimal a float para JSON
        if isinstance(result.get('distance_km'), Decimal):
            result['distance_km'] = float(result['distance_km'])
        # Convertir map_point si es necesario
        if result.get('map_point'):
            # GEOGRAPHY se maneja como string WKT o dict
            pass
        return result


class TrailRoute(BaseModel):
    """Modelo para trail_routes"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.trail_id = kwargs.get('trail_id')
        self.version = kwargs.get('version', 1)
        self.is_active = kwargs.get('is_active', True)
        self.total_distance_km = kwargs.get('total_distance_km')
        self.elevation_gain = kwargs.get('elevation_gain')
        self.elevation_loss = kwargs.get('elevation_loss')
        self.created_at = kwargs.get('created_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('trail_id'):
            result['trail_id'] = str(result['trail_id'])
        # Convertir Decimal a float
        if isinstance(result.get('total_distance_km'), Decimal):
            result['total_distance_km'] = float(result['total_distance_km'])
        return result


class RouteSegment(BaseModel):
    """Modelo para route_segments"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.route_id = kwargs.get('route_id')
        self.path = kwargs.get('path')  # GEOGRAPHY(LineStringZ, 4326)
        self.segment_order = kwargs.get('segment_order')
        self.distance_km = kwargs.get('distance_km')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('route_id'):
            result['route_id'] = str(result['route_id'])
        # Convertir Decimal a float
        if isinstance(result.get('distance_km'), Decimal):
            result['distance_km'] = float(result['distance_km'])
        return result


class RouteElevationProfile(BaseModel):
    """Modelo para route_elevation_profile"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.route_id = kwargs.get('route_id')
        self.distance_mark_km = kwargs.get('distance_mark_km')
        self.elevation_m = kwargs.get('elevation_m')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('route_id'):
            result['route_id'] = str(result['route_id'])
        # Convertir Decimal a float
        if isinstance(result.get('distance_mark_km'), Decimal):
            result['distance_mark_km'] = float(result['distance_mark_km'])
        return result


class TrailPoint(BaseModel):
    """Modelo para trail_points"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.trail_id = kwargs.get('trail_id')
        self.name = kwargs.get('name')
        self.description = kwargs.get('description')
        self.type = kwargs.get('type')  # 'inicio', 'fin', 'mirador', 'peligro', 'agua', 'descanso', 'refugio', 'cruce', 'campamento', 'cascada', 'vista', 'informacion'
        self.location = kwargs.get('location')  # GEOGRAPHY(PointZ, 4326)
        self.km_marker = kwargs.get('km_marker')
        self.order_index = kwargs.get('order_index')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('trail_id'):
            result['trail_id'] = str(result['trail_id'])
        # Convertir Decimal a float
        if isinstance(result.get('km_marker'), Decimal):
            result['km_marker'] = float(result['km_marker'])
        # Convertir location de geography a coordenadas
        if result.get('location'):
            location = result['location']
            # Si es un string WKT, intentar parsearlo
            if isinstance(location, str):
                # Formato: POINTZ(lon lat elevation) o POINT(lon lat)
                import re
                match = re.search(r'POINTZ?\s*\(([^)]+)\)', location)
                if match:
                    coords = match.group(1).strip().split()
                    if len(coords) >= 2:
                        lon = float(coords[0])
                        lat = float(coords[1])
                        elevation = float(coords[2]) if len(coords) > 2 else 0
                        result['location'] = {
                            'longitude': lon,
                            'latitude': lat,
                            'elevation': elevation
                        }
            # Si ya es un dict, mantenerlo
            elif isinstance(location, dict):
                result['location'] = location
        return result

"""
User trail history model
"""
from models.base import BaseModel
from datetime import datetime
from decimal import Decimal


class UserTrailHistory(BaseModel):
    """Modelo para user_trail_history"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.user_id = kwargs.get('user_id')
        self.trail_id = kwargs.get('trail_id')
        self.completed = kwargs.get('completed', False)
        self.completion_time_minutes = kwargs.get('completion_time_minutes')
        self.distance_km = kwargs.get('distance_km')
        self.elevation_gain = kwargs.get('elevation_gain')
        self.started_at = kwargs.get('started_at')
        self.finished_at = kwargs.get('finished_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('user_id'):
            result['user_id'] = str(result['user_id'])
        if result.get('trail_id'):
            result['trail_id'] = str(result['trail_id'])
        # Convertir Decimal a float
        if isinstance(result.get('distance_km'), Decimal):
            result['distance_km'] = float(result['distance_km'])
        return result

"""
Media models
"""
from models.base import BaseModel
from datetime import datetime


class TrailMedia(BaseModel):
    """Modelo para trail_media"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.trail_id = kwargs.get('trail_id')
        self.media_type = kwargs.get('media_type')  # 'image', 'photo_360', 'photo_180'
        self.url = kwargs.get('url')
        self.thumbnail_url = kwargs.get('thumbnail_url')
        self.order_index = kwargs.get('order_index')
        self.created_at = kwargs.get('created_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('trail_id'):
            result['trail_id'] = str(result['trail_id'])
        return result

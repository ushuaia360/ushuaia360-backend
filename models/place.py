"""
Tourist place models
"""
from models.base import BaseModel
from datetime import datetime


class TouristPlace(BaseModel):
    """Modelo para tourist_places"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.slug = kwargs.get('slug')
        self.category = kwargs.get('category')
        self.location = kwargs.get('location')  # GEOGRAPHY(Point, 4326)
        self.region = kwargs.get('region')
        self.country = kwargs.get('country')
        self.is_premium = kwargs.get('is_premium', True)
        self.created_at = kwargs.get('created_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUID a string
        if result.get('id'):
            result['id'] = str(result['id'])
        return result


class PlaceMedia(BaseModel):
    """Modelo para place_media"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.place_id = kwargs.get('place_id')
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
        if result.get('place_id'):
            result['place_id'] = str(result['place_id'])
        return result

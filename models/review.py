"""
Review models
"""
from models.base import BaseModel
from datetime import datetime


class TrailReview(BaseModel):
    """Modelo para trail_reviews"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.trail_id = kwargs.get('trail_id')
        self.user_id = kwargs.get('user_id')
        self.rating = kwargs.get('rating')  # 1-5
        self.comment = kwargs.get('comment')
        self.image_urls = kwargs.get('image_urls') or []
        self.created_at = kwargs.get('created_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('trail_id'):
            result['trail_id'] = str(result['trail_id'])
        if result.get('user_id'):
            result['user_id'] = str(result['user_id'])
        return result


class PlaceReview(BaseModel):
    """Modelo para place_reviews (puntos turísticos)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.place_id = kwargs.get('place_id')
        self.user_id = kwargs.get('user_id')
        self.rating = kwargs.get('rating')
        self.comment = kwargs.get('comment')
        self.image_urls = kwargs.get('image_urls') or []
        self.created_at = kwargs.get('created_at')

    def to_dict(self) -> dict:
        result = super().to_dict()
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('place_id'):
            result['place_id'] = str(result['place_id'])
        if result.get('user_id'):
            result['user_id'] = str(result['user_id'])
        return result

"""
Favorite models
"""
from models.base import BaseModel
from datetime import datetime


class UserFavorite(BaseModel):
    """Modelo para user_favorites"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.user_id = kwargs.get('user_id')
        self.entity_type = kwargs.get('entity_type')  # 'trail', 'place'
        self.entity_id = kwargs.get('entity_id')
        self.created_at = kwargs.get('created_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('user_id'):
            result['user_id'] = str(result['user_id'])
        if result.get('entity_id'):
            result['entity_id'] = str(result['entity_id'])
        return result

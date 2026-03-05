"""
Wallpaper model
"""
from models.base import BaseModel
from datetime import datetime


class Wallpaper(BaseModel):
    """Modelo para wallpapers"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.url = kwargs.get('url')
        self.is_premium = kwargs.get('is_premium', False)
        self.created_at = kwargs.get('created_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUID a string
        if result.get('id'):
            result['id'] = str(result['id'])
        return result

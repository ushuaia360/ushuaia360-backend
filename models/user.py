"""
User model
"""
from models.base import BaseModel
from datetime import datetime
from typing import Optional


class User(BaseModel):
    """Modelo para users"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.email = kwargs.get('email')
        self.password_hash = kwargs.get('password_hash')
        self.full_name = kwargs.get('full_name')
        self.avatar_url = kwargs.get('avatar_url')
        self.language = kwargs.get('language', 'es')
        self.is_admin = kwargs.get('is_admin', False)
        self.is_premium = kwargs.get('is_premium', False)
        self.premium_until = kwargs.get('premium_until')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
    
    def to_dict(self, exclude_password=True) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        if exclude_password:
            result.pop('password_hash', None)
        # Convertir UUID a string
        if result.get('id'):
            result['id'] = str(result['id'])
        return result

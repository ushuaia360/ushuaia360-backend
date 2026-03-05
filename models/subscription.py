"""
Subscription model
"""
from models.base import BaseModel
from datetime import datetime


class Subscription(BaseModel):
    """Modelo para subscriptions"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.user_id = kwargs.get('user_id')
        self.provider = kwargs.get('provider')  # 'apple', 'google'
        self.external_id = kwargs.get('external_id')
        self.status_id = kwargs.get('status_id')
        self.started_at = kwargs.get('started_at')
        self.expires_at = kwargs.get('expires_at')
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = super().to_dict()
        # Convertir UUIDs a strings
        if result.get('id'):
            result['id'] = str(result['id'])
        if result.get('user_id'):
            result['user_id'] = str(result['user_id'])
        return result

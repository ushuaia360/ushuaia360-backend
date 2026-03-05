"""
Status models
"""
from models.base import BaseModel


class TrailStatus(BaseModel):
    """Modelo para trail_statuses"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')


class SubscriptionStatus(BaseModel):
    """Modelo para subscription_statuses"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')

"""
Modelo de ejemplo
"""
from datetime import datetime
from models.base import BaseModel
from typing import Optional


class Example(BaseModel):
    """Modelo de ejemplo para referencia"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        name: str = "",
        description: Optional[str] = None,
        created_at: Optional[datetime] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at or datetime.utcnow()

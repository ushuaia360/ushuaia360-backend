"""
Modelo base para otros modelos
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
import uuid


class BaseModel:
    """Clase base para todos los modelos"""
    
    def __init__(self, **kwargs):
        """Inicializa el modelo con los atributos proporcionados"""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    result[key] = float(value)
                elif isinstance(value, uuid.UUID):
                    result[key] = str(value)
                elif value is None:
                    result[key] = None
                else:
                    result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: dict):
        """Crea una instancia del modelo desde un diccionario"""
        return cls(**data)
    
    @classmethod
    def from_row(cls, row):
        """Crea una instancia del modelo desde una fila de asyncpg"""
        if row is None:
            return None
        # asyncpg rows son dict-like
        return cls(**dict(row))
    
    def __repr__(self):
        """Representación del modelo"""
        attrs = ', '.join(f"{k}={v}" for k, v in self.__dict__.items() if not k.startswith('_'))
        return f"{self.__class__.__name__}({attrs})"

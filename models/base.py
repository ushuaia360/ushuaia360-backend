"""
Modelo base para otros modelos
"""
from datetime import datetime
from typing import Optional


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
                else:
                    result[key] = value
        return result
    
    def __repr__(self):
        """Representación del modelo"""
        attrs = ', '.join(f"{k}={v}" for k, v in self.__dict__.items() if not k.startswith('_'))
        return f"{self.__class__.__name__}({attrs})"

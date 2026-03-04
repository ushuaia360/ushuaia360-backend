"""
Servicio de ejemplo - Lógica de negocio
"""
from typing import List, Optional
from models.example import Example


class ExampleService:
    """Servicio de ejemplo para referencia"""
    
    @staticmethod
    async def get_all() -> List[Example]:
        """Obtiene todos los ejemplos"""
        # Aquí iría la lógica para obtener datos de la base de datos
        return []
    
    @staticmethod
    async def get_by_id(id: int) -> Optional[Example]:
        """Obtiene un ejemplo por ID"""
        # Aquí iría la lógica para obtener un ejemplo específico
        return None
    
    @staticmethod
    async def create(data: dict) -> Example:
        """Crea un nuevo ejemplo"""
        # Aquí iría la lógica para crear un nuevo ejemplo
        return Example(**data)
    
    @staticmethod
    async def update(id: int, data: dict) -> Optional[Example]:
        """Actualiza un ejemplo existente"""
        # Aquí iría la lógica para actualizar un ejemplo
        return None
    
    @staticmethod
    async def delete(id: int) -> bool:
        """Elimina un ejemplo"""
        # Aquí iría la lógica para eliminar un ejemplo
        return False

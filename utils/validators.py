"""
Utilidades de validación
"""
from typing import Any, Dict, List, Optional


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Optional[str]:
    """
    Valida que los campos requeridos estén presentes en los datos
    
    Args:
        data: Diccionario con los datos a validar
        required_fields: Lista de campos requeridos
    
    Returns:
        None si la validación es exitosa, mensaje de error si falla
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        return f"Campos requeridos faltantes: {', '.join(missing_fields)}"
    
    return None


def validate_email(email: str) -> bool:
    """Valida formato de email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_length(value: str, min_length: int = 0, max_length: int = None) -> bool:
    """Valida la longitud de un string"""
    if not isinstance(value, str):
        return False
    
    if len(value) < min_length:
        return False
    
    if max_length and len(value) > max_length:
        return False
    
    return True

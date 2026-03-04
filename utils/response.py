"""
Utilidades para respuestas HTTP
"""
from quart import jsonify
from typing import Any, Dict, Optional


def success_response(
    data: Any = None,
    message: str = "Operación exitosa",
    status_code: int = 200
) -> tuple:
    """
    Crea una respuesta de éxito estandarizada
    
    Args:
        data: Datos a incluir en la respuesta
        message: Mensaje descriptivo
        status_code: Código de estado HTTP
    
    Returns:
        Tupla con (jsonify response, status_code)
    """
    response = {
        'success': True,
        'message': message
    }
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code


def error_response(
    message: str = "Ha ocurrido un error",
    status_code: int = 400,
    errors: Optional[Dict] = None
) -> tuple:
    """
    Crea una respuesta de error estandarizada
    
    Args:
        message: Mensaje de error
        status_code: Código de estado HTTP
        errors: Diccionario con errores específicos (opcional)
    
    Returns:
        Tupla con (jsonify response, status_code)
    """
    response = {
        'success': False,
        'message': message
    }
    
    if errors:
        response['errors'] = errors
    
    return jsonify(response), status_code

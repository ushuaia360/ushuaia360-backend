"""
Manejo de errores
"""
import logging
from quart import jsonify

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Registra todos los manejadores de errores"""
    
    @app.errorhandler(404)
    async def not_found(error):
        """Manejo de errores 404"""
        return jsonify({
            'error': 'Not Found',
            'message': 'El recurso solicitado no existe',
            'status_code': 404
        }), 404
    
    @app.errorhandler(400)
    async def bad_request(error):
        """Manejo de errores 400"""
        return jsonify({
            'error': 'Bad Request',
            'message': 'Solicitud inválida',
            'status_code': 400
        }), 400
    
    @app.errorhandler(500)
    async def internal_error(error):
        """Manejo de errores 500"""
        logger.error(f"Error interno: {error}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Ha ocurrido un error en el servidor',
            'status_code': 500
        }), 500
    
    @app.errorhandler(Exception)
    async def handle_exception(error):
        """Manejo genérico de excepciones"""
        logger.error(f"Excepción no manejada: {error}", exc_info=True)
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Ha ocurrido un error inesperado',
            'status_code': 500
        }), 500

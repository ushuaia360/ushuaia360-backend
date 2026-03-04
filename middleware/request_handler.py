"""
Middleware para manejo de requests
"""
import logging
from quart import request

logger = logging.getLogger(__name__)


def register_middleware(app):
    """Registra todos los middlewares"""
    
    @app.before_request
    async def before_request():
        """Middleware ejecutado antes de cada request"""
        logger.info(f"{request.method} {request.path}")
    
    @app.after_request
    async def after_request(response):
        """Middleware ejecutado después de cada request"""
        # Headers de seguridad
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

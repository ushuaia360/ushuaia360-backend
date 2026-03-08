"""
Middleware para manejo de requests
"""
import logging
from quart import request, jsonify

logger = logging.getLogger(__name__)


def register_middleware(app):
    """Registra todos los middlewares"""
    
    @app.before_request
    async def before_request():
        """Middleware ejecutado antes de cada request"""
        # Manejar peticiones OPTIONS (preflight de CORS)
        if request.method == 'OPTIONS':
            response = jsonify({})
            response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Max-Age'] = '3600'
            return response
        
        logger.info(f"{request.method} {request.path}")
    
    @app.after_request
    async def after_request(response):
        """Middleware ejecutado después de cada request"""
        # Headers de seguridad
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

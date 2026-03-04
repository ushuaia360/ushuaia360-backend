"""
Registro de todas las rutas
"""
from quart import Blueprint
from routes.health import health_bp
from routes.api import api_bp


def register_routes(app):
    """Registra todos los blueprints de rutas"""
    # Blueprint para health checks
    app.register_blueprint(health_bp)
    
    # Blueprint para API v1
    app.register_blueprint(api_bp, url_prefix='/api/v1')

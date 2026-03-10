"""
Registro de todas las rutas
"""
from quart import Blueprint
from routes.health import health_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.trails import trails_bp
from routes.users import users_bp

def register_routes(app):
    """Registra todos los blueprints de rutas"""
    # Blueprint para health checks
    app.register_blueprint(health_bp)
    
    # Blueprint para API v1
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Blueprint para autenticación
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    
    # Blueprint para trails
    app.register_blueprint(trails_bp, url_prefix='/api/v1')

    # Blueprint para users
    app.register_blueprint(users_bp, url_prefix='/api/v1')
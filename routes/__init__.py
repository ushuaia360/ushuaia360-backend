"""
Registro de todas las rutas
"""
from quart import Blueprint
from routes.health import health_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.trails import trails_bp
from routes.users import users_bp
from routes.favorites import favorites_bp
from routes.map_markers import map_bp
from routes.places import places_bp
from routes.trail_history import trail_history_bp

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

    # Favoritos (app móvil)
    app.register_blueprint(favorites_bp, url_prefix='/api/v1')

    # Mapa: marcadores y lugares
    app.register_blueprint(map_bp, url_prefix='/api/v1')
    app.register_blueprint(places_bp, url_prefix='/api/v1')

    # Historial de recorridos (/me/trail-history/*)
    app.register_blueprint(trail_history_bp, url_prefix='/api/v1')
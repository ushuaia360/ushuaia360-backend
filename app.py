"""
API base con Quart - Aplicación principal
"""
from quart import Quart
from quart_cors import cors
import logging
from config.settings import Config
from routes import register_routes
from middleware.error_handler import register_error_handlers
from middleware.request_handler import register_middleware
from db import init_db

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """Factory function para crear la aplicación"""
    app = Quart(__name__)
    
    # Cargar configuración
    app.config.from_object(config_class)
    
    # Habilitar CORS
    app = cors(app, allow_origin=app.config.get('CORS_ORIGINS', '*'), allow_credentials=True)
    
    # Inicializar base de datos
    @app.before_serving
    async def startup():
        await init_db()
        logger.info("Base de datos inicializada correctamente")
    
    # Registrar middleware
    register_middleware(app)
    
    # Registrar rutas
    register_routes(app)
    
    # Registrar manejadores de errores
    register_error_handlers(app)
    
    logger.info("Aplicación inicializada correctamente")
    return app


# Crear instancia de la aplicación
app = create_app()


if __name__ == '__main__':
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 5000),
        debug=app.config.get('DEBUG', True)
    )

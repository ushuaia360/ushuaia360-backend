"""
Configuración de la aplicación
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base"""
    # Aplicación
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    # JSON
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True
    
    # Base de datos (cuando se agregue)
    # DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    
    # API
    API_VERSION = '1.0'
    API_PREFIX = '/api/v1'


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY debe estar configurada en producción")


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    DEBUG = True


# Mapeo de configuraciones
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

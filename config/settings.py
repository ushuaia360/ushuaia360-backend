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
    PORT = int(os.getenv('PORT', 5050))
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    # JSON
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True
    
    # Flask/Quart options
    PROVIDE_AUTOMATIC_OPTIONS = True
    
    # Base de datos
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', SECRET_KEY)
    JWT_EXPIRATION_SECONDS = int(os.getenv('JWT_EXPIRATION_SECONDS', 60 * 60 * 24 * 14))  # 14 days
    
    # Resend
    RESEND_API_KEY = os.getenv('RESEND_API_KEY')
    RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'noreply@ushuaia360.com')
    
    # Frontend URL (Next.js: páginas /verify, /reset-password)
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')

    # Deep link scheme de la app móvil (expo scheme en app.json)
    MOBILE_DEEP_LINK_SCHEME = os.getenv('MOBILE_DEEP_LINK_SCHEME', 'ushuaia360')
    
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

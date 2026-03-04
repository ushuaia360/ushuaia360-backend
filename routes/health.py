"""
Rutas de health check
"""
from quart import Blueprint, jsonify
from datetime import datetime

health_bp = Blueprint('health', __name__)


@health_bp.route('/')
async def index():
    """Endpoint raíz"""
    return jsonify({
        'message': 'API Ushuaia360',
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat()
    })


@health_bp.route('/health')
async def health():
    """Endpoint de health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

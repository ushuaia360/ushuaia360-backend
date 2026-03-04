"""
Rutas principales de la API
"""
from quart import Blueprint, jsonify
from datetime import datetime
from config.settings import Config

api_bp = Blueprint('api', __name__)


@api_bp.route('/status')
async def api_status():
    """Endpoint de estado de la API"""
    return jsonify({
        'api_version': Config.API_VERSION,
        'status': 'operational',
        'timestamp': datetime.utcnow().isoformat()
    })


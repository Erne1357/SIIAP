"""
Endpoint de salud del sistema.

GET /health  →  200 OK  (usado por Docker health checks y deploy.yml)
"""

from flask import Blueprint, jsonify

from app import db

api_health = Blueprint('api_health', __name__)


@api_health.route('/health', methods=['GET'])
def health_check():
    """Verifica que la app y la base de datos estén operativas."""
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False

    status = 'ok' if db_ok else 'degraded'
    code = 200 if db_ok else 503

    return jsonify({'status': status, 'db': db_ok}), code

"""
Rastreo de sesiones activas usando Redis.

Permite que el postgraduate_admin vea cuántos usuarios están conectados
(han tenido actividad en los últimos SESSION_TTL segundos).

Uso:
    # En before_request (app/__init__.py), tras verificar que el usuario está autenticado:
    from app.utils.session_tracker import track_user_session

    track_user_session(current_user.id)

    # En la ruta de configuración del admin:
    from app.utils.session_tracker import get_online_users_count, get_online_users

    count = get_online_users_count()
    users = get_online_users()  # lista de user_ids
"""

import logging
import time
from typing import List

import redis as redis_lib
from flask import current_app

logger = logging.getLogger(__name__)

# Tiempo en segundos que un usuario se considera "activo" (15 minutos = sesión Flask)
SESSION_TTL = 15 * 60

# Prefijo de clave en Redis
_KEY_PREFIX = 'siiap:online:'

# ── Circuit breaker ───────────────────────────────────────────────────────────
# Evita bloquear cada request cuando Redis no está disponible.
# Después de un fallo, salta todos los intentos durante _CIRCUIT_RESET segundos.
_circuit_open_until: float = 0.0
_CIRCUIT_RESET = 300  # segundos antes de reintentar (5 min)


def _get_client() -> redis_lib.Redis:
    """Devuelve un cliente Redis. Lanza excepción si el circuit breaker está abierto."""
    if time.monotonic() < _circuit_open_until:
        raise redis_lib.ConnectionError('Redis circuit breaker open')
    url = current_app.config.get('REDIS_URL', 'redis://redis:6379/0')
    return redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


def _open_circuit(e: Exception, context: str) -> None:
    global _circuit_open_until
    _circuit_open_until = time.monotonic() + _CIRCUIT_RESET
    logger.warning(f'[session_tracker] {context}: {e} — Redis desactivado por {_CIRCUIT_RESET}s')


def track_user_session(user_id: int) -> None:
    """
    Registra o renueva la presencia activa del usuario en Redis.
    Llama a esta función en cada request autenticado.
    """
    global _circuit_open_until
    try:
        client = _get_client()
        key = f'{_KEY_PREFIX}{user_id}'
        # SETEX crea la clave con TTL; si ya existe, la renueva
        client.setex(key, SESSION_TTL, '1')
        _circuit_open_until = 0.0  # éxito → resetear circuit breaker
    except redis_lib.ConnectionError as e:
        if 'circuit breaker' not in str(e):
            _open_circuit(e, f'Error al rastrear user {user_id}')
    except Exception as e:
        _open_circuit(e, f'Error al rastrear user {user_id}')


def get_online_users_count() -> int:
    """Retorna el número de usuarios con sesión activa en este momento."""
    try:
        client = _get_client()
        keys = client.keys(f'{_KEY_PREFIX}*')
        return len(keys)
    except Exception as e:
        if 'circuit breaker' not in str(e):
            _open_circuit(e, 'Error al obtener conteo')
        return 0


def get_online_users() -> List[int]:
    """Retorna la lista de user_ids con sesión activa en este momento."""
    try:
        client = _get_client()
        keys = client.keys(f'{_KEY_PREFIX}*')
        prefix_len = len(_KEY_PREFIX)
        return [int(k[prefix_len:]) for k in keys if k[prefix_len:].isdigit()]
    except Exception as e:
        if 'circuit breaker' not in str(e):
            _open_circuit(e, 'Error al obtener lista de usuarios')
        return []

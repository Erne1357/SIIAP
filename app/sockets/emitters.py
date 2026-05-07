"""
Helpers para emisión de eventos Socket.IO.

Centraliza patrones repetidos de emit para mantener consistencia y evitar
boilerplate try/except en cada servicio.

Todos los emits envuelven errores silenciosamente (fire-and-forget) para
que fallas de Redis/socketio no tumben la request original.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def emit_user_and_coordinators(event: str, payload: dict, user_id: int, program_id: Optional[int]):
    """
    Emite un evento user-targeted al usuario afectado y a los coordinadores
    del programa (scoped) + coordinadores globales (coordinator:programs:all).

    Útil para admission:status_changed, permanence:status_changed,
    extension:decided: el usuario necesita la notificación y los coordinadores
    del programa correspondiente también deben verla en tiempo real.

    Args:
        event: nombre del evento socket (ej. 'admission:status_changed')
        payload: diccionario serializable con los datos del evento
        user_id: usuario afectado (sala user:{id})
        program_id: programa al que pertenece el evento. Si es None, no se
                    emite a coordinator:program:{pid} (solo global y usuario).
    """
    try:
        from app.extensions import socketio
        socketio.emit(event, payload, room=f'user:{user_id}')
        socketio.emit(event, payload, room='coordinator:programs:all')
        if program_id is not None:
            socketio.emit(event, payload, room=f'coordinator:program:{program_id}')
    except Exception as exc:
        logger.warning(f'[WS] emit_user_and_coordinators fallo ({event}): {exc}')


def emit_to_coordinators(event: str, payload: dict, program_id: Optional[int]):
    """
    Emite un evento solo a coordinadores (sin user:{id}).

    Args:
        event: nombre del evento
        payload: diccionario serializable
        program_id: si None, solo a coordinator:programs:all; si int, también
                    a coordinator:program:{pid}.
    """
    try:
        from app.extensions import socketio
        socketio.emit(event, payload, room='coordinator:programs:all')
        if program_id is not None:
            socketio.emit(event, payload, room=f'coordinator:program:{program_id}')
    except Exception as exc:
        logger.warning(f'[WS] emit_to_coordinators fallo ({event}): {exc}')


def emit_broadcast(event: str, payload: dict):
    """
    Emite un evento a todos los clientes conectados (sin sala).

    Útil para cambios en páginas públicas (event:changed, program:changed).
    """
    try:
        from app.extensions import socketio
        socketio.emit(event, payload)
    except Exception as exc:
        logger.warning(f'[WS] emit_broadcast fallo ({event}): {exc}')


def emit_to_user(event: str, payload: dict, user_id: int):
    """Emite un evento solo a la sala user:{user_id}."""
    try:
        from app.extensions import socketio
        socketio.emit(event, payload, room=f'user:{user_id}')
    except Exception as exc:
        logger.warning(f'[WS] emit_to_user fallo ({event}): {exc}')

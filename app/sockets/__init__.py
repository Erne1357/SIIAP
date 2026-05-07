"""
Registro centralizado de todos los handlers de Socket.IO.

Uso en create_app():
    from app.sockets import register_socket_handlers
    register_socket_handlers(socketio)
"""

from app.sockets.core import register_core_handlers


def register_socket_handlers(socketio):
    register_core_handlers(socketio)

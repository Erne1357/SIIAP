"""
Handlers de conexión / desconexión de Socket.IO.

Salas utilizadas:
  user:{user_id}             — sala privada por usuario (notificaciones personales)
  role:{role_name}           — sala por rol (eventos dirigidos a un grupo)
  deliberation:{program_id}  — sala de deliberación por programa

Los clientes NO necesitan suscribirse manualmente; al conectar el servidor
los une automáticamente a sus salas según su sesión Flask-Login.
"""

import logging
from flask_login import current_user
from flask_socketio import join_room, disconnect

logger = logging.getLogger(__name__)


def register_core_handlers(socketio):

    @socketio.on('connect')
    def handle_connect():
        """
        Evento de conexión.
        Se llama automáticamente cuando el cliente abre el socket.
        Rechaza la conexión si el usuario no está autenticado.
        """
        if not current_user.is_authenticated:
            logger.warning('[WS] Conexión rechazada: usuario no autenticado')
            return False  # Desconecta al cliente

        # Sala personal
        join_room(f'user:{current_user.id}')

        # Salas por rol (rol.name)
        if hasattr(current_user, 'roles'):
            for role in current_user.roles:
                join_room(f'role:{role.name}')

        logger.debug(
            f'[WS] Conectado: user={current_user.id} '
            f'roles={[r.name for r in getattr(current_user, "roles", [])]}'
        )

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            logger.debug(f'[WS] Desconectado: user={current_user.id}')

    @socketio.on('join_deliberation')
    def handle_join_deliberation(data):
        """
        Permite a un coordinador/admin unirse a la sala de deliberación
        de un programa específico para recibir actualizaciones en tiempo real.

        Payload esperado: { "program_id": 42 }
        """
        if not current_user.is_authenticated:
            return False

        program_id = data.get('program_id')
        if program_id:
            join_room(f'deliberation:{program_id}')
            logger.debug(
                f'[WS] user={current_user.id} joined deliberation:{program_id}'
            )

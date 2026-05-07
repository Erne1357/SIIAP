"""
Handlers de conexión / desconexión de Socket.IO.

Salas utilizadas:
  user:{user_id}                 — sala privada por usuario (notificaciones personales)
  role:{role_name}               — sala por rol (eventos dirigidos a un grupo)
  role:coordinator               — sala funcional: todos los que tienen coordinator.page.view
                                   (program_admin, postgraduate_admin, coordinator)
  coordinator:program:{pid}      — sala por programa para coordinadores scoped a ese programa
  coordinator:programs:all       — sala para coordinadores con acceso global (postgraduate_admin)
  deliberation:{program_id}      — sala de deliberación por programa

Los clientes NO necesitan suscribirse manualmente; al conectar el servidor
los une automáticamente a sus salas según su sesión Flask-Login.

Nota (Phase 9): Las salas SocketIO se mantienen basadas en roles porque el
broadcasting es notificación, no control de acceso. La sala role:coordinator
se asigna por permiso (coordinator.page.view) en lugar de solo por role.name
para que program_admin y postgraduate_admin también la reciban.

Nota (Fase 3 gap resuelto): coordinator:program:{pid} y coordinator:programs:all
permiten emitir eventos user-scoped (admission:status_changed, permanence:status_changed,
extension:decided) solo a los coordinadores del programa relevante, en lugar de
inundar a todos los coordinadores vía role:coordinator.
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

        # Sala por rol
        if current_user.role:
            join_room(f'role:{current_user.role.name}')

        # Sala funcional de coordinación: todos los que gestionan programas
        # (program_admin, postgraduate_admin, coordinator)
        if current_user.has_permission('coordinator.page.view'):
            join_room('role:coordinator')

            # Salas program-scoped para eventos user-targeted
            # None = acceso global (postgraduate_admin) → sala catch-all
            # set  = acceso scoped → una sala por programa accesible
            try:
                accessible_pids = current_user.get_accessible_program_ids()
                if accessible_pids is None:
                    join_room('coordinator:programs:all')
                else:
                    for pid in accessible_pids:
                        join_room(f'coordinator:program:{pid}')
            except Exception as exc:
                logger.warning(f'[WS] No se pudieron resolver programas accesibles: {exc}')

        logger.debug(
            f'[WS] Conectado: user={current_user.id} '
            f'role={current_user.role.name if current_user.role else None}'
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

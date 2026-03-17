"""
Instancias de extensiones Flask compartidas entre módulos.

Al definirlas aquí y llamar a .init_app(app) en create_app(), se evita
el problema de importaciones circulares: cualquier servicio o socket handler
puede importar `socketio` desde este módulo sin depender de `app/__init__.py`.
"""

from flask_socketio import SocketIO

# La instancia de SocketIO se configura en create_app() con socketio.init_app(app, ...)
socketio = SocketIO()

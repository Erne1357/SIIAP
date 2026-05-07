# eventlet.monkey_patch() DEBE estar antes de cualquier otro import
# para que las operaciones de red funcionen de forma asíncrona con Socket.IO
import eventlet
eventlet.monkey_patch()

from app import create_app       # noqa: E402
from app.extensions import socketio  # noqa: E402, F401

app = create_app()

if __name__ == '__main__':
    # Desarrollo local: usar socketio.run en lugar de app.run
    socketio.run(app, host='0.0.0.0', debug=True, use_reloader=True)

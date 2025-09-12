# app/routes/api/files_api.py
from pathlib import Path
from flask import Blueprint, current_app, send_file, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.utils.files import abs_path_from_db

api_files = Blueprint('api_files', __name__, url_prefix='/files')

INLINE_EXT = {'pdf'}  # muestra inline; el resto descarga

def _send_safe(base: Path, rel_path: str, inline: bool):
    """
    base: carpeta base permitida (Path)
    rel_path: ruta relativa guardada en BD/URL (p.ej. '42/admission/mi_archivo.pdf')
    inline: True -> inline, False -> attachment
    """
    try:
        abs_path = abs_path_from_db(rel_path, base)  # safe_join
    except Exception:
        abort(400)  # traversal o ruta inválida

    p = Path(abs_path)
    if not p.is_file():
        abort(404)

    # send_file con ETag/If-Modified-Since
    return send_file(
        str(p),
        as_attachment=not inline,
        conditional=True
    )

@api_files.route('/avatar/<int:user_id>/<path:filename>', methods=['GET'])
@login_required
def avatar(user_id: int, filename: str):
    # Cualquier usuario autenticado puede ver avatares.
    # Si quieres restringir, agrega chequeo similar a user_doc.
    filename = secure_filename(filename)
    rel = f"{user_id}/{filename}"
    base: Path = current_app.config['AVATAR_FOLDER']
    # imágenes -> inline
    return _send_safe(base, rel, inline=True)

@api_files.route('/doc/<int:user_id>/<phase>/<path:filename>', methods=['GET'])
@login_required
def user_doc(user_id: int, phase: str, filename: str):
    # Control de acceso: dueño o roles privilegiados
    allowed_roles = {'postgraduate_admin', 'program_admin', 'social_service'}
    if user_id != current_user.id and current_user.role.name not in allowed_roles:
        abort(403)

    # Fases válidas
    valid_phases = {'admission', 'permanence', 'conclusion'}
    if phase not in valid_phases:
        abort(400)

    filename = secure_filename(filename)
    rel = f"{user_id}/{phase}/{filename}"
    base: Path = current_app.config['USER_DOCS_FOLDER']

    # inline sólo para ciertas extensiones (PDF por ahora)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return _send_safe(base, rel, inline=(ext in INLINE_EXT))

@api_files.route('/template/<path:filename>', methods=['GET'])
@login_required
def template(filename: str):
    filename = secure_filename(filename)
    # Aquí tus plantillas viven "flat" (sin user_id/phase)
    base: Path = current_app.config['TEMPLATE_STORE']
    return _send_safe(base, filename, inline=False)  # siempre como descarga

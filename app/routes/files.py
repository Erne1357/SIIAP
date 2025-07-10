from flask import Blueprint, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from pathlib import Path
from werkzeug.utils import safe_join

bp_files = Blueprint('files', __name__, url_prefix='/files')

# ---------- Avatares públicos ----------------------------------------------
@bp_files.route('/avatar/<int:user_id>/<filename>')
@login_required
def avatar(user_id: int, filename: str):
    root: Path = current_app.config['AVATAR_FOLDER'] / str(user_id)
    return _safe_send(root, filename, as_attachment=False)

# ---------- Documentos privados --------------------------------------------
@bp_files.route('/doc/<int:user_id>/<phase>/<filename>')
@login_required
def user_doc(user_id: int, phase: str, filename: str):
    # Sólo dueño o personal con rol staff
    if user_id != current_user.id and not getattr(current_user, 'is_staff', False):
        abort(403)
    root: Path = (current_app.config['USER_DOCS_FOLDER']
                  / str(user_id) / phase)
    return _safe_send(root, filename, as_attachment=True)

# ---------- helper interno --------------------------------------------------
def _safe_send(root: Path, filename: str, as_attachment=False):
    file_path = safe_join(root, filename)
    if not file_path or not Path(file_path).is_file():
        abort(404)
    return send_from_directory(root, filename, as_attachment=as_attachment)

# ---------- Plantillas públicas ---------------------------------------------
@bp_files.route('/template/<path:filename>')
@login_required          # quítalo si quieres que sean públicas
def template(filename: str):
    root: Path = current_app.config['TEMPLATE_STORE']
    return _safe_send(root, filename, as_attachment=True)


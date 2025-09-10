from flask import Blueprint, current_app, send_file, abort
from flask_login import login_required, current_user
from pathlib import Path

bp_files = Blueprint('files', __name__, url_prefix='/files')


@bp_files.route('/avatar/<int:user_id>/<filename>')
@login_required
def avatar(user_id: int, filename: str):
    # Ruta absoluta a la carpeta de avatares
    avatar_folder: Path = current_app.config['AVATAR_FOLDER'] / str(user_id)
    file_path = avatar_folder / filename

    if not file_path.is_file():
        abort(404)
    # no attachment para verlo inline
    return send_file(str(file_path), as_attachment=False)


@bp_files.route('/doc/<int:user_id>/<phase>/<filename>')
@login_required
def user_doc(user_id: int, phase: str, filename: str):
    # Control de acceso
    allowed = ['postgraduate_admin', 'program_admin', 'social_service']
    if user_id != current_user.id and current_user.role.name not in allowed:
        abort(403)

    # Ruta absoluta
    docs_folder: Path = current_app.config['USER_DOCS_FOLDER'] / str(user_id) / phase
    file_path = docs_folder / filename
    if not file_path.is_file():
        abort(404)

    # Decide inline vs descarga según extensión
    ext = filename.rsplit('.', 1)[-1].lower()
    inline_ext = {'pdf'}  # puedes añadir más si quieres
    as_attachment = False if ext in inline_ext else True

    return send_file(
        str(file_path),
        as_attachment=as_attachment,
        conditional=True  # habilita uso de ETag/If-Modified-Since
    )


@bp_files.route('/template/<path:filename>')
@login_required
def template(filename: str):
    tpl_folder: Path = current_app.config['TEMPLATE_STORE']
    file_path = tpl_folder / filename

    if not file_path.is_file():
        abort(404)
    return send_file(str(file_path), as_attachment=True)

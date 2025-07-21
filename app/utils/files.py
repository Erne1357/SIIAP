from pathlib import Path
import uuid
from werkzeug.utils import secure_filename, safe_join
from flask import current_app, abort
from typing import Literal

def _uuid_name(ext: str) -> str:
    return f"{uuid.uuid4().hex}.{ext.lower()}"

# ---------- rutas absolutas -------------------------------------------------
def avatar_dir(user_id: int) -> Path:
    if current_app.config['AVATAR_FOLDER'] / str(user_id) is None:
       #Si no existe la carpeta, la creamos
       current_app.config['AVATAR_FOLDER'] / str(user_id).mkdir(parents=True, exist_ok=True)
    return current_app.config['AVATAR_FOLDER'] / str(user_id)

def docs_dir(user_id: int, phase: Literal['admission', 'permanence', 'conclusion']) -> Path:
    return (current_app.config['USER_DOCS_FOLDER']
            / str(user_id) / phase)

# ---------- operaciones comunes --------------------------------------------
def save_avatar(file_storage, user_id: int) -> str:
    ext = _validate_ext(file_storage.filename, current_app.config['ALLOWED_IMAGE_EXT'])
    folder = avatar_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)

    filename = _uuid_name(ext)
    file_storage.save(folder / filename)
    return f"{user_id}/{filename}"          

def save_user_doc(file_storage, user_id: int, phase: str, name: str) -> str:
    ext = _validate_ext(file_storage.filename, current_app.config['ALLOWED_DOC_EXT'])
    folder = docs_dir(user_id, phase)
    folder.mkdir(parents=True, exist_ok=True)

    safe = secure_filename(name.rsplit('.', 1)[0])
    filename = f"{safe}.{ext}"
    file_storage.save(folder / filename)
    return f"{user_id}/{phase}/{filename}"

def _validate_ext(name: str, allowed: set[str]) -> str:
    if '.' not in name:
        abort(400, "Archivo sin extensión")
    ext = name.rsplit('.', 1)[1].lower()
    if ext not in allowed:
        abort(400, "Extensión no permitida")
    return ext

def abs_path_from_db(relative_path: str, base_folder: Path) -> Path:
    """Convierte '42/avatar.webp' ➜ <Path …/uploads/avatars/42/avatar.webp>"""
    return safe_join(base_folder, relative_path)  # evita ../ traversal

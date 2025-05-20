import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    INSTANCE_DIR = BASE_DIR / 'instance'

    STATIC_FOLDER  = BASE_DIR / 'app' / 'static'
    UPLOAD_FOLDER  = INSTANCE_DIR / 'uploads'
    TEMPLATE_STORE = INSTANCE_DIR / 'templates_sys'

    # sub-rutas útiles
    AVATAR_FOLDER      = UPLOAD_FOLDER / 'avatars'
    USER_DOCS_FOLDER   = UPLOAD_FOLDER / 'documents'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # ---- límites y tipos permitidos -------------------------------------------
    ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp'}
    ALLOWED_DOC_EXT   = {'pdf', 'doc', 'docx', 'xlsx'}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024         # 10 MB

    # Secret key for sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta'
    # SQLAlchemy database URI: using PostgreSQL; 'db' is the Docker service name
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:password@db:5432/SIIAPEC'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

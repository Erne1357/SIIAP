import os
from pathlib import Path

class Config:
    STATIC_VERSION = "1.0.41111111166" 
    BASE_DIR = Path(__file__).resolve().parent.parent
    INSTANCE_DIR = BASE_DIR / 'instance'

    STATIC_FOLDER  = BASE_DIR / 'app' / 'static'
    UPLOAD_FOLDER  = INSTANCE_DIR / 'uploads'
    TEMPLATE_STORE = INSTANCE_DIR / 'templates_sys'

    # sub-rutas útiles
    AVATAR_FOLDER      = UPLOAD_FOLDER / 'avatars'
    USER_DOCS_FOLDER   = UPLOAD_FOLDER / 'documents'

    # ---- límites y tipos permitidos -------------------------------------------
    #ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp'}
    ALLOWED_DOC_EXT   = {'pdf'} #, 'doc', 'docx', 'xlsx'}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024         # 10 MB

    # Secret key for sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta'
    # SQLAlchemy database URI: using PostgreSQL; 'db' is the Docker service name
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:password@db:5432/SIIAP'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_NAME = "siiapec_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"   # o "Strict" si no haces POST cross-site
    SESSION_COOKIE_SECURE = False     # True en producción con HTTPS
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False    # True en producción con HTTPS

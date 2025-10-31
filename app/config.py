import os
from pathlib import Path

class Config:
    # Versión estática (actualízala cuando cambies CSS/JS)
    STATIC_VERSION = os.environ.get('STATIC_VERSION', '1.0.41111111276')
    
    # Directorios base
    BASE_DIR = Path(__file__).resolve().parent.parent
    INSTANCE_DIR = BASE_DIR / 'instance'
    STATIC_FOLDER = BASE_DIR / 'app' / 'static'
    
    # Uploads - puede ser sobrescrito por variable de entorno
    UPLOAD_FOLDER = Path(os.environ.get('UPLOAD_FOLDER', str(INSTANCE_DIR / 'uploads')))
    TEMPLATE_STORE = INSTANCE_DIR / 'templates_sys'

    # Sub-rutas útiles
    AVATAR_FOLDER = UPLOAD_FOLDER / 'avatars'
    USER_DOCS_FOLDER = UPLOAD_FOLDER / 'documents'

    # Límites y tipos permitidos
    ALLOWED_DOC_EXT = {'pdf'}
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024  # 3 MB

    # ===== SEGURIDAD =====
    # Secret key - DEBE ser diferente en producción
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-CHANGE-IN-PRODUCTION')
    
    # ===== BASE DE DATOS =====
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:password@db:5432/SIIAP'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ===== SESIONES Y COOKIES =====
    SESSION_COOKIE_NAME = "siiap_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # En producción con HTTPS detrás de proxy, esto debe ser True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    
    # ===== ENTORNO =====
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # ===== GUNICORN (solo para referencia) =====
    # Estas variables se usarán directamente en el comando gunicorn
    GUNICORN_WORKERS = int(os.environ.get('GUNICORN_WORKERS', '4'))
    GUNICORN_TIMEOUT = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
import os

class Config:
    # Secret key for sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta'
    # SQLAlchemy database URI: using PostgreSQL; 'db' is the Docker service name
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:password@db:5432/SIIAPEC'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

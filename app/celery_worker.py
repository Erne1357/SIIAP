# app/celery_worker.py
from app import create_app
from app.celery_app import init_celery

app = create_app()
celery = init_celery(app)

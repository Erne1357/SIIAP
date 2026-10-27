"""Celery TaskLog queries and writes for the worker admin panel."""
from __future__ import annotations

from app import db
from app.models.task_log import TaskLog
from app.utils.datetime_utils import now_local


def paginate_task_logs(page: int, per_page: int, status=None, task_name=None, triggered_by=None):
    """Task history, newest first, optionally filtered. Returns a Pagination."""
    q = TaskLog.query

    if status:
        q = q.filter(TaskLog.status == status)
    if task_name:
        q = q.filter(TaskLog.task_name == task_name)
    if triggered_by:
        q = q.filter(TaskLog.triggered_by == triggered_by)

    return q.order_by(TaskLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def log_manual_task(task_id: str, task_name: str, kwargs: dict, user_id: int) -> TaskLog:
    """Record a manually triggered task as 'pending' (commits)."""
    log = TaskLog(
        task_id=task_id,
        task_name=task_name,
        status='pending',
        triggered_by='manual',
        triggered_by_user_id=user_id,
        kwargs=kwargs,
        created_at=now_local(),
    )
    db.session.add(log)
    db.session.commit()
    return log

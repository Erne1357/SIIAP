# app/services/teaching_scope_service.py
"""
Who may see a course group (phase 6B1).

A teacher is whoever a group names as `teacher_id`, whatever their role. The
program staff in scope (coordinator, postgraduate admin) also see the group.
"""
from __future__ import annotations

from typing import Optional

from app.models.course_group import CourseGroup
from app.services import program_scope_service


def groups_of(user_id: int, period_id: Optional[int] = None) -> list[CourseGroup]:
    query = CourseGroup.query.filter_by(teacher_id=user_id)
    if period_id is not None:
        query = query.filter_by(academic_period_id=period_id)
    return query.order_by(CourseGroup.academic_period_id.desc(), CourseGroup.id).all()


def can_view_group(user, group: Optional[CourseGroup]) -> bool:
    if group is None or user is None:
        return False
    if group.teacher_id == user.id:
        return True
    return program_scope_service.program_in_scope(user, group.program_id)

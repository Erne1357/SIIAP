# app/services/teacher_service.py
"""
Teacher accounts (phase 6B1).

A teacher is an assignment (`CourseGroup.teacher_id`), not a role: any active
internal user can teach. The `teacher` role only exists for people who have no
other role, and this service creates exactly those accounts.
"""
from __future__ import annotations

import logging

from app import db
from app.models.role import Role
from app.models.user import User
from app.services import password_reset_service as prs
from app.services.errors import DomainError
from app.services.user_history_service import UserHistoryService

logger = logging.getLogger(__name__)

TEACHER_ROLE = 'teacher'
#: Roles that never teach: applicants and students are not staff.
_NON_TEACHING_ROLES = ('applicant', 'student')


class TeacherError(DomainError):
    """Business rule of teacher accounts."""


def create_teacher(first_name: str, last_name: str, email: str, actor_id: int) -> User:
    """
    Create a `teacher` account and mail the single-use link to set a password.

    An existing teacher with that e-mail is returned as is. An account with any
    other role is refused: nobody's role is changed here.
    """
    first_name = (first_name or '').strip()
    last_name = (last_name or '').strip()
    email = (email or '').strip().lower()
    if not first_name or not last_name:
        raise TeacherError('El nombre y el apellido del docente son obligatorios.')
    if '@' not in email:
        raise TeacherError('El correo electrónico no es una dirección válida.')

    existing = User.query.filter(db.func.lower(User.email) == email).first()
    if existing is None:
        existing = User.query.filter(db.func.lower(User.username) == email).first()
    if existing is not None:
        if existing.role is not None and existing.role.name == TEACHER_ROLE:
            if not existing.is_active:
                raise TeacherError('Esa cuenta de docente está desactivada.')
            return existing
        raise TeacherError(
            'No se pudo dar de alta al docente con ese correo. Si ya tiene cuenta, '
            'elígelo de la lista de docentes.')

    role = Role.query.filter_by(name=TEACHER_ROLE).first()
    if role is None:
        raise TeacherError("El rol 'teacher' no existe en el sistema.")

    user = User(
        first_name=first_name, last_name=last_name, mother_last_name='',
        username=email, password=prs.random_password(), email=email,
        is_internal=True, role_id=role.id, must_change_password=True,
    )
    db.session.add(user)
    db.session.flush()

    token = prs.generate_token(user_id=user.id, purpose='set_password',
                               ttl_minutes=prs.INTERACTIVE_TTL_MINUTES, created_by_id=actor_id)
    # Savepoint: a database error while queueing must not poison the session
    # that still has to commit the account.
    savepoint = db.session.begin_nested()
    try:
        from app.services.email_service import EmailService
        from app.services.email_templates import EmailTemplates

        subject, html = EmailTemplates.staff_account_set_password(
            user_name=f'{first_name} {last_name}'.strip(), username=user.username,
            token_link=prs.build_reset_password_url(token.token), expires_at=token.expires_at,
        )
        EmailService.queue_email(user_id=user.id, subject=subject, html_content=html)
        savepoint.commit()
    except Exception as exc:  # the token row persists: the e-mail can be re-sent
        if savepoint.is_active:
            savepoint.rollback()
        logger.warning('[teacher_service] activation e-mail not queued for user %s: %s',
                       user.id, exc)

    UserHistoryService.log_action(
        user_id=user.id, action='created', admin_id=actor_id,
        details={'kind': 'teacher_account'},
    )
    db.session.commit()
    return user


def teacher_choices() -> list[User]:
    """Active internal users who may teach: `teacher` accounts first, then staff."""
    users = (User.query.join(Role, Role.id == User.role_id)
             .filter(User.is_active.is_(True), User.is_internal.is_(True),
                     Role.name.notin_(_NON_TEACHING_ROLES))
             .all())
    return sorted(users, key=lambda u: (u.role.name != TEACHER_ROLE,
                                        (u.last_name or '').lower(),
                                        (u.first_name or '').lower()))

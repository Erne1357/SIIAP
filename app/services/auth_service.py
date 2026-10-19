"""
Database access behind the authentication routes.

The login route's order of checks, its rate limiting, the timing-equalizer
hash and the CSRF rotation stay in ``app/routes/api/auth_api.py``; this module
only owns the queries and commits so routes never touch the session.
"""
from __future__ import annotations

from typing import Optional

from werkzeug.security import generate_password_hash

from app import db
from app.models.role import Role
from app.models.user import User
from app.services import password_reset_service as prs
from app.services.errors import DomainError
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local


def find_user_by_username(username: str) -> Optional[User]:
    """Exact-match lookup used by the login flow."""
    return User.query.filter_by(username=username).first()


def record_login(user: User) -> None:
    """Stamp ``last_login`` and commit (after a successful login)."""
    user.last_login = now_local()
    db.session.commit()


def change_own_password(user: User, new_password: str, logger=None) -> None:
    """
    Store the new password hash, clear ``must_change_password`` and log it.

    The password write is committed first; a failure while writing the history
    row is logged and swallowed, exactly as the route always did.
    """
    user.password = generate_password_hash(new_password)
    user.must_change_password = False
    db.session.commit()

    try:
        UserHistoryService.log_password_change(user_id=user.id, changed_by_user=True)
        db.session.commit()
    except Exception as e:  # noqa: BLE001 - history is best-effort here
        if logger is not None:
            logger.error(f"Error al registrar cambio de contraseña en historial: {e}")


def reset_password_with_token(token: str, new_password: str) -> User:
    """
    Consume a reset token and commit. On any failure the session is rolled
    back and the original exception is re-raised for the route to translate.
    """
    try:
        user = prs.consume_token(token, new_password)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return user


class RegistrationRejected(DomainError):
    """Self-registration refused (duplicate username/e-mail). Spanish message."""


class ApplicantRoleMissing(Exception):
    """The ``applicant`` role is not seeded."""


def ensure_registration_available(username: str, email: str) -> None:
    """Raise RegistrationRejected when the username or e-mail already exists."""
    if User.query.filter_by(username=username).first():
        raise RegistrationRejected("El nombre de usuario ya existe.")
    if User.query.filter_by(email=email).first():
        raise RegistrationRejected("El correo electrónico ya está registrado.")


def get_applicant_role_id() -> int:
    """Id of the ``applicant`` role; raises ApplicantRoleMissing if absent."""
    role = Role.query.filter_by(name="applicant").first()
    if not role:
        raise ApplicantRoleMissing()
    return role.id


def register_applicant(*, first_name, last_name, mother_last_name, username,
                       password, email, is_internal, role_id) -> User:
    """Create the applicant account and commit; rolls back on failure."""
    try:
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            mother_last_name=mother_last_name,
            username=username,
            password=password,
            email=email,
            is_internal=is_internal,
            role_id=role_id,
            # The applicant just chose this password: nothing to force on the
            # next login.
            must_change_password=False,
        )
        db.session.add(new_user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return new_user

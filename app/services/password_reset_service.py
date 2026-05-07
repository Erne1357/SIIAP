"""
Token-based password set/reset flow.

Generates opaque random tokens stored in `password_reset_token`.  Used by:
  - Bulk-import student onboarding (purpose='set_password').
  - Future "forgot password" flow (purpose='reset_password').

Service is framework-agnostic: routes pass user IDs and tokens explicitly,
service does not touch request/session/current_user.
"""

import secrets
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import db
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.user_history_service import UserHistoryService
from app.utils.datetime_utils import now_local


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class PasswordResetError(Exception):
    """Base error for password reset operations."""


class TokenNotFound(PasswordResetError):
    pass


class TokenExpired(PasswordResetError):
    pass


class TokenAlreadyUsed(PasswordResetError):
    pass


class WeakPassword(PasswordResetError):
    pass


# ---------------------------------------------------------------------------
# Token operations
# ---------------------------------------------------------------------------

def generate_token(
    user_id: int,
    purpose: str = 'set_password',
    ttl_days: int = 7,
    created_by_id: int | None = None,
) -> PasswordResetToken:
    """
    Create and persist a new opaque password reset token for the user.

    Caller is responsible for committing the surrounding transaction or
    calling db.session.commit() afterwards.
    """
    if purpose not in ('set_password', 'reset_password'):
        raise ValueError(f"Invalid purpose: {purpose!r}")

    raw = secrets.token_urlsafe(48)
    prt = PasswordResetToken(
        token=raw,
        user_id=user_id,
        purpose=purpose,
        expires_at=now_local() + timedelta(days=ttl_days),
        created_by=created_by_id,
    )
    db.session.add(prt)
    db.session.flush()
    return prt


def get_token(token: str) -> PasswordResetToken:
    """
    Fetch a token row.  Raises TokenNotFound / TokenExpired / TokenAlreadyUsed
    so callers get precise error codes for the API response.
    """
    prt = PasswordResetToken.query.filter_by(token=token).first()
    if not prt:
        raise TokenNotFound("Token inválido o inexistente.")
    if prt.is_used:
        raise TokenAlreadyUsed("Este enlace ya fue utilizado.")
    if prt.is_expired:
        raise TokenExpired("Este enlace ha expirado. Solicita uno nuevo.")
    return prt


def consume_token(token: str, new_password: str) -> User:
    """
    Validate token, set new password, mark token used, clear must_change_password.

    Returns the updated User on success.  Caller is expected to commit.
    """
    prt = get_token(token)

    is_valid, msg = _validate_password_strength(new_password)
    if not is_valid:
        raise WeakPassword(msg)

    user = User.query.get(prt.user_id)
    if not user:
        raise TokenNotFound("Usuario asociado al token no existe.")

    user.password = generate_password_hash(new_password)
    user.must_change_password = False
    prt.used_at = now_local()

    UserHistoryService.log_action(
        user_id=user.id,
        admin_id=None,
        action='password_set_via_token',
        details={'purpose': prt.purpose, 'token_id': prt.id},
    )
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Local copy of auth_api.validate_password_strength to keep the service
    decoupled from the routes layer.
    """
    import re

    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r'[A-Z]', password):
        return False, "La contraseña debe contener al menos una letra mayúscula."
    if not re.search(r'[a-z]', password):
        return False, "La contraseña debe contener al menos una letra minúscula."
    if not re.search(r'\d', password):
        return False, "La contraseña debe contener al menos un número."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "La contraseña debe contener al menos un caracter especial (!@#$%^&*...)."
    return True, "OK"

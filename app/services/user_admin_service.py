"""
User administration and self-service profile writes.

Owns the queries and commits behind ``/api/v1/admin/users`` and
``/api/v1/users``. Framework-agnostic: the routes pass ids and values in.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, not_, or_

from app import db
from app.models.user import User
from app.models.user_program import UserProgram
from app.services import program_scope_service as scope_service
from app.services.errors import ConflictError, DomainError
from app.services.user_history_service import UserHistoryService


def rollback_session() -> None:
    """Discard pending changes after a failed operation."""
    db.session.rollback()


# ─── Búsqueda con alcance: un filtro sobre un campo prohibido es un oráculo ───
#
# La proyección al nivel reducido corre DESPUÉS de la consulta, así que no
# protege ningún campo que el WHERE ya haya tocado: si el número de control
# entra en el predicado, el simple hecho de que la fila vuelva —o no— responde
# «¿el número de control de esta persona contiene X?». El valor se filtra una
# adivinanza a la vez aunque jamás aparezca en el payload. Lo mismo vale para
# el orden (publica el valor relativo de la columna) y para cualquier conteo
# calculado sobre ese filtro.
#
# Regla: sólo se puede buscar sobre campos que el llamador puede VER en ESA
# fila. Como el alcance es por fila y el filtro es por consulta, el predicado
# se parte en dos ramas mutuamente excluyentes (dentro / fuera de alcance).

#: Columnas buscables cuando la fila es visible COMPLETA para el llamador.
_FULL_SEARCH_COLUMNS = (
    User.first_name,
    User.last_name,
    User.mother_last_name,
    User.email,
    User.username,       # para un estudiante ES el número de control
    User.control_number,
)

#: Columnas buscables cuando la fila sólo puede salir al nivel reducido.
#: Se derivan del catálogo del servicio para que no puedan divergir de la
#: lista blanca de la proyección.
_REDUCED_SEARCH_COLUMNS = tuple(
    getattr(User, name)
    for name in sorted(scope_service.CROSS_PROGRAM_SEARCHABLE_FIELDS)
)


def _search_clause(columns, search: str):
    """OR de ILIKE sobre `columns` — nunca se llama con columnas prohibidas."""
    pattern = f"%{search}%"
    return or_(*[column.ilike(pattern) for column in columns])


def _in_scope_clause(scope: set, caller_id: int):
    """
    Predicado SQL «esta fila está dentro del alcance del llamador».

    Espejo exacto en SQL de `scope_service.user_in_scope(..., allow_self=True)`
    para un alcance NO global: el propio usuario, más quien tenga un
    `UserProgram` en alguno de los programas del llamador. Una cuenta de staff
    (sin `UserProgram`) queda fuera, igual que en el servicio.

    Va como EXISTS y no como JOIN a propósito: se evalúa fila por fila dentro
    de la consulta —que es lo que permite aplicar un conjunto de campos
    distinto a cada fila— y no duplica al usuario con varias inscripciones.
    """
    clauses = [User.id == caller_id]
    if scope:
        clauses.append(User.user_program.any(UserProgram.program_id.in_(scope)))
    return or_(*clauses)


def search_users(*, page: int, per_page: int, role_filter, program_filter,
                 active_filter: str, search, scope, may_summarize: bool,
                 caller_id: int):
    """
    Build and run the scoped, filtered, paginated user listing.

    ``scope`` is the caller's accessible program ids (None = global).
    Returns ``(pagination, ignored_cross_program)`` where the second item lists
    the filters that were not applied to out-of-scope rows (see the notes above).
    """
    query = User.query

    # Filtro por programa — permitido sobre cualquier fila.
    if program_filter:
        query = query.filter(
            User.user_program.any(UserProgram.program_id == program_filter)
        )

    # Predicados que SÓLO pueden evaluarse sobre una fila visible completa.
    full_only = []
    ignored_cross_program = []

    if role_filter:
        full_only.append(User.role.has(name=role_filter))
        ignored_cross_program.append('role')

    if active_filter == 'true':
        full_only.append(User.is_active.is_(True))
        ignored_cross_program.append('active')
    elif active_filter == 'false':
        full_only.append(User.is_active.is_(False))
        ignored_cross_program.append('active')

    if search:
        full_only.append(_search_clause(_FULL_SEARCH_COLUMNS, search))

    if scope is None:
        # Alcance global: no hay filas ajenas, un solo conjunto de campos.
        ignored_cross_program = []
        if full_only:
            query = query.filter(and_(*full_only))
    else:
        in_scope = _in_scope_clause(scope, caller_id)
        full_branch = and_(in_scope, *full_only) if full_only else in_scope

        if may_summarize:
            # Dos ramas disjuntas por construcción (P / NOT P): la unión de
            # «dentro de alcance Y conjunto completo» con «fuera de alcance Y
            # conjunto reducido». La única rama que menciona control_number,
            # username, role o is_active va conjugada con `in_scope`, así que
            # ninguna fila puede entrar por un campo que el llamador no vería.
            reduced_branch = not_(in_scope)
            if search:
                reduced_branch = and_(
                    reduced_branch,
                    _search_clause(_REDUCED_SEARCH_COLUMNS, search),
                )
            query = query.filter(or_(full_branch, reduced_branch))
        else:
            # Sin nivel reducido las filas ajenas no se devolvían igual, pero
            # seguían contando en `pagination.total`: ese conteo también era un
            # oráculo. Ahora ni entran en la consulta.
            ignored_cross_program = []
            query = query.filter(full_branch)

    pagination = query.order_by(User.last_name, User.first_name).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return pagination, ignored_cross_program


def get_user_program(user_id: int) -> Optional[UserProgram]:
    """First UserProgram of the user (read-only), or None."""
    return UserProgram.query.filter_by(user_id=user_id).first()


# ─── Admin: basic info update ────────────────────────────────────────────────

class OwnEmailChangeForbidden(DomainError):
    """An administrator tried to change their own e-mail."""


class EmailAlreadyInUse(DomainError):
    """The new e-mail belongs to another account."""


def update_basic_info(user: User, values: dict, caller_id: int) -> dict:
    """
    Apply the already-validated ``values`` (any of first_name, last_name,
    mother_last_name, email) to ``user``, log the diff and commit.

    Changing the caller's own e-mail raises OwnEmailChangeForbidden and a
    duplicate raises EmailAlreadyInUse; both are raised BEFORE anything is
    written. Returns the changed-fields map.
    """
    changed_fields = {}
    pending = {}

    if 'first_name' in values:
        new_value = values['first_name']
        if new_value and new_value != user.first_name:
            changed_fields['first_name'] = {'old': user.first_name, 'new': new_value}
            pending['first_name'] = new_value

    if 'last_name' in values:
        new_value = values['last_name']
        if new_value and new_value != user.last_name:
            changed_fields['last_name'] = {'old': user.last_name, 'new': new_value}
            pending['last_name'] = new_value

    if 'mother_last_name' in values:
        new_value = values['mother_last_name']
        if new_value != user.mother_last_name:
            changed_fields['mother_last_name'] = {
                'old': user.mother_last_name, 'new': new_value}
            pending['mother_last_name'] = new_value

    if 'email' in values:
        new_value = values['email']
        if new_value and new_value != user.email:
            # Nadie cambia su propio correo desde la consola de administración.
            #
            # El correo es el canal de recuperación de la cuenta: es a donde
            # viaja el enlace de un solo uso de `reset_password` y la única vía
            # de vuelta cuando se pierde la contraseña. Quien puede reescribirlo
            # sobre sí mismo puede apuntar su propia recuperación a un buzón
            # ajeno a la institución y conservar la entrada después de causar
            # baja, sin que nadie más intervenga. Por eso `PATCH /users/me`
            # tampoco lo expone: el nombre es autoservicio, el correo no.
            #
            # La condición cuelga de "el valor cambia" a propósito: el modal
            # envía siempre los cuatro campos precargados, y rechazar por la
            # simple presencia de 'email' impediría a un administrador
            # corregirse una tilde del nombre.
            if user.id == caller_id:
                raise OwnEmailChangeForbidden(
                    "No puedes cambiar tu propio correo: es el canal de "
                    "recuperación de tu cuenta. Pídeselo al jefe de posgrado."
                )
            existing = User.query.filter(
                User.email == new_value, User.id != user.id
            ).first()
            if existing:
                raise EmailAlreadyInUse("El email ya está en uso.")
            changed_fields['email'] = {'old': user.email, 'new': new_value}
            pending['email'] = new_value

    for attr, val in pending.items():
        setattr(user, attr, val)

    if changed_fields:
        UserHistoryService.log_basic_info_update(
            user_id=user.id, changed_fields=changed_fields)

    db.session.commit()
    return changed_fields


# ─── Admin: reset password, toggle, control number, delete, social service ───

def issue_admin_password_reset(user_id: int, admin_id: int) -> dict:
    """
    Issue an administrative reset link and commit. On a domain failure
    (TokenNotFound, MissingEmail) the session is rolled back and it re-raises.
    """
    from app.services import password_reset_service as prs
    try:
        result = prs.issue_admin_reset(user_id=user_id, admin_id=admin_id)
    except (prs.TokenNotFound, prs.MissingEmail):
        db.session.rollback()
        raise
    db.session.commit()
    return result


def toggle_user_active(user: User) -> bool:
    """Flip ``is_active``, log it and commit. Returns the new state."""
    user.is_active = not user.is_active
    UserHistoryService.log_user_activation(user_id=user.id, is_active=user.is_active)
    db.session.commit()
    return user.is_active


def control_number_exists(control_number: str) -> bool:
    """True when any user already holds this control number (global check)."""
    return User.query.filter(User.control_number == control_number).first() is not None


def assign_control_number_as_admin(*, user_id: int, program_id: int,
                                   control_number: str, admin_id: int):
    """Administrative control-number transition; rolls back on any failure."""
    from app.services import acceptance_service as svc
    try:
        return svc.assign_control_number_admin(
            user_id=user_id,
            program_id=program_id,
            control_number=control_number,
            admin_id=admin_id,
        )
    except Exception:
        db.session.rollback()
        raise


class UserOnThesisCommittee(ConflictError):
    """The user sits on a tutorial committee or an examination board (409)."""


def thesis_memberships_count(user_id: int) -> int:
    """How many theses list `user_id` on their committee or board."""
    from sqlalchemy import func
    from app.models.thesis import ThesisMember

    return (db.session.query(func.count(func.distinct(ThesisMember.thesis_id)))
            .filter(ThesisMember.user_id == user_id).scalar() or 0)


def delete_user_account(user: User, user_name: str) -> None:
    """
    Log the deletion, commit, delete the row and commit.

    Refused before any write when the user sits on a thesis committee or
    board: `thesis_member.user_id` is RESTRICT, and the coordination must
    replace the person first.
    """
    theses = thesis_memberships_count(user.id)
    if theses:
        raise UserOnThesisCommittee(
            f'No se puede eliminar: integra el comité/sínodo de {theses} tesis. '
            'Reemplázalo primero.')
    UserHistoryService.log_user_deletion(user_id=user.id, user_name=user_name)
    db.session.commit()
    db.session.delete(user)
    db.session.commit()


def create_social_service_account(*, creator_id: int, user_data: dict,
                                  permissions: list, program_ids, expires_at,
                                  raw_expires_at):
    """
    Create the social-service user with its delegations, log it and commit.
    Rolls back and re-raises on any failure (the route maps the exception).
    Returns ``(new_user, delegations, email_sent)``.
    """
    from app.services.permission_service import create_social_service_user
    try:
        new_user, delegations, email_sent = create_social_service_user(
            creator_id=creator_id,
            user_data=user_data,
            permissions_to_delegate=permissions,
            program_ids=program_ids,
            expires_at=expires_at,
        )
        UserHistoryService.log_action(
            user_id=new_user.id,
            admin_id=creator_id,
            action='social_service_created',
            details={
                'permissions_delegated': permissions,
                'program_ids': program_ids or [],
                'expires_at': raw_expires_at,
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return new_user, delegations, email_sent


# ─── Self-service profile ────────────────────────────────────────────────────

_PROFILE_TEXT_FIELDS = (
    'phone', 'mobile_phone', 'address', 'curp', 'rfc', 'birth_place',
    'cedula_profesional', 'nss', 'emergency_contact_name',
    'emergency_contact_phone', 'emergency_contact_relationship',
)


def complete_profile(user: User, fields: dict, birth_date, logger=None):
    """
    Write the profile fields, refresh the completion flag and commit.

    ``fields`` maps each name in ``_PROFILE_TEXT_FIELDS`` to its sanitised
    value (or None). ``birth_date`` is a date or None (None leaves it as is).
    Returns ``(was_complete_before, is_complete_now)``. The first completion is
    recorded in the history (best effort).
    """
    for name in _PROFILE_TEXT_FIELDS:
        setattr(user, name, fields.get(name))
    if birth_date:
        user.birth_date = birth_date

    was_complete_before = user.profile_completed
    is_complete_now = user.update_profile_completion_status()
    db.session.commit()

    if not was_complete_before and is_complete_now:
        try:
            UserHistoryService.log_profile_completion(user_id=user.id)
            db.session.commit()
        except Exception as e:  # noqa: BLE001 - history is best-effort here
            if logger is not None:
                logger.error(f"Error al registrar completado de perfil en historial: {e}")

    return was_complete_before, is_complete_now


def update_own_basic_info(user: User, *, first_name, last_name,
                          mother_last_name, scolarship_type) -> None:
    """Write the self-service name fields, refresh completion and commit."""
    user.first_name = first_name
    user.last_name = last_name
    user.mother_last_name = mother_last_name
    if scolarship_type is not None:
        user.scolarship_type = scolarship_type
    user.update_profile_completion_status()
    db.session.commit()

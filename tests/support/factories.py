"""
Model factories shared by new tests.

Permissions are synthetic on purpose: the real catalog and its role mapping
live only in `database/` on the server (never in git), so a test grants exactly
the codenames it exercises and nothing else.
"""

from datetime import date, timedelta
from itertools import count

from app import db
from app.models.academic_period import AcademicPeriod
from app.models.permission import Permission
from app.models.program import Program
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_program import UserProgram

ROLE_NAMES = ('applicant', 'program_admin', 'postgraduate_admin', 'social_service', 'student')
DEFAULT_PASSWORD = 'Test1234!'

_seq = count(1)


def _next() -> int:
    return next(_seq)


def get_or_create_role(name: str) -> Role:
    role = Role.query.filter_by(name=name).first()
    if role is None:
        role = Role(name=name, description=f'Rol de prueba: {name}')
        db.session.add(role)
        db.session.flush()
    return role


def get_or_create_permission(codename: str) -> Permission:
    perm = Permission.query.filter_by(codename=codename).first()
    if perm is None:
        parts = codename.split('.')
        perm = Permission(
            codename=codename,
            display_name=codename,
            resource=parts[0],
            perm_type=parts[1] if len(parts) > 1 else 'api',
            action='.'.join(parts[2:]) or 'action',
        )
        perm.is_active = True
        db.session.add(perm)
        db.session.flush()
    return perm


def grant(role: Role, *codenames: str) -> None:
    """Map each codename to the role (idempotent)."""
    for codename in codenames:
        perm = get_or_create_permission(codename)
        exists = RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first()
        if exists is None:
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.session.flush()


def make_user(role_name: str = 'applicant', *, username: str | None = None,
              password: str = DEFAULT_PASSWORD, must_change_password: bool = False,
              is_active: bool = True, **fields) -> User:
    role = get_or_create_role(role_name)
    n = _next()
    username = username or f'{role_name}_{n}'
    user = User(
        first_name=fields.pop('first_name', 'Prueba'),
        last_name=fields.pop('last_name', 'Usuario'),
        mother_last_name=fields.pop('mother_last_name', ''),
        username=username,
        password=password,
        email=fields.pop('email', f'{username}@siiap.test'),
        is_internal=fields.pop('is_internal', role_name != 'applicant'),
        role_id=role.id,
        must_change_password=must_change_password,
    )
    user.is_active = is_active
    for key, value in fields.items():
        setattr(user, key, value)
    db.session.add(user)
    db.session.flush()
    return user


def make_program(coordinator: User | None = None, **fields) -> Program:
    coordinator = coordinator or make_user('program_admin')
    n = _next()
    program = Program(
        name=fields.pop('name', f'Programa de prueba {n}'),
        description=fields.pop('description', 'Descripción de prueba'),
        coordinator_id=coordinator.id,
        slug=fields.pop('slug', f'programa-{n}'),
        is_active=fields.pop('is_active', True),
        **fields,
    )
    db.session.add(program)
    db.session.flush()
    return program


def enroll(user: User, program: Program, admission_status: str = 'in_progress') -> UserProgram:
    link = UserProgram(user_id=user.id, program_id=program.id, admission_status=admission_status)
    db.session.add(link)
    db.session.flush()
    return link


def make_academic_period(code: str | None = None, *, is_active: bool = True) -> AcademicPeriod:
    today = date.today()
    code = code or f'2{_next():04d}'
    period = AcademicPeriod(
        code=code,
        name=f'Periodo {code}',
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=150),
        admission_start_date=today - timedelta(days=60),
        admission_end_date=today + timedelta(days=30),
        is_active=is_active,
        status='active' if is_active else 'upcoming',
    )
    db.session.add(period)
    db.session.flush()
    return period

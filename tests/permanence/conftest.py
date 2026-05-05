# tests/permanence/conftest.py
"""Helpers for permanence tests."""

import tempfile
from pathlib import Path
from datetime import date, timedelta

from app import db
from app.models.role import Role
from app.models.user import User
from app.models.program import Program
from app.models.academic_period import AcademicPeriod
from app.models.user_program import UserProgram
from app.models.semester_enrollment import SemesterEnrollment


def make_test_config() -> dict:
    p = Path(tempfile.mkdtemp())
    return {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'CELERY_BROKER_URL': 'memory://',
        'CELERY_RESULT_BACKEND': 'cache+memory://',
        'SERVER_NAME': 'localhost.test',
        'PUBLIC_BASE_URL': 'http://localhost.test',
        'PREFERRED_URL_SCHEME': 'http',
        'UPLOAD_FOLDER': p,
        'AVATAR_FOLDER': p / 'avatars',
        'USER_DOCS_FOLDER': p / 'documents',
        'EVENTS_FOLDER': p / 'events',
        'TEMPLATE_STORE': p / 'templates_sys',
    }


def make_role(name: str) -> Role:
    r = Role(name=name, description=f'Role {name}')
    db.session.add(r)
    db.session.flush()
    return r


def make_user(role: Role, suffix: str = '') -> User:
    username = f'user_{role.name}{suffix}'
    u = User(
        first_name='Test',
        last_name='User',
        mother_last_name='',
        username=username,
        password='Test1234!',
        email=f'{username}@siiap.test',
        is_internal=True,
        role_id=role.id,
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    return u


def make_program(coordinator: User, slug: str = 'test-prog') -> Program:
    p = Program(
        name='Test Program',
        description='Test',
        coordinator_id=coordinator.id,
        slug=slug,
        is_active=True,
    )
    db.session.add(p)
    db.session.flush()
    return p


def make_period(code: str, start: date, end: date | None = None,
                is_active: bool = False) -> AcademicPeriod:
    end = end or (start + timedelta(days=120))
    ap = AcademicPeriod(
        code=code,
        name=f'Period {code}',
        start_date=start,
        end_date=end,
        admission_start_date=start - timedelta(days=90),
        admission_end_date=start - timedelta(days=15),
        is_active=is_active,
        status='active' if is_active else 'completed',
    )
    db.session.add(ap)
    db.session.flush()
    return ap


def make_user_program(user: User, program: Program, period: AcademicPeriod,
                      semester: int = 1) -> UserProgram:
    up = UserProgram(
        user_id=user.id,
        program_id=program.id,
        admission_period_id=period.id,
        admission_status='enrolled',
        current_semester=semester,
    )
    db.session.add(up)
    db.session.flush()
    return up


def make_enrollment(up: UserProgram, period: AcademicPeriod, semester_number: int,
                    status: str = 'active', confirmed: bool = True) -> SemesterEnrollment:
    se = SemesterEnrollment(
        user_program_id=up.id,
        academic_period_id=period.id,
        semester_number=semester_number,
        status=status,
        enrollment_confirmed=confirmed,
    )
    db.session.add(se)
    db.session.flush()
    return se

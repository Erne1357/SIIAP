# tests/acceptance/conftest.py
import tempfile
from pathlib import Path
from datetime import date, timedelta

from app import db
from app.models.role import Role
from app.models.user import User
from app.models.program import Program
from app.models.academic_period import AcademicPeriod
from app.models.user_program import UserProgram


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
        'ALLOWED_DOC_EXT': {'pdf', 'doc', 'docx'},
        'ALLOWED_IMAGE_EXT': {'jpg', 'jpeg', 'png', 'webp'},
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


def make_period(code: str = '20263', is_active: bool = True) -> AcademicPeriod:
    today = date.today()
    ap = AcademicPeriod(
        code=code,
        name=f'Period {code}',
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=120),
        admission_start_date=today - timedelta(days=60),
        admission_end_date=today + timedelta(days=15),
        is_active=is_active,
        status='active' if is_active else 'completed',
    )
    db.session.add(ap)
    db.session.flush()
    return ap


def make_accepted_user_program(user: User, program: Program,
                                period: AcademicPeriod) -> UserProgram:
    up = UserProgram(
        user_id=user.id,
        program_id=program.id,
        admission_period_id=period.id,
        admission_status='accepted',
    )
    db.session.add(up)
    db.session.flush()
    return up

# tests/purge/conftest.py
"""
Fixtures shared across purge tests.

Sets up:
- In-memory SQLite app with a temp directory that also acts as INSTANCE_DIR
  (so that _BACKUPS_DIR in the service resolves to a writable temp location).
- All 5 roles + the 3 purge permissions mapped to postgraduate_admin.
- One program with a minimal Phase/Step/Archive/ProgramStep tree.
- Helper factories for applicants in various admission states.
- Actual files on disk so ZIP-content and confirm-purge tests can exercise
  the os.remove path.
"""

import csv
import io
import json
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import create_app, db
from app.models.role import Role
from app.models.user import User
from app.models.program import Program
from app.models.academic_period import AcademicPeriod
from app.models.user_program import UserProgram
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.phase import Phase
from app.models.step import Step
from app.models.archive import Archive
from app.models.program_step import ProgramStep
from app.models.submission import Submission
from app.models.purge_run import PurgeRun
from app.models.retention_policy import RetentionPolicy


# ---------------------------------------------------------------------------
# App + DB lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture(scope='function')
def app(monkeypatch):
    """
    Flask app with SQLite in-memory DB plus a temp directory that serves both
    as UPLOAD_FOLDER and as the base for the backup directory.

    We monkeypatch app.services.applicant_archive_service._BACKUPS_DIR so the
    service writes ZIPs into the temp tree rather than instance/backups/purge.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix='siiap_purge_test_'))
    backups_dir = tmp_root / 'backups' / 'purge'
    backups_dir.mkdir(parents=True, exist_ok=True)

    cfg = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'purge-test-secret',
        'WTF_CSRF_ENABLED': False,
        'CELERY_BROKER_URL': 'memory://',
        'CELERY_RESULT_BACKEND': 'cache+memory://',
        'SERVER_NAME': 'localhost.test',
        'PUBLIC_BASE_URL': 'http://localhost.test',
        'PREFERRED_URL_SCHEME': 'http',
        'MAX_CONTENT_LENGTH': 10 * 1024 * 1024,
        'ALLOWED_DOC_EXT': {'pdf', 'doc', 'docx'},
        'UPLOAD_FOLDER': tmp_root,
        'AVATAR_FOLDER': tmp_root / 'avatars',
        'USER_DOCS_FOLDER': tmp_root / 'documents',
        'EVENTS_FOLDER': tmp_root / 'events',
        'TEMPLATE_STORE': tmp_root / 'templates_sys',
    }

    application = create_app(test_config=cfg)

    # Redirect the service's backup directory to our temp tree.
    import app.services.applicant_archive_service as svc_mod
    monkeypatch.setattr(svc_mod, '_BACKUPS_DIR', backups_dir)

    # Also patch _archive_path_for and _ensure_backups_dir to use the new dir.
    def _patched_ensure():
        backups_dir.mkdir(parents=True, exist_ok=True)
        return backups_dir

    def _patched_archive_path(run_id: str) -> Path:
        return _patched_ensure() / f'{run_id}.zip'

    monkeypatch.setattr(svc_mod, '_ensure_backups_dir', _patched_ensure)
    monkeypatch.setattr(svc_mod, '_archive_path_for', _patched_archive_path)

    # Patch Config.UPLOAD_FOLDER used by the service for file resolution.
    # The service reads Config.UPLOAD_FOLDER at call time (not import time) via
    # Path(Config.UPLOAD_FOLDER), so patching the class attribute is enough.
    import app.config as config_mod
    monkeypatch.setattr(config_mod.Config, 'UPLOAD_FOLDER', tmp_root)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def upload_root(app):
    """Returns the Path used as UPLOAD_FOLDER (tmp root)."""
    return Path(app.config['UPLOAD_FOLDER'])


@pytest.fixture
def backups_dir(app):
    """Returns the monkeypatched backups dir."""
    import app.services.applicant_archive_service as svc_mod
    return svc_mod._BACKUPS_DIR


# ---------------------------------------------------------------------------
# Roles + permissions
# ---------------------------------------------------------------------------

@pytest.fixture
def roles(app):
    out = {}
    for name in ('applicant', 'program_admin', 'postgraduate_admin',
                 'social_service', 'student'):
        r = Role(name=name, description=f'Test role: {name}')
        db.session.add(r)
        out[name] = r
    db.session.flush()
    return out


def _make_perm(codename: str, role: Role) -> None:
    parts = codename.split('.')
    perm = Permission.query.filter_by(codename=codename).first()
    if not perm:
        perm = Permission(
            codename=codename,
            display_name=codename,
            resource=parts[0],
            perm_type=parts[1] if len(parts) > 1 else 'api',
            action='.'.join(parts[2:]) if len(parts) > 2 else 'action',
        )
        db.session.add(perm)
        db.session.flush()
    if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
        db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.session.flush()


@pytest.fixture
def permissions(app, roles):
    """Seed the three purge permissions onto postgraduate_admin."""
    _make_perm('admin.api.purge_view', roles['postgraduate_admin'])
    _make_perm('admin.api.purge_archive', roles['postgraduate_admin'])
    _make_perm('admin.api.purge_confirm', roles['postgraduate_admin'])
    return True


# ---------------------------------------------------------------------------
# Academic periods
# ---------------------------------------------------------------------------

@pytest.fixture
def periods(app):
    """
    Four sequential periods:
      P0 = 20251  (2+ closed periods ago)
      P1 = 20253  (1 closed period ago)
      P2 = 20263  (current/active)
      P3 = 20271  (future/upcoming)
    """
    from datetime import datetime
    seq = [
        # P0 (20251) — very old; both P1 and P2 admission windows are in the past
        # so _periods_elapsed_since('20251') returns >= 2.
        # P3 (20271) — future admission window, so it yields 0 elapsed periods
        # after itself (used by test_excludes_recent_ups).
        ('20251', '2020-01-15', '2020-06-15', False, 'completed'),
        ('20253', '2021-08-15', '2021-12-15', False, 'completed'),
        ('20263', '2023-01-15', '2023-06-15', True,  'active'),
        ('20271', '2030-01-15', '2030-06-15', False, 'upcoming'),
    ]
    out = {}
    for code, sd, ed, active, status in seq:
        ap = AcademicPeriod(
            code=code,
            name=f'Period {code}',
            start_date=date.fromisoformat(sd),
            end_date=date.fromisoformat(ed),
            admission_start_date=date.fromisoformat(sd) - timedelta(days=60),
            admission_end_date=date.fromisoformat(sd) - timedelta(days=10),
            is_active=active,
            status=status,
        )
        db.session.add(ap)
        db.session.flush()
        out[code] = ap
    return out


# ---------------------------------------------------------------------------
# Program + structural fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def postgrad_admin(app, roles):
    u = User(
        first_name='Postgrad', last_name='Admin', mother_last_name='',
        username='purge_postgrad', password='Test1234!',
        email='purge_postgrad@test.local', is_internal=True,
        role_id=roles['postgraduate_admin'].id, must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture
def applicant_user_factory(app, roles):
    """Factory: returns a plain applicant User."""
    counter = [0]

    def _make(suffix=None):
        counter[0] += 1
        s = suffix or f'appl{counter[0]}'
        u = User(
            first_name='Appl', last_name=f'Test{s}', mother_last_name='',
            username=f'appl_{s}', password='Test1234!',
            email=f'appl_{s}@test.local', is_internal=False,
            role_id=roles['applicant'].id, must_change_password=False,
        )
        db.session.add(u)
        db.session.flush()
        return u

    return _make


@pytest.fixture
def coordinator(app, roles):
    u = User(
        first_name='Coord', last_name='Test', mother_last_name='',
        username='purge_coord', password='Test1234!',
        email='purge_coord@test.local', is_internal=True,
        role_id=roles['program_admin'].id, must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture
def program(app, coordinator):
    p = Program(
        name='Purge MII', description='Test', coordinator_id=coordinator.id,
        slug='purge-mii', is_active=True, duration_semesters=4,
    )
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def program_structure(app, program):
    """Minimal Phase/Step/Archive/ProgramStep tree for the program."""
    phase = Phase(name='admission', description='Admisión')
    db.session.add(phase)
    db.session.flush()

    step = Step(name='Documentos Admisión', description='Step admisión', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()

    archive = Archive(
        name='Constancia', description='constancia', file_path='',
        step_id=step.id, is_downloadable=False, is_uploadable=True,
    )
    db.session.add(archive)
    db.session.flush()
    archive.is_active = True
    db.session.flush()

    ps = ProgramStep(program_id=program.id, step_id=step.id, sequence=1)
    db.session.add(ps)
    db.session.flush()

    return {'phase': phase, 'step': step, 'archive': archive, 'ps': ps}


# ---------------------------------------------------------------------------
# Helpers: create UserProgram + optional Submission with a real file
# ---------------------------------------------------------------------------

def _write_fake_file(upload_root: Path, user_id: int, filename: str = 'doc.pdf') -> str:
    """
    Writes a small fake PDF to upload_root/user_<id>/<filename>.
    Returns the relative path (as stored in Submission.file_path).
    """
    user_dir = upload_root / f'user_{user_id}'
    user_dir.mkdir(parents=True, exist_ok=True)
    rel = f'user_{user_id}/{filename}'
    full = upload_root / rel
    full.write_bytes(b'%PDF-1.4 fake content for testing')
    return rel


@pytest.fixture
def make_applicant(app, program, program_structure, periods, upload_root):
    """
    Factory that creates a UserProgram with given admission_status.

    Signature:
        make_applicant(user, status, period_code='20251', with_file=True)
    Returns: (UserProgram, Submission|None)
    """
    def _make(user: User, status: str = 'expired',
              period_code: str = '20251', with_file: bool = True):
        ap = AcademicPeriod.query.filter_by(code=period_code).first()
        up = UserProgram(
            user_id=user.id,
            program_id=program.id,
            admission_status=status,
            admission_period_id=ap.id if ap else None,
            current_semester=None,
            has_conacyt_scholarship=False,
        )
        db.session.add(up)
        db.session.flush()

        sub = None
        if with_file:
            rel_path = _write_fake_file(upload_root, user.id)
            sub = Submission(
                file_path=rel_path,
                status='approved',
                user_id=user.id,
                archive_id=program_structure['archive'].id,
                program_step_id=program_structure['ps'].id,
                semester=1,
            )
            db.session.add(sub)
            db.session.flush()

        return up, sub

    return _make


# ---------------------------------------------------------------------------
# Login helper (mirrors transition/test_api.py)
# ---------------------------------------------------------------------------

def login(client, user, password='Test1234!'):
    resp = client.post('/api/v1/auth/login',
                       json={'username': user.username, 'password': password})
    try:
        token = resp.get_json().get('data', {}).get('csrf_token', '')
    except Exception:
        token = ''
    return token


def csrf(token: str) -> dict:
    return {'X-CSRFToken': token}

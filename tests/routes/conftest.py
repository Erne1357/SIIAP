"""Module-scoped app + seed shared by the route-coverage matrices.

One app per test module (hundreds of cases would otherwise rebuild the schema
for each). Roles are synthetic; permissions are granted explicitly by the
module that needs them.
"""

import pytest

from app import create_app, db
from tests.support.factories import (
    ROLE_NAMES, enroll, get_or_create_role, make_academic_period, make_program, make_user,
)
from tests.support.fixtures import login_as, make_test_config, prepare_database, release_database


@pytest.fixture(scope='module')
def routes_app(tmp_path_factory):
    app = create_app(make_test_config(tmp_path_factory.mktemp('routes')))
    with app.app_context():
        prepare_database()
        for name in ROLE_NAMES:
            get_or_create_role(name)
        db.session.commit()
    # No app context is held open while tests run: Flask-Login and the
    # permission cache both live on `g`, which an outer context would share
    # across requests (a logout would then log out every later request).
    yield app
    with app.app_context():
        release_database()


@pytest.fixture(scope='module')
def role_users(routes_app):
    """{role_name: user_id} — one active user per role, zero grants."""
    ids = {}
    with routes_app.app_context():
        for name in ROLE_NAMES:
            ids[name] = make_user(name).id
        db.session.commit()
    return ids


@pytest.fixture(scope='module')
def dataset(routes_app):
    """Minimal real data: coordinator, program, active period, enrolled applicant."""
    with routes_app.app_context():
        coordinator = make_user('program_admin')
        program = make_program(coordinator)
        period = make_academic_period()
        applicant = make_user('applicant')
        link = enroll(applicant, program)
        db.session.commit()
        return {
            'coordinator_id': coordinator.id,
            'program_id': program.id,
            'program_slug': program.slug,
            'period_id': period.id,
            'applicant_id': applicant.id,
            'applicant_uuid': str(applicant.uuid),
            'user_program_id': link.id,
        }


def client_for(app, user_id):
    """Fresh logged-in ApiClient for the user id (re-queried: sessions are reused)."""
    from app.models.user import User
    with app.app_context():
        user = db.session.get(User, user_id)
        return login_as(app.test_client(), user)

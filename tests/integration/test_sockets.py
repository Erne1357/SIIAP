"""Socket.IO connect rooms and join_deliberation authorisation (app/sockets/core.py)."""

import pytest

from app import db
from app.extensions import socketio
from app.models.user_permission import UserPermission
from tests.integration.auth_support import (  # noqa: F401
    ensure_permission, fake_redis, grant_codename, isolate_globals,
)
from tests.support.factories import enroll, make_program, make_user

GLOBAL = 'academic_periods.api.create'
COORD_VIEW = 'coordinator.page.view'
DELIB = 'deliberation.api.list_applicants'


class _CookieJarShim:
    """Flask-SocketIO 5.3 calls `client.cookie_jar.inject_wsgi()`, gone since Werkzeug 2.3."""

    def __init__(self, flask_client):
        self._client = flask_client
        self.cookie_jar = self

    def inject_wsgi(self, environ):
        header = '; '.join(c._to_request_header() for c in self._client._cookies.values())
        if header:
            environ['HTTP_COOKIE'] = header


def connect(app, api_client):
    """Open a socket sharing the logged-in HTTP client's session cookie."""
    raw = getattr(api_client, 'raw', api_client)
    return socketio.test_client(app, flask_test_client=_CookieJarShim(raw))


def receives(sio_client, room):
    """True when this client's socket currently sits in `room`.

    Membership is read from the server's room manager: the Flask-SocketIO 5.3 test
    client cannot capture server-side emits with python-socketio 5.17.
    """
    manager = socketio.server.manager
    sid = manager.sid_from_eio_sid(sio_client.eio_sid, '/')
    return sid in manager.rooms.get('/', {}).get(room, {})


def join_delib(sio_client, program_id):
    return sio_client.emit('join_deliberation', {'program_id': program_id}, callback=True)


# ── connect ─────────────────────────────────────────────────────────────────

class TestConnect:
    def test_anonymous_is_rejected(self, app, client):
        assert connect(app, client).is_connected() is False

    def test_anonymous_without_http_client_is_rejected(self, app):
        assert socketio.test_client(app).is_connected() is False

    def test_authenticated_is_accepted(self, app, login):
        sio = connect(app, login(make_user('student')))
        assert sio.is_connected() is True

    def test_expired_session_cookie_for_deactivated_user_rejected(self, app, login):
        user = make_user('student')
        client = login(user)
        user.is_active = False
        db.session.commit()
        assert connect(app, client).is_connected() is False

    def test_malformed_user_id_rejected(self, app, client):
        with client.session_transaction() as sess:
            sess['_user_id'] = 'garbage'
        assert connect(app, client).is_connected() is False

    def test_disconnect_is_clean(self, app, login):
        sio = connect(app, login(make_user('student')))
        sio.disconnect()
        assert sio.is_connected() is False

    def test_two_connections_same_user(self, app, login):
        client = login(make_user('student'))
        a, b = connect(app, client), connect(app, client)
        assert a.is_connected() and b.is_connected()


# ── automatic rooms ─────────────────────────────────────────────────────────

class TestRooms:
    def test_joins_own_user_room(self, app, login):
        user = make_user('student')
        sio = connect(app, login(user))
        assert receives(sio, f'user:{user.id}')

    def test_does_not_join_other_users_room(self, app, login):
        user, other = make_user('student'), make_user('student')
        sio = connect(app, login(user))
        assert not receives(sio, f'user:{other.id}')

    def test_joins_role_room(self, app, login):
        sio = connect(app, login(make_user('student')))
        assert receives(sio, 'role:student')

    def test_does_not_join_other_role_rooms(self, app, login):
        sio = connect(app, login(make_user('student')))
        assert not receives(sio, 'role:program_admin')
        assert not receives(sio, 'role:postgraduate_admin')

    def test_non_coordinator_not_in_coordinator_rooms(self, app, login):
        sio = connect(app, login(make_user('applicant')))
        assert not receives(sio, 'role:coordinator')
        assert not receives(sio, 'coordinator:programs:all')

    def test_coordinator_joins_functional_room(self, app, login):
        grant_codename('program_admin', COORD_VIEW)
        sio = connect(app, login(make_user('program_admin')))
        assert receives(sio, 'role:coordinator')

    def test_coordinator_joins_own_program_room_only(self, app, login):
        grant_codename('program_admin', COORD_VIEW)
        user = make_user('program_admin')
        mine, theirs = make_program(user), make_program()
        sio = connect(app, login(user))
        assert receives(sio, f'coordinator:program:{mine.id}')
        assert not receives(sio, f'coordinator:program:{theirs.id}')
        assert not receives(sio, 'coordinator:programs:all')

    def test_coordinator_without_programs_gets_no_program_rooms(self, app, login):
        grant_codename('program_admin', COORD_VIEW)
        other = make_program()
        sio = connect(app, login(make_user('program_admin')))
        assert not receives(sio, f'coordinator:program:{other.id}')

    def test_global_admin_joins_catch_all_room(self, app, login):
        grant_codename('postgraduate_admin', COORD_VIEW, GLOBAL)
        program = make_program()
        sio = connect(app, login(make_user('postgraduate_admin')))
        assert receives(sio, 'coordinator:programs:all')
        assert not receives(sio, f'coordinator:program:{program.id}')

    def test_global_admin_in_role_coordinator(self, app, login):
        grant_codename('postgraduate_admin', COORD_VIEW, GLOBAL)
        sio = connect(app, login(make_user('postgraduate_admin')))
        assert receives(sio, 'role:coordinator')

    def test_scoped_delegation_gives_program_room(self, app, login):
        grant_codename('social_service', COORD_VIEW)
        user = make_user('social_service')
        program = make_program()
        perm = ensure_permission('some.api.work')
        db.session.add(UserPermission(user_id=user.id, permission_id=perm.id, program_id=program.id,
                                      granted_by=program.coordinator_id))
        db.session.commit()
        sio = connect(app, login(user))
        assert receives(sio, f'coordinator:program:{program.id}')

    def test_scope_failure_does_not_reject_connection(self, app, login, monkeypatch):
        grant_codename('program_admin', COORD_VIEW)
        user = make_user('program_admin')
        client = login(user)

        def boom(self):
            raise RuntimeError('scope lookup failed')
        monkeypatch.setattr(type(user), 'get_accessible_program_ids', boom)
        sio = connect(app, client)
        assert sio.is_connected()
        assert receives(sio, f'user:{user.id}')


# ── join_deliberation ───────────────────────────────────────────────────────

class TestJoinDeliberation:
    def test_coordinator_with_permission_and_scope_joins(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        program = make_program(user)
        sio = connect(app, login(user))
        assert join_delib(sio, program.id) is True
        assert receives(sio, f'deliberation:{program.id}')

    def test_not_in_room_before_joining(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        program = make_program(user)
        sio = connect(app, login(user))
        assert not receives(sio, f'deliberation:{program.id}')

    def test_applicant_without_permission_denied(self, app, login):
        program = make_program()
        user = make_user('applicant')
        enroll(user, program)
        sio = connect(app, login(user))
        assert join_delib(sio, program.id) is False
        assert not receives(sio, f'deliberation:{program.id}')

    def test_permission_without_scope_denied(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        make_program(user)
        foreign = make_program()
        sio = connect(app, login(user))
        assert join_delib(sio, foreign.id) is False
        assert not receives(sio, f'deliberation:{foreign.id}')

    def test_scope_without_permission_denied(self, app, login):
        grant_codename('program_admin', COORD_VIEW)
        user = make_user('program_admin')
        program = make_program(user)
        sio = connect(app, login(user))
        assert join_delib(sio, program.id) is False
        assert not receives(sio, f'deliberation:{program.id}')

    def test_global_admin_joins_any_program(self, app, login):
        grant_codename('postgraduate_admin', COORD_VIEW, GLOBAL, DELIB)
        program = make_program()
        sio = connect(app, login(make_user('postgraduate_admin')))
        assert join_delib(sio, program.id) is True
        assert receives(sio, f'deliberation:{program.id}')

    def test_string_program_id_is_coerced(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        program = make_program(user)
        sio = connect(app, login(user))
        assert join_delib(sio, str(program.id)) is True

    @pytest.mark.parametrize('payload', [None, [], 'x', 5, {}, {'program_id': None},
                                         {'program_id': 'abc'}, {'program_id': ''},
                                         {'program_id': [1]}, {'program_id': {'a': 1}}])
    def test_malformed_payload_denied(self, app, login, payload):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        make_program(user)
        sio = connect(app, login(user))
        assert sio.emit('join_deliberation', payload, callback=True) is False

    def test_malformed_payload_does_not_disconnect(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        sio = connect(app, login(make_user('program_admin')))
        sio.emit('join_deliberation', {'program_id': 'abc'})
        assert sio.is_connected()

    def test_denied_join_does_not_disconnect(self, app, login):
        sio = connect(app, login(make_user('applicant')))
        join_delib(sio, 1)
        assert sio.is_connected()

    def test_nonexistent_program_denied_for_scoped_user(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        make_program(user)
        sio = connect(app, login(user))
        assert join_delib(sio, 99999) is False

    def test_negative_program_id_denied(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        make_program(user)
        sio = connect(app, login(user))
        assert join_delib(sio, -1) is False

    def test_join_does_not_grant_other_program_rooms(self, app, login):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        mine, other = make_program(user), make_program()
        sio = connect(app, login(user))
        join_delib(sio, mine.id)
        assert not receives(sio, f'deliberation:{other.id}')

    def test_delegated_program_scope_allows_join(self, app, login):
        grant_codename('social_service', COORD_VIEW, DELIB)
        user = make_user('social_service')
        program = make_program()
        perm = ensure_permission('some.api.work')
        db.session.add(UserPermission(user_id=user.id, permission_id=perm.id, program_id=program.id,
                                      granted_by=program.coordinator_id))
        db.session.commit()
        sio = connect(app, login(user))
        assert join_delib(sio, program.id) is True

    def test_scope_error_fails_closed(self, app, login, monkeypatch):
        grant_codename('program_admin', COORD_VIEW, DELIB)
        user = make_user('program_admin')
        program = make_program(user)
        client = login(user)
        sio = connect(app, client)
        from app.services import program_scope_service

        def boom(*a, **k):
            raise RuntimeError('boom')
        monkeypatch.setattr(program_scope_service, 'program_in_scope', boom)
        assert join_delib(sio, program.id) is False
        assert not receives(sio, f'deliberation:{program.id}')

    def test_deliberation_room_permission_constant(self):
        from app.sockets.core import DELIBERATION_ROOM_PERMISSION
        assert DELIBERATION_ROOM_PERMISSION == 'deliberation.api.list_applicants'

"""public_id_service, UserHistoryService.log_action and AuthAuditService."""

import json
import uuid

import pytest

from app import db
from app.models import Archive, Phase, Step, Submission
from app.models.log import Log
from app.models.user import User
from app.models.user_history import UserHistory
from app.services import auth_audit_service as aas
from app.services import public_id_service as pid
from app.services.auth_audit_service import AuthAuditService as AA
from app.services.user_history_service import UserHistoryService as UH
from tests.support.factories import make_user


# --------------------------------------------------------------- public ids
class TestPublicId:
    def test_public_id_is_hyphenated_uuid_string(self, app):
        u = make_user('applicant')
        value = pid.public_id(u)
        assert str(uuid.UUID(value)) == value and value == str(u.uuid)

    def test_none_and_unflushed_row(self, app):
        assert pid.public_id(None) is None
        fresh = User(first_name='A', last_name='B', mother_last_name='', username='pending',
                     password='x', email='p@x.test', is_internal=False, role_id=None,
                     must_change_password=False)
        assert pid.public_id(fresh) is None

    def test_uuids_are_unique_and_time_ordered_version_7(self, app):
        users = [make_user('applicant') for _ in range(5)]
        ids = [u.uuid for u in users]
        assert len(set(ids)) == 5 and all(i.version == 7 for i in ids)

    def test_uuid_for_roundtrip(self, app):
        u = make_user('applicant')
        assert pid.uuid_for(User, u.id) == str(u.uuid)

    @pytest.mark.parametrize('bad', [None, 'abc', '', 424242])
    def test_uuid_for_missing_or_garbage(self, app, bad):
        assert pid.uuid_for(User, bad) is None

    def test_uuid_for_numeric_string(self, app):
        u = make_user('applicant')
        assert pid.uuid_for(User, str(u.id)) == str(u.uuid)

    def test_uuids_for_bulk_single_query(self, app):
        users = [make_user('applicant') for _ in range(3)]
        db.session.commit()
        expected = {u.id: str(u.uuid) for u in users}   # load before counting
        stmts = []
        from sqlalchemy import event
        engine = db.engine

        def listener(conn, cursor, statement, *rest):
            stmts.append(statement)
        event.listen(engine, 'before_cursor_execute', listener)
        try:
            out = pid.uuids_for(User, list(expected) + [None, 'x', 999999])
        finally:
            event.remove(engine, 'before_cursor_execute', listener)
        assert out == expected
        assert len(stmts) == 1

    def test_uuids_for_empty(self, app):
        assert pid.uuids_for(User, []) == {} and pid.uuids_for(User, None) == {}

    def test_project_uuid_keys_swaps_only_present_keys(self, app):
        u = make_user('applicant')
        out = pid.project_uuid_keys({'user_id': u.id, 'x': 1}, {'user_id': User, 'missing': User})
        assert out == {'user_id': str(u.uuid), 'x': 1}

    def test_project_does_not_mutate_input(self, app):
        u = make_user('applicant')
        src = {'user_id': u.id}
        pid.project_uuid_keys(src, {'user_id': User})
        assert src == {'user_id': u.id}

    def test_project_none_payload(self, app):
        assert pid.project_uuid_keys(None, {'a': User}) == {}

    def test_by_uuid_lookup_and_malformed(self, app):
        u = make_user('applicant')
        db.session.commit()
        assert User.by_uuid(str(u.uuid)).id == u.id
        assert User.by_uuid('not-a-uuid') is None
        assert User.by_uuid(str(uuid.uuid4())) is None

    def test_user_uuid_shorthand(self, app):
        u = make_user('applicant')
        assert pid.user_uuid(u.id) == str(u.uuid)


class TestCorrectionRequiredProjection:
    def _archive(self):
        ph = Phase('admission', 'd')
        db.session.add(ph)
        db.session.flush()
        st = Step('s', 'd', ph.id)
        db.session.add(st)
        db.session.flush()
        ar = Archive('CV', 'd', None, st.id)
        db.session.add(ar)
        db.session.flush()
        return ar

    def test_plain_text_passes_through(self, app):
        assert pid.correction_required_to_public('Falta CV') == 'Falta CV'
        assert pid.correction_required_to_internal('Falta CV') == 'Falta CV'

    @pytest.mark.parametrize('v', [None, '', 5])
    def test_falsy_or_non_string_untouched(self, app, v):
        assert pid.correction_required_to_public(v) == v

    def test_json_without_archive_id_untouched(self, app):
        raw = json.dumps({'notes': 'x'})
        assert pid.correction_required_to_public(raw) == raw

    def test_roundtrip_integer_to_uuid_and_back(self, app):
        ar = self._archive()
        stored = json.dumps({'archive_id': ar.id, 'notes': 'n'})
        public = json.loads(pid.correction_required_to_public(stored))
        assert public['archive_id'] == str(ar.uuid) and public['notes'] == 'n'
        back = json.loads(pid.correction_required_to_internal(json.dumps(public)))
        assert back['archive_id'] == ar.id

    def test_unknown_uuid_becomes_none_not_error(self, app):
        raw = json.dumps({'archive_id': str(uuid.uuid4())})
        assert json.loads(pid.correction_required_to_internal(raw))['archive_id'] is None

    def test_json_list_untouched(self, app):
        assert pid.correction_required_to_public('[1,2]') == '[1,2]'

    def test_null_archive_id_untouched(self, app):
        raw = json.dumps({'archive_id': None})
        assert pid.correction_required_to_public(raw) == raw


# ------------------------------------------------------------ log_action
class TestLogAction:
    @pytest.fixture(autouse=True)
    def _ctx(self, app):
        with app.test_request_context('/'):
            yield

    def test_creates_row_with_admin(self, app):
        u, admin = make_user('student'), make_user('program_admin')
        entry = UH.log_action(u.id, 'profile_updated', 'texto', admin_id=admin.id)
        db.session.commit()
        row = UserHistory.query.get(entry.id)
        assert (row.user_id, row.admin_id, row.action, row.details) == \
            (u.id, admin.id, 'profile_updated', 'texto')
        assert row.timestamp is not None

    def test_dict_details_serialised_as_json_keeping_unicode(self, app):
        u = make_user('student')
        entry = UH.log_action(u.id, 'profile_updated', {'campo': 'Teléfono'})
        assert json.loads(entry.details) == {'campo': 'Teléfono'}
        assert 'Teléfono' in entry.details

    def test_unknown_user(self, app):
        with pytest.raises(ValueError, match='no existe'):
            UH.log_action(424242, 'profile_updated')

    def test_invalid_action_rejected_and_nothing_written(self, app):
        u = make_user('student')
        with pytest.raises(ValueError, match='no es válida'):
            UH.log_action(u.id, 'made_up_action')
        db.session.flush()
        assert UserHistory.query.count() == 0

    def test_every_registered_action_has_label(self, app):
        assert all(isinstance(v, str) and v for v in UH.ACTIONS.values())

    def test_admin_defaults_to_current_user(self, app):
        from flask_login import login_user
        u, actor = make_user('student'), make_user('program_admin')
        db.session.commit()
        login_user(actor)
        assert UH.log_action(u.id, 'profile_updated').admin_id == actor.id

    def test_explicit_admin_wins_over_current_user(self, app):
        from flask_login import login_user
        u, actor, other = make_user('student'), make_user('program_admin'), make_user('program_admin')
        db.session.commit()
        login_user(actor)
        assert UH.log_action(u.id, 'profile_updated', admin_id=other.id).admin_id == other.id

    def test_anonymous_request_leaves_admin_null(self, app):
        u = make_user('student')
        assert UH.log_action(u.id, 'profile_updated').admin_id is None

    def test_log_action_does_not_commit(self, app):
        u = make_user('student')
        UH.log_action(u.id, 'profile_updated')
        db.session.rollback()
        assert UserHistory.query.count() == 0


class TestLogActionOutsideRequest:
    # Regression: log_action(admin_id=None) outside a request read current_user (None) and raised AttributeError.
    def test_works_in_background_job_context(self, app):
        u = make_user('student')
        assert UH.log_action(u.id, 'profile_updated').admin_id is None

    def test_explicit_admin_id_works_without_request(self, app):
        u, admin = make_user('student'), make_user('program_admin')
        assert UH.log_action(u.id, 'profile_updated', admin_id=admin.id).admin_id == admin.id


# ------------------------------------------------------------- auth audit
@pytest.fixture
def audit(app):
    aas._failure_windows.clear()
    app.config['LOGIN_THROTTLE_USER_MAX'] = 3
    yield
    aas._failure_windows.clear()


def _rows(action=None):
    q = Log.query.order_by(Log.id)
    if action:
        q = q.filter_by(action=action)
    return q.all()


class TestAuthAudit:
    def test_success_always_persisted(self, audit):
        u = make_user('student')
        db.session.commit()
        AA.record_login_success(u.id, 'bob', '203.0.113.77', 'Mozilla')
        row = _rows(AA.ACTION_LOGIN_SUCCESS)[0]
        payload = json.loads(row.description)
        assert row.user_id == u.id and payload['username'] == 'bob'

    def test_stores_network_prefix_not_full_ip(self, audit):
        AA.record_login_failure('x', '203.0.113.77', 'ua', 'bad_password')
        d = _rows()[0].description
        assert '203.0.113.0/24' in d and '203.0.113.77' not in d

    def test_ipv6_uses_48_prefix(self, audit):
        AA.record_login_failure('x', '2001:db8:abcd:1234::1', 'ua', 'bad_password')
        assert '2001:db8:abcd::/48' in _rows()[0].description

    @pytest.mark.parametrize('ip', ['', 'garbage', None])
    def test_unparseable_ip(self, audit, ip):
        AA.record_login_failure('x', ip, 'ua', 'bad_password')
        assert json.loads(_rows()[0].description)['ip_prefix'] == 'unknown'

    def test_first_failure_logged_then_silent_until_threshold(self, audit):
        for _ in range(2):
            AA.record_login_failure('victim', '1.2.3.4', 'ua', 'bad_password')
        assert [r.action for r in _rows()] == [AA.ACTION_LOGIN_FAILED]

    def test_threshold_failure_logged_as_throttled(self, audit):
        for _ in range(3):
            AA.record_login_failure('victim', '1.2.3.4', 'ua', 'bad_password')
        assert [r.action for r in _rows()] == [AA.ACTION_LOGIN_FAILED, AA.ACTION_LOGIN_THROTTLED]

    def test_failures_beyond_threshold_do_not_write(self, audit):
        for _ in range(50):
            AA.record_login_failure('victim', '1.2.3.4', 'ua', 'bad_password')
        assert len(_rows()) == 2

    def test_volume_cap_is_per_username(self, audit):
        for name in ('a', 'b', 'c'):
            AA.record_login_failure(name, '1.2.3.4', 'ua', 'unknown_user')
        assert len(_rows(AA.ACTION_LOGIN_FAILED)) == 3

    def test_unknown_username_row_has_null_user(self, audit):
        AA.record_login_failure('ghost', '1.2.3.4', 'ua', 'unknown_user')
        assert _rows()[0].user_id is None

    def test_known_and_unknown_take_same_path(self, audit):
        u = make_user('student')
        db.session.commit()
        AA.record_login_failure('real', '1.2.3.4', 'ua', 'bad_password', user_id=u.id)
        AA.record_login_failure('ghost', '1.2.3.4', 'ua', 'unknown_user')
        a, b = _rows()
        assert a.action == b.action and set(json.loads(a.description)) == set(json.loads(b.description))

    def test_success_resets_failure_window(self, audit):
        u = make_user('student')
        db.session.commit()
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')
        AA.record_login_success(u.id, 'bob', '1.2.3.4', 'ua')
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')
        assert len(_rows(AA.ACTION_LOGIN_FAILED)) == 2

    def test_reason_and_counter_in_payload(self, audit):
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'inactive_account')
        p = json.loads(_rows()[0].description)
        assert p['reason'] == 'inactive_account' and p['failed_attempts'] == 1

    def test_long_values_truncated(self, audit):
        AA.record_login_failure('u' * 500, '1.2.3.4', 'A' * 500, 'r' * 500)
        p = json.loads(_rows()[0].description)
        assert len(p['username']) == 64 and len(p['user_agent']) == 120 and len(p['reason']) == 40

    def test_subject_key_is_case_and_space_insensitive(self, audit):
        assert aas._subject_key(' Bob ') == aas._subject_key('bob')
        assert 'bob' not in aas._subject_key('bob')

    def test_window_expiry_restarts_count(self, audit, monkeypatch):
        t = {'now': 1000.0}
        monkeypatch.setattr(aas, 'monotonic', lambda: t['now'])
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')
        t['now'] += 15 * 60 + 1
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')
        assert len(_rows(AA.ACTION_LOGIN_FAILED)) == 2

    def test_inside_window_does_not_restart(self, audit, monkeypatch):
        t = {'now': 1000.0}
        monkeypatch.setattr(aas, 'monotonic', lambda: t['now'])
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')
        t['now'] += 60
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')
        assert len(_rows(AA.ACTION_LOGIN_FAILED)) == 1

    def test_lru_is_bounded(self, audit, monkeypatch):
        monkeypatch.setattr(aas, '_SUBJECTS_MAX', 5)
        for i in range(20):
            aas._count_failure(f'user{i}')
        assert len(aas._failure_windows) == 5

    def test_write_failure_never_raises(self, audit, monkeypatch):
        def boom():
            raise RuntimeError('db down')
        monkeypatch.setattr(db.session, 'commit', boom)
        AA.record_login_failure('bob', '1.2.3.4', 'ua', 'bad_password')   # must not raise
        AA.record_login_success(1, 'bob', '1.2.3.4', 'ua')

    def test_setting_resolution_order(self, app, monkeypatch):
        app.config['LOGIN_THROTTLE_USER_MAX'] = None
        monkeypatch.setenv('LOGIN_THROTTLE_USER_MAX', '9')
        assert aas._setting('LOGIN_THROTTLE_USER_MAX', 5) == 9
        app.config['LOGIN_THROTTLE_USER_MAX'] = 2
        assert aas._setting('LOGIN_THROTTLE_USER_MAX', 5) == 2

    @pytest.mark.parametrize('bad', ['abc', '0', '-3'])
    def test_setting_invalid_falls_back(self, app, bad):
        app.config['LOGIN_THROTTLE_USER_MAX'] = bad
        assert aas._setting('LOGIN_THROTTLE_USER_MAX', 5) == 5

"""password_reset_service: token lifecycle, single use, strength, admin reset."""

import string
from datetime import timedelta

import pytest
from freezegun import freeze_time
from werkzeug.security import check_password_hash

from app import db
from app.models.email_queue import EmailQueue
from app.models.notification import Notification
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.models.user_history import UserHistory
from app.services import password_reset_service as prs
from app.utils.datetime_utils import now_local
from tests.support.factories import make_user

GOOD = 'Nueva#Clave1'


@pytest.fixture(autouse=True)
def _request_ctx(app):
    # UserHistoryService.log_action(admin_id=None) reads flask_login.current_user,
    # which only resolves inside a request (see test_user_history_service.py).
    with app.test_request_context('/'):
        yield


@pytest.fixture
def person(app):
    u = make_user('student', must_change_password=True)
    admin = make_user('postgraduate_admin')
    db.session.commit()
    return u, admin


def _token(user, **kw):
    t = prs.generate_token(user.id, **kw)
    db.session.commit()
    return t


class TestGenerateToken:
    def test_persists_opaque_token(self, person):
        u, _ = person
        t = _token(u)
        assert PasswordResetToken.query.get(t.id).token == t.token
        assert len(t.token) >= 48

    def test_tokens_are_unique(self, person):
        u, _ = person
        assert len({prs.generate_token(u.id).token for _ in range(25)}) == 25

    def test_default_ttl_is_seven_days(self, person):
        u, _ = person
        with freeze_time('2026-03-01 10:00:00'):
            t = prs.generate_token(u.id)
            assert t.expires_at - now_local() == timedelta(days=7)

    def test_ttl_minutes_wins_over_days(self, person):
        u, _ = person
        with freeze_time('2026-03-01 10:00:00'):
            t = prs.generate_token(u.id, ttl_days=7, ttl_minutes=45)
            assert t.expires_at - now_local() == timedelta(minutes=45)

    def test_ttl_minutes_zero_is_honoured(self, person):
        u, _ = person
        with freeze_time('2026-03-01 10:00:00'):
            t = prs.generate_token(u.id, ttl_minutes=0)
            assert t.expires_at == now_local()

    def test_invalid_purpose(self, person):
        with pytest.raises(ValueError):
            prs.generate_token(person[0].id, purpose='hack')

    @pytest.mark.parametrize('purpose', ['set_password', 'reset_password'])
    def test_valid_purposes(self, person, purpose):
        assert prs.generate_token(person[0].id, purpose=purpose).purpose == purpose

    def test_records_creator(self, person):
        u, admin = person
        assert prs.generate_token(u.id, created_by_id=admin.id).created_by == admin.id


class TestGetToken:
    def test_valid(self, person):
        t = _token(person[0])
        assert prs.get_token(t.token).id == t.id

    def test_unknown(self, app):
        with pytest.raises(prs.TokenNotFound):
            prs.get_token('nope')

    def test_expired(self, person):
        with freeze_time('2026-03-01 10:00:00'):
            t = _token(person[0], ttl_minutes=10)
        with freeze_time('2026-03-01 10:11:00'):
            with pytest.raises(prs.TokenExpired):
                prs.get_token(t.token)

    def test_valid_one_second_before_expiry(self, person):
        with freeze_time('2026-03-01 10:00:00'):
            t = _token(person[0], ttl_minutes=10)
        with freeze_time('2026-03-01 10:09:59'):
            assert prs.get_token(t.token).id == t.id

    def test_persisted_row_comparison_does_not_raise_typeerror(self, person):
        t = _token(person[0])
        db.session.expire_all()
        # naive datetime read back from the DB must still compare with now_local()
        assert PasswordResetToken.query.get(t.id).is_expired is False

    def test_used_takes_precedence_over_expired(self, person):
        with freeze_time('2026-03-01 10:00:00'):
            t = _token(person[0], ttl_minutes=1)
            t.used_at = now_local()
            db.session.commit()
        with freeze_time('2026-04-01'):
            with pytest.raises(prs.TokenAlreadyUsed):
                prs.get_token(t.token)


class TestConsumeToken:
    def test_sets_password_and_clears_flag(self, person):
        u, _ = person
        t = _token(u)
        prs.consume_token(t.token, GOOD)
        db.session.commit()
        user = User.query.get(u.id)
        assert check_password_hash(user.password, GOOD)
        assert user.must_change_password is False

    def test_single_use(self, person):
        t = _token(person[0])
        prs.consume_token(t.token, GOOD)
        db.session.commit()
        with pytest.raises(prs.TokenAlreadyUsed):
            prs.consume_token(t.token, 'Otra#Clave2')

    def test_second_attempt_does_not_change_password(self, person):
        u, _ = person
        t = _token(u)
        prs.consume_token(t.token, GOOD)
        db.session.commit()
        with pytest.raises(prs.TokenAlreadyUsed):
            prs.consume_token(t.token, 'Otra#Clave2')
        assert check_password_hash(User.query.get(u.id).password, GOOD)

    def test_marks_used_at(self, person):
        t = _token(person[0])
        with freeze_time('2026-03-01 10:00:00'):
            prs.consume_token(t.token, GOOD)
            assert t.used_at == now_local()

    def test_expired_token_leaves_password_alone(self, person):
        u, _ = person
        with freeze_time('2026-03-01 10:00:00'):
            t = _token(u, ttl_minutes=5)
        before = User.query.get(u.id).password
        with freeze_time('2026-03-02'):
            with pytest.raises(prs.TokenExpired):
                prs.consume_token(t.token, GOOD)
        assert User.query.get(u.id).password == before

    def test_weak_password_does_not_burn_token(self, person):
        t = _token(person[0])
        with pytest.raises(prs.WeakPassword):
            prs.consume_token(t.token, 'weak')
        assert PasswordResetToken.query.get(t.id).used_at is None
        prs.consume_token(t.token, GOOD)

    def test_writes_history(self, person):
        u, _ = person
        t = _token(u)
        prs.consume_token(t.token, GOOD)
        db.session.commit()
        rows = UserHistory.query.filter_by(user_id=u.id, action='password_set_via_token').all()
        assert len(rows) == 1
        assert str(t.id) in rows[0].details

    def test_history_does_not_contain_token_or_password(self, person):
        u, _ = person
        t = _token(u)
        prs.consume_token(t.token, GOOD)
        db.session.commit()
        blob = ' '.join(h.details or '' for h in UserHistory.query.all())
        assert t.token not in blob and GOOD not in blob


class TestConsumeTokenRealRegistry:
    def test_consume_works_with_real_action_registry(self, person):
        """Regression: 'password_set_via_token' must be a registered history action."""
        u, _ = person
        t = _token(u)
        prs.consume_token(t.token, GOOD)
        db.session.commit()
        assert UserHistory.query.filter_by(user_id=u.id, action='password_set_via_token').count() == 1


class TestPasswordStrength:
    @pytest.mark.parametrize('pw,fragment', [
        ('Ab1!', '8 caracteres'),
        ('abcdefg1!', 'mayúscula'),
        ('ABCDEFG1!', 'minúscula'),
        ('Abcdefgh!', 'número'),
        ('Abcdefg12', 'especial'),
    ])
    def test_rejections(self, pw, fragment):
        ok, msg = prs._validate_password_strength(pw)
        assert ok is False and fragment in msg

    def test_accepts_strong(self):
        assert prs._validate_password_strength(GOOD) == (True, 'OK')

    def test_exactly_eight_chars_ok(self):
        assert prs._validate_password_strength('Abcdef1!')[0] is True


class TestRandomPassword:
    def test_default_length(self):
        assert len(prs.random_password()) == 24

    def test_custom_length(self):
        assert len(prs.random_password(40)) == 40

    def test_not_repeating(self):
        assert len({prs.random_password() for _ in range(50)}) == 50

    def test_uses_only_printable_alphabet(self):
        allowed = set(string.ascii_letters + string.digits + string.punctuation)
        assert set(prs.random_password(200)) <= allowed

    def test_mixes_character_classes(self):
        pw = prs.random_password(200)
        assert any(c.isupper() for c in pw) and any(c.islower() for c in pw)
        assert any(c.isdigit() for c in pw) and any(c in string.punctuation for c in pw)


class TestDeliverableEmail:
    @pytest.mark.parametrize('email', ['', '   ', 'sin-arroba', None])
    def test_missing_or_malformed(self, app, email):
        u = make_user('student')
        u.email = email
        with pytest.raises(prs.MissingEmail):
            prs.require_deliverable_email(u)

    def test_returns_trimmed_mailbox(self, app):
        u = make_user('student')
        u.email = '  a@b.mx '
        assert prs.require_deliverable_email(u) == 'a@b.mx'


class TestResetUrl:
    def test_contains_token_and_base(self, app):
        url = prs.build_reset_password_url('TOK123')
        assert url.startswith('http://localhost.test') and url.endswith('TOK123')

    def test_ignores_request_host(self, app):
        with app.test_request_context('/', headers={'Host': 'evil.example'}):
            assert 'evil.example' not in prs.build_reset_password_url('T')


class TestIssueAdminReset:
    def test_invalidates_old_password_and_forces_change(self, person, graph):
        u, admin = person
        old = User.query.get(u.id).password
        prs.issue_admin_reset(u.id, admin.id)
        db.session.commit()
        user = User.query.get(u.id)
        assert user.password != old
        assert not check_password_hash(user.password, 'Test1234!')
        assert user.must_change_password is True

    def test_returns_short_ttl(self, person):
        u, admin = person
        with freeze_time('2026-03-01 10:00:00'):
            r = prs.issue_admin_reset(u.id, admin.id)
            assert r['ttl_minutes'] == prs.INTERACTIVE_TTL_MINUTES == 45
            assert r['expires_at'] - now_local() == timedelta(minutes=45)

    def test_issues_single_reset_token(self, person):
        u, admin = person
        prs.issue_admin_reset(u.id, admin.id)
        db.session.commit()
        tokens = PasswordResetToken.query.filter_by(user_id=u.id).all()
        assert len(tokens) == 1
        assert tokens[0].purpose == 'reset_password' and tokens[0].created_by == admin.id

    def test_history_goes_to_admin_not_target(self, person):
        u, admin = person
        prs.issue_admin_reset(u.id, admin.id)
        db.session.commit()
        assert UserHistory.query.filter_by(user_id=admin.id, action='password_reset').count() == 1
        assert UserHistory.query.filter_by(user_id=u.id, action='password_reset').count() == 0

    def test_target_is_notified_and_mailed_once(self, person):
        u, admin = person
        prs.issue_admin_reset(u.id, admin.id)
        db.session.commit()
        assert Notification.query.filter_by(user_id=u.id, type='password_reset').count() == 1
        assert EmailQueue.query.filter_by(user_id=u.id).count() == 1

    def test_link_only_in_email_not_in_history_or_notification(self, person):
        u, admin = person
        prs.issue_admin_reset(u.id, admin.id)
        db.session.commit()
        token = PasswordResetToken.query.filter_by(user_id=u.id).one().token
        assert token in EmailQueue.query.filter_by(user_id=u.id).one().html_content
        for n in Notification.query.all():
            assert token not in (n.message or '') and token not in str(n.data)
            assert token not in (n.action_url or '')
        for h in UserHistory.query.all():
            assert token not in (h.details or '')

    def test_unknown_user(self, person):
        with pytest.raises(prs.TokenNotFound):
            prs.issue_admin_reset(424242, person[1].id)

    def test_user_without_email_blocked_and_password_untouched(self, person):
        u, admin = person
        u.email = ''
        db.session.commit()
        old = u.password
        with pytest.raises(prs.MissingEmail):
            prs.issue_admin_reset(u.id, admin.id)
        assert User.query.get(u.id).password == old
        assert PasswordResetToken.query.count() == 0

    def test_issued_token_can_be_consumed(self, person):
        u, admin = person
        prs.issue_admin_reset(u.id, admin.id)
        db.session.commit()
        token = PasswordResetToken.query.filter_by(user_id=u.id).one().token
        prs.consume_token(token, GOOD)
        db.session.commit()
        assert check_password_hash(User.query.get(u.id).password, GOOD)

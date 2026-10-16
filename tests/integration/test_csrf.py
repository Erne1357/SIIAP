"""CSRF guard on /api mutations and the malformed-path / malformed-query guard."""

import uuid

import pytest

from tests.integration.auth_routes import register_test_routes
from tests.integration.auth_support import fake_redis, isolate_globals  # noqa: F401
from tests.support.factories import make_user

MUTATIONS = ['post', 'put', 'patch', 'delete']
ECHO = '/api/v1/_t/echo'
# Paths the guard deliberately skips (credentials are the protection).
EXEMPT = {'/api/v1/auth/login', '/api/v1/auth/register'}


@pytest.fixture
def app(app):
    return register_test_routes(app)


# ── csrf: logged-in session ─────────────────────────────────────────────────

class TestCsrfHeader:
    @pytest.mark.parametrize('method', MUTATIONS)
    def test_missing_header_is_400(self, login, method):
        client = login(make_user('student'))
        resp = getattr(client.raw, method)(ECHO)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error']['code'] == 'BAD_REQUEST'
        assert body['error']['message'] == 'Token CSRF no enviado en la petición'
        assert body['data'] is None

    @pytest.mark.parametrize('method', MUTATIONS)
    def test_wrong_header_is_400(self, login, method):
        client = login(make_user('student'))
        resp = getattr(client.raw, method)(ECHO, headers={'X-CSRFToken': 'otro-token'})
        assert resp.status_code == 400
        assert 'inválido' in resp.get_json()['error']['message']

    @pytest.mark.parametrize('method', MUTATIONS)
    def test_correct_header_passes(self, login, method):
        client = login(make_user('student'))
        assert getattr(client, method)(ECHO).status_code == 200

    def test_empty_header_value_is_400(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO, headers={'X-CSRFToken': ''}).status_code == 400

    def test_prefix_of_token_rejected(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO, headers={'X-CSRFToken': 'test-csrf'}).status_code == 400

    def test_token_with_trailing_char_rejected(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO, headers={'X-CSRFToken': 'test-csrf-token '}).status_code == 400

    def test_token_case_sensitive(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO, headers={'X-CSRFToken': 'TEST-CSRF-TOKEN'}).status_code == 400

    def test_header_name_case_insensitive(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO, headers={'x-csrftoken': 'test-csrf-token'}).status_code == 200

    def test_token_in_json_body_is_not_accepted(self, login):
        client = login(make_user('student'))
        resp = client.raw.post(ECHO, json={'csrf_token': 'test-csrf-token'})
        assert resp.status_code == 400

    def test_token_in_query_string_is_not_accepted(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO + '?csrf_token=test-csrf-token').status_code == 400

    def test_token_in_form_field_is_not_accepted(self, login):
        client = login(make_user('student'))
        assert client.raw.post(ECHO, data={'csrf_token': 'test-csrf-token'}).status_code == 400

    def test_get_does_not_need_token(self, login):
        client = login(make_user('student'))
        assert client.raw.get(ECHO).status_code == 200

    def test_head_and_options_do_not_need_token(self, login):
        client = login(make_user('student'))
        assert client.raw.head(ECHO).status_code == 200
        assert client.raw.options(ECHO).status_code == 200

    def test_csrf_runs_before_authentication_check(self, login):
        client = login(make_user('student'))
        resp = client.raw.post('/api/v1/auth/change-password', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'BAD_REQUEST'

    def test_csrf_failure_has_flash_in_spanish(self, login):
        client = login(make_user('student'))
        flash = client.raw.post(ECHO).get_json()['flash'][0]
        assert flash['level'] == 'danger'
        assert 'CSRF' in flash['message']

    # Regression (fixed): hmac.compare_digest(str, str) raises TypeError on non-ASCII input, so a non-
    # ASCII X-CSRFToken header yields 500 instead of 400 (app/utils/csrf.py:42)
    def test_non_ascii_header_is_400_not_500(self, login):
        client = login(make_user('student'))
        resp = client.raw.post(ECHO, headers={'X-CSRFToken': 'tókén'})
        assert resp.status_code == 400


class TestCsrfAnonymous:
    @pytest.mark.parametrize('method', MUTATIONS)
    def test_no_session_token_is_400_expired(self, client, method):
        resp = getattr(client, method)(ECHO, headers={'X-CSRFToken': 'cualquiera'})
        assert resp.status_code == 400
        assert 'Sesión expirada' in resp.get_json()['error']['message']

    def test_no_session_token_generates_one_for_next_request(self, client):
        client.post(ECHO)
        with client.session_transaction() as sess:
            assert sess.get('_csrf_token')

    def test_anonymous_with_valid_session_token_passes(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'abc'
        assert client.post(ECHO, headers={'X-CSRFToken': 'abc'}).status_code == 200

    def test_login_is_exempt(self, client, fake_redis):
        resp = client.post('/api/v1/auth/login', json={'username': 'x', 'password': 'y'})
        assert resp.status_code == 401  # reached the view, not a 400

    def test_login_exemption_is_exact_path(self, client):
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'abc'
        # A look-alike path is NOT exempt.
        assert client.post('/api/v1/auth/login/x', json={}).status_code == 400
        assert client.post('/api/v1/auth/login2', json={}).status_code == 400

    def test_non_api_post_is_not_csrf_checked(self, client):
        assert client.post('/_t/form').status_code == 200

    def test_non_api_prefix_lookalike_is_not_checked(self, client):
        # '/apix/...' does not start with '/api/'; guard must not misfire.
        assert client.post('/apix/none').status_code == 404

    def test_reset_password_requires_session_token(self, client):
        resp = client.post('/api/v1/auth/reset-password/tok', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'BAD_REQUEST'

    def test_login_page_issues_fresh_token(self, client):
        client.get('/login')
        with client.session_transaction() as sess:
            first = sess['_csrf_token']
        client.get('/login')
        with client.session_transaction() as sess:
            assert sess['_csrf_token'] != first


class TestCsrfCoversEveryApiMutation:
    """Walk the whole URL map: every mutating /api route rejects a tokenless request."""

    def _sample(self, rule):
        values = {}
        for name in rule.arguments:
            conv = rule._converters.get(name)
            kind = type(conv).__name__
            if kind == 'IntegerConverter':
                values[name] = 1
            elif kind == 'UUIDConverter':
                values[name] = uuid.uuid4()
            else:
                values[name] = 'x'
        return values

    def test_every_api_mutation_without_token_is_400(self, app, login):
        client = login(make_user('student'))
        adapter = app.url_map.bind('localhost')
        offenders, checked = [], 0
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith('/api/'):
                continue
            for method in sorted(rule.methods & {'POST', 'PUT', 'PATCH', 'DELETE'}):
                try:
                    url = adapter.build(rule.endpoint, self._sample(rule), method=method)
                except Exception:
                    continue
                path = url.split('?')[0]
                if path in EXEMPT:
                    continue
                checked += 1
                resp = client.raw.open(url, method=method)
                if resp.status_code != 400:
                    offenders.append((method, path, resp.status_code))
        assert checked > 50, 'URL map walk found suspiciously few mutations'
        assert offenders == []

    def test_every_api_mutation_with_wrong_token_is_400(self, app, login):
        client = login(make_user('student'))
        adapter = app.url_map.bind('localhost')
        offenders = []
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith('/api/'):
                continue
            for method in sorted(rule.methods & {'POST', 'PUT', 'PATCH', 'DELETE'}):
                try:
                    url = adapter.build(rule.endpoint, self._sample(rule), method=method)
                except Exception:
                    continue
                if url.split('?')[0] in EXEMPT:
                    continue
                resp = client.raw.open(url, method=method, headers={'X-CSRFToken': 'mal'})
                if resp.status_code != 400:
                    offenders.append((method, url, resp.status_code))
        assert offenders == []

    def test_only_login_is_exempt_in_the_url_map(self, app):
        """Anything exempt must also be a real, intentional route."""
        paths = {r.rule for r in app.url_map.iter_rules()}
        assert '/api/v1/auth/login' in paths


# ── malformed paths / queries ───────────────────────────────────────────────

class TestMalformedApiPaths:
    @pytest.mark.parametrize('token', ['undefined', 'null', 'NaN'])
    def test_path_segment(self, login, token):
        client = login(make_user('student'))
        resp = client.get(f'/api/v1/_t/echo/{token}')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error']['code'] == 'MALFORMED_PATH'
        assert token in body['error']['message']
        assert body['error']['path'] == f'/api/v1/_t/echo/{token}'
        assert body['data'] is None

    @pytest.mark.parametrize('token', ['undefined', 'null', 'NaN'])
    def test_query_value(self, login, token):
        client = login(make_user('student'))
        resp = client.get(f'{ECHO}?program_id={token}')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error']['code'] == 'MALFORMED_QUERY'
        assert f'program_id={token}' in body['error']['message']

    def test_middle_segment(self, client):
        resp = client.get('/api/v1/undefined/echo')
        assert resp.status_code == 400
        assert resp.get_json()['error']['code'] == 'MALFORMED_PATH'

    def test_applies_to_anonymous_requests(self, client):
        assert client.get('/api/v1/auth/undefined/info').status_code == 400

    def test_on_real_endpoints(self, login):
        client = login(make_user('student'))
        assert client.get('/api/v1/auth/reset-password/undefined/info').status_code == 400

    def test_percent_encoded_segment_is_decoded(self, client):
        resp = client.get('/api/v1/_t/echo/%75ndefined')
        assert resp.status_code == 400

    def test_query_key_irrelevant_value_checked(self, client):
        assert client.get(f'{ECHO}?a=1&b=null').status_code == 400

    def test_mutation_with_valid_csrf_still_rejected(self, login):
        client = login(make_user('student'))
        assert client.post('/api/v1/_t/echo/undefined').status_code == 400
        assert client.post('/api/v1/_t/echo/undefined').get_json()['error']['code'] == 'MALFORMED_PATH'

    def test_csrf_checked_first_on_mutations(self, login):
        client = login(make_user('student'))
        resp = client.raw.post('/api/v1/_t/echo/undefined')
        assert resp.get_json()['error']['code'] == 'BAD_REQUEST'

    @pytest.mark.parametrize('value', ['undefined1', 'Undefined', 'NULL', 'nan', 'nullable', ''])
    def test_lookalikes_are_not_flagged(self, client, value):
        assert client.get(f'{ECHO}?q={value}').status_code == 200

    @pytest.mark.parametrize('segment', ['undefined1', 'Null', 'nan', 'xundefined'])
    def test_lookalike_segments_not_flagged(self, client, segment):
        assert client.get(f'/api/v1/_t/echo/{segment}').status_code == 200

    def test_non_api_paths_not_affected(self, client):
        assert client.get('/_t/open?x=null').status_code == 200

    def test_substring_in_larger_query_value_not_flagged(self, client):
        assert client.get(f'{ECHO}?q=value-undefined-x').status_code == 200

    # Regression (fixed): reject_malformed_api_paths iterates request.args.items(), which yields only
    # the FIRST value of a repeated key, so '?id=1&id=undefined' slips through (app/__init__.py
    # reject_malformed_api_paths; use request.args.items(multi=True))
    def test_repeated_query_key_second_value_checked(self, client):
        assert client.get(f'{ECHO}?id=1&id=undefined').status_code == 400

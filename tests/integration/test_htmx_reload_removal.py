"""Fragment routes that replaced `location.reload()` (plan phase 03, stage C2).

Each fragment answers an HX request with a bare partial (no page shell) and
keeps the normal navigation of the same URL unchanged.
"""

import json

from tests.support.factories import get_or_create_role, grant, make_user

HX = {'HX-Request': 'true'}


def _html(resp):
    return resp.get_data(as_text=True)


class TestDashboardRefresh:
    def _applicant(self, login):
        user = make_user('applicant')
        grant(get_or_create_role('applicant'), 'programs.api.enroll')
        return login(user)

    def test_full_page_carries_the_refresh_region(self, app, login):
        resp = self._applicant(login).get('/user/dashboard')
        html = _html(resp)
        assert resp.status_code == 200
        assert 'id="dashboard-content"' in html
        assert 'siiap:dashboard:refresh' in html
        assert 'hx-swap="morph:innerHTML"' in html
        assert 'HX-Request' in resp.headers['Vary']

    def test_htmx_request_gets_only_the_body(self, app, login):
        resp = self._applicant(login).get('/user/dashboard', headers=HX)
        html = _html(resp)
        assert resp.status_code == 200
        assert '<html' not in html and 'id="dashboard-content"' not in html
        assert 'HX-Request' in resp.headers['Vary']

    def test_postgraduate_refresh_sends_only_its_data_regions(self, app, login):
        user = make_user('postgraduate_admin')
        grant(get_or_create_role('postgraduate_admin'), 'academic_periods.api.create')
        client = login(user)
        page = _html(client.get('/user/dashboard'))
        assert 'hx-swap="none"' in page and 'hx-select-oob=' in page
        frag = _html(client.get('/user/dashboard', headers=HX))
        for region in ('postgradBanner', 'postgradOverviewData', 'postgradProgramStats'):
            assert f'id="{region}"' in frag
        assert 'adminTabs' not in frag  # the tabs are never swapped

    def test_anonymous_htmx_gets_hx_redirect(self, client):
        resp = client.get('/user/dashboard', headers=HX)
        assert resp.status_code == 401
        assert resp.headers['HX-Redirect'].endswith('/login')


class TestEventsWidgetFragment:
    def test_returns_the_partial_for_htmx_and_plain(self, app, login):
        client = login(make_user('applicant'))
        for headers in (HX, {}):
            resp = client.get('/user/dashboard/events-widget', headers=headers)
            assert resp.status_code == 200
            assert '<html' not in _html(resp)
            assert 'HX-Request' in resp.headers['Vary']

    def test_anonymous_htmx_gets_hx_redirect(self, client):
        resp = client.get('/user/dashboard/events-widget', headers=HX)
        assert resp.status_code == 401
        assert resp.headers['HX-Redirect'].endswith('/login')


class TestProfileSummaryFragment:
    def test_main_column_plus_oob_card_and_escaping(self, app, login):
        user = make_user('applicant')
        user.first_name = '<b>Ana</b>'
        client = login(user)
        resp = client.get('/user/profile/summary', headers=HX)
        html = _html(resp)
        assert resp.status_code == 200
        assert '<html' not in html
        assert 'id="profilePersonalInfo" hx-swap-oob="innerHTML"' in html
        assert '<b>Ana</b>' not in html and '&lt;b&gt;Ana&lt;/b&gt;' in html

    def test_full_profile_page_has_both_regions_without_oob(self, app, login):
        html = _html(login(make_user('applicant')).get('/user/profile'))
        assert 'id="profileHeaderMain"' in html
        assert 'id="profilePersonalInfo"' in html
        assert 'hx-swap-oob' not in html

    def test_anonymous_htmx_gets_hx_redirect(self, client):
        resp = client.get('/user/profile/summary', headers=HX)
        assert resp.status_code == 401


class TestReviewListRefresh:
    URL = '/admin/review/submissions'

    def _client(self, login):
        user = make_user('program_admin')
        grant(get_or_create_role('program_admin'), 'admin_review.page.view')
        return login(user)

    def test_full_page_binds_the_body_to_realtime_events(self, app, login):
        resp = self._client(login).get(self.URL)
        html = _html(resp)
        assert resp.status_code == 200
        assert 'id="submissions-body"' in html
        assert 'siiap:submission:reviewed from:window' in html
        assert 'siiap:submission:new from:window' in html
        assert 'id="phase-count-admission"' in html

    def test_htmx_returns_rows_plus_oob_counters(self, app, login):
        resp = self._client(login).get(self.URL + '?status=pending', headers=HX)
        html = _html(resp)
        assert resp.status_code == 200
        assert '<html' not in html and '<thead' not in html
        assert 'id="pendingDocsCount" hx-swap-oob="true"' in html
        assert 'id="phase-count-conclusion" hx-swap-oob="true"' in html
        assert 'HX-Request' in resp.headers['Vary']

    def test_without_permission_htmx_swaps_nothing(self, app, login):
        resp = login(make_user('student')).get(self.URL, headers=HX)
        assert resp.status_code == 403
        assert resp.headers['HX-Reswap'] == 'none'
        assert json.loads(resp.headers['HX-Trigger'])['siiap:flash']['message']


class TestEmailConnectionFragment:
    URL = '/admin/emails/connection'

    def _admin(self, login):
        user = make_user('postgraduate_admin')
        grant(get_or_create_role('postgraduate_admin'), 'admin_emails.api.manage')
        return login(user)

    def test_disconnected_state_is_rendered(self, app, login, monkeypatch):
        monkeypatch.setattr('app.routes.pages.admin.email_pages.read_account_info', lambda: None)
        resp = self._admin(login).get(self.URL, headers=HX)
        html = _html(resp)
        assert resp.status_code == 200
        assert 'No conectado.' in html and 'Conectar con Microsoft' in html
        assert '<html' not in html

    def test_connected_state_escapes_the_account(self, app, login, monkeypatch):
        monkeypatch.setattr('app.routes.pages.admin.email_pages.read_account_info',
                            lambda: {'name': '<i>X</i>', 'username': 'x@y.mx'})
        html = _html(self._admin(login).get(self.URL, headers=HX))
        assert 'btnDisconnect' in html and '&lt;i&gt;X&lt;/i&gt;' in html

    def test_without_permission_htmx_swaps_nothing(self, app, login):
        resp = login(make_user('student')).get(self.URL, headers=HX)
        assert resp.status_code == 403
        assert resp.headers['HX-Reswap'] == 'none'

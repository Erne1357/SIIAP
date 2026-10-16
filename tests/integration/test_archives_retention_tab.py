"""
The retention tab on /admin/settings/ only renders for callers who can use it.

Regression: coordinators (program_admin) reach the archives page through
archives.api.list, but the retention tab always loaded retention.js, whose
first request needs admin_retention.api.manage — every coordinator saw a 403
alert on page load. Found by the E2E suite.
"""

from tests.support.factories import get_or_create_role, grant, make_user

URL = '/admin/settings/'


def _page_for(app, login, *codenames):
    user = make_user('program_admin')
    grant(get_or_create_role('program_admin'), *codenames)
    resp = login(user).get(URL)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def test_coordinator_without_retention_permission_gets_no_retention_tab(app, login):
    html = _page_for(app, login, 'archives.api.list')
    assert 'id="tab-retention"' not in html
    assert 'id="pane-retention"' not in html
    assert 'js/admin/settings/retention.js' not in html


def test_retention_manager_gets_the_tab_and_its_script(app, login):
    html = _page_for(app, login, 'archives.api.list', 'admin_retention.api.manage')
    assert 'id="tab-retention"' in html
    assert 'id="pane-retention"' in html
    assert 'js/admin/settings/retention.js' in html

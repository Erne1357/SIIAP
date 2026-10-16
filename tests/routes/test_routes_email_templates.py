"""Step 5 — every transactional e-mail template renders without a request context."""

from pathlib import Path

import jinja2
import pytest

EMAILS_DIR = Path(__file__).resolve().parents[2] / 'app' / 'templates' / 'emails'
TEMPLATES = sorted(p.name for p in EMAILS_DIR.glob('*.html'))


class PermissiveUndefined(jinja2.ChainableUndefined):
    """Missing variables render as '' and tolerate calls, comparisons, iteration."""

    def __call__(self, *a, **k):
        return self

    def __lt__(self, other):
        return False

    __le__ = __gt__ = __ge__ = __lt__

    def __getitem__(self, key):
        return self


def _context():
    """Generic context: every variable the templates reference, as plausible text."""
    names = (
        'user_name program_name reason event_title archive_name slot_datetime new_slot_datetime '
        'location url notes expires_str closes_at control_number period_name status_label to_program '
        'from_program event_date granted_until event_url dashboard_url logo_url title preheader '
        'header_title rejection_type deadline_name deadline_date old_status new_status'
    ).split()
    ctx = {n: f'<{n}>' for n in names}
    ctx.update(approved=True, rejection_type='partial', url='http://localhost.test/x',
               event_url='http://localhost.test/e', dashboard_url='http://localhost.test/d')
    return ctx


def test_email_templates_discovered():
    assert len(TEMPLATES) >= 25 and 'base_email.html' in TEMPLATES


@pytest.fixture(scope='module')
def email_env(routes_app):
    with routes_app.app_context():
        yield routes_app.jinja_env.overlay(undefined=PermissiveUndefined)


@pytest.mark.parametrize('name', [t for t in TEMPLATES if t != 'base_email.html'])
@pytest.mark.parametrize('approved', [True, False])
def test_email_template_renders_without_request_context(routes_app, email_env, name, approved):
    from flask import has_request_context
    assert not has_request_context()
    ctx = _context()
    ctx['approved'] = approved
    html = email_env.get_template(f'emails/{name}').render(**ctx)
    assert '<html' in html.lower()
    assert 'lang="es"' in html, f'{name}: missing lang="es" (WCAG 3.1.1)'
    assert '{{' not in html and '{%' not in html


def test_base_template_declares_spanish():
    assert 'lang="es"' in (EMAILS_DIR / 'base_email.html').read_text(encoding='utf-8')


def test_email_templates_use_no_css_variables():
    """Outlook drops custom properties: emails must use literal hex (rule in base_email.html)."""
    offenders = [t for t in TEMPLATES if 'var(--' in (EMAILS_DIR / t).read_text(encoding='utf-8')
                 .split('#}', 1)[-1]]
    assert not offenders, offenders

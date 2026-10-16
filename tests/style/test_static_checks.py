"""Hard (zero-tolerance) static checks that need no baseline."""

import re

import pytest

from tests.style.rules import ROOT, TEMPLATES, scan_secrets

pytestmark = pytest.mark.style


@pytest.mark.parametrize("name", ["base.html", "auth_base.html"])
def test_root_templates_declare_spanish(name):
    html = (TEMPLATES / name).read_text(encoding="utf-8")
    assert re.search(r"<html\b[^>]*\blang\s*=\s*[\"']es", html), f"{name} must have lang=\"es\" on <html>"


def test_base_email_declares_spanish():
    html = (TEMPLATES / "emails" / "base_email.html").read_text(encoding="utf-8")
    assert re.search(r"<html\b[^>]*\blang\s*=\s*[\"']es", html)


def test_no_secrets_in_tracked_files():
    findings = scan_secrets()
    assert not findings, "Possible secrets committed:\n" + "\n".join(findings)


def test_css_core_declared_once():
    """Page templates must not re-link the CSS core (see _head_css.html)."""
    offenders = []
    for p in TEMPLATES.rglob("*.html"):
        if p.name in {"_head_css.html"}:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"""href=["'][^"']*(?:_tokens|/css/base|/css/components/)""", text):
            offenders.append(p.relative_to(ROOT).as_posix())
    assert not offenders, "CSS core linked outside _head_css.html: " + ", ".join(offenders)

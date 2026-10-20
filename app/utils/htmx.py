"""htmx helpers: detect HX requests, render fragments, talk to the client bridge.

The client side lives in ``app/static/js/utils/htmx-bridge.js``. The contract
between both halves:

* A fragment route returns an HTML partial (``render_fragment``), never the
  ``{data, error, meta, flash}`` envelope.
* A message for the user travels in ``HX-Trigger`` as a ``siiap:flash`` event
  (``hx_flash``); the bridge turns it into ``SIIAP.flash``.
* A refusal (401/403/404/400/500) on an HX request must never be a 302 to a
  full page: htmx would follow it and inject the login page into a ``<tbody>``.
  ``hx_error`` / ``hx_redirect`` build the right answer.

See ``.claude/rules/htmx-fragments.md``.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from flask import Response, make_response, render_template, request

HX_TRIGGER = "HX-Trigger"
FLASH_EVENT = "siiap:flash"


def is_htmx() -> bool:
    """True when the current request was issued by htmx (``HX-Request: true``)."""
    return request.headers.get("HX-Request", "").lower() == "true"


def wants_html_fragment() -> bool:
    """True when the caller expects an HTML fragment (and can swap it in place).

    Error handlers and request hooks branch on this to answer with htmx headers
    instead of a redirect or a full error page.
    """
    return is_htmx()


def _as_response(response) -> Response:
    return response if isinstance(response, Response) else make_response(response)


def hx_trigger(response, event: str, payload: Optional[Any] = None) -> Response:
    """Add a client event to the ``HX-Trigger`` header, keeping any already set.

    ``payload`` becomes ``event.detail``. The JSON is ASCII-escaped because HTTP
    header values must be latin-1 safe.
    """
    resp = _as_response(response)
    raw = resp.headers.get(HX_TRIGGER)
    events: dict = {}
    if raw:
        try:
            parsed = json.loads(raw)
            events = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            # A plain comma-separated list of event names.
            events = {name.strip(): "" for name in raw.split(",") if name.strip()}
    events[event] = payload if payload is not None else ""
    resp.headers[HX_TRIGGER] = json.dumps(events, ensure_ascii=True, separators=(",", ":"))
    return resp


def hx_flash(response, level: str, message: str) -> Response:
    """Queue a user message (shown by ``SIIAP.flash`` through the bridge)."""
    return hx_trigger(response, FLASH_EVENT, {"level": level, "message": message})


def hx_redirect(url: str, status: int = 200) -> Response:
    """Full-page navigation requested by the server (``HX-Redirect``).

    Unlike a 302, htmx does not follow it with XHR: it assigns ``location``.
    """
    resp = make_response("", status)
    resp.headers["HX-Redirect"] = url
    return resp


def hx_error(status: int, message: str, level: str = "danger") -> Response:
    """Error answer for an HX request: swap nothing, tell the user why."""
    resp = make_response("", status)
    resp.headers["HX-Reswap"] = "none"
    return hx_flash(resp, level, message)


def render_fragment(template: str, *, status: int = 200, **context) -> Response:
    """Render a partial (``templates/<area>/_partials/*.html``) as a response.

    ``Vary: HX-Request`` keeps a cache from serving the fragment to a normal
    navigation of the same URL (or the full page to htmx).
    """
    resp = make_response(render_template(template, **context), status)
    resp.headers.add("Vary", "HX-Request")
    return resp

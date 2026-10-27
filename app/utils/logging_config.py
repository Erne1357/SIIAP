"""
Process-wide logging to stdout with a request id per line.

Every module already logs through `logging.getLogger(__name__)`, but nothing
configured the root logger: Python's last-resort handler only printed WARNING
and above, without timestamps, so INFO lines from services were lost.

`configure_logging()` sends everything to stdout (Docker collects it) with a
request id on each line, so one request can be followed across log lines.
Loki (via Alloy, in the separate `platform` stack) collects every container's
stdout, so the `request_id=<id>` token is what correlates a request across
lines there.
"""
from __future__ import annotations

import logging
import logging.config
import os
import re
import uuid

from flask import Flask, g, has_request_context, request

REQUEST_ID_HEADER = 'X-Request-ID'

# Accept an upstream id only if it is short and harmless to echo into logs.
_SAFE_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{1,64}$')

_configured = False


class RequestIdFilter(logging.Filter):
    """Attach the current request id (or '-') to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = (
            getattr(g, 'request_id', '-') if has_request_context() else '-'
        )
        return True


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger once per process. Safe to call repeatedly."""
    global _configured
    if _configured:
        return
    level = (level or os.environ.get('LOG_LEVEL') or 'INFO').upper()
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {'request_id': {'()': RequestIdFilter}},
        'formatters': {
            'default': {
                'format': '%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s: %(message)s',
            },
        },
        'handlers': {
            'stdout': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
                'formatter': 'default',
                'filters': ['request_id'],
            },
        },
        'root': {'level': level, 'handlers': ['stdout']},
        'loggers': {
            # Request lines already come from gunicorn's access log.
            'werkzeug': {'level': 'WARNING'},
            'engineio': {'level': 'WARNING'},
            'socketio': {'level': 'WARNING'},
        },
    })
    _configured = True


def init_request_id(app: Flask) -> None:
    """Assign a request id per request and echo it back in the response."""

    @app.before_request
    def _assign_request_id():
        incoming = request.headers.get(REQUEST_ID_HEADER, '')
        g.request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex[:16]

    @app.after_request
    def _echo_request_id(response):
        request_id = getattr(g, 'request_id', None)
        if request_id:
            response.headers.setdefault(REQUEST_ID_HEADER, request_id)
        return response

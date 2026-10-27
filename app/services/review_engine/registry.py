"""Registry of review kinds: one `ReviewKind` instance per key."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.review_engine.errors import ReviewNotFound

if TYPE_CHECKING:
    from app.services.review_engine.base import ReviewKind

#: key -> ReviewKind instance, in registration order.
KINDS: dict = {}

UNKNOWN_KIND_MESSAGE = 'Tipo de revisión no encontrado.'


def register(kind: 'ReviewKind') -> 'ReviewKind':
    """Add `kind` to the registry (re-registering the same key replaces it). Returns it."""
    if not getattr(kind, 'key', None):
        raise ValueError('A review kind needs a key.')
    KINDS[kind.key] = kind
    return kind


def get_kind(key) -> 'ReviewKind':
    """The kind registered under `key`; ReviewNotFound (404) when there is none."""
    kind = KINDS.get(key) if isinstance(key, str) else None
    if kind is None:
        raise ReviewNotFound(UNKNOWN_KIND_MESSAGE)
    return kind

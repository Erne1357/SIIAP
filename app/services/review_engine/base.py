"""
`ReviewKind` — the adapter one reviewable type implements — and `Decision`,
the engine's result.

A kind wraps an existing table (no data migration): it knows how to load and
lock one item, which program and student program it belongs to, which status
means "pending", how to write a decision and which automatic effects an
approval has (and how to undo them when it is reverted). The engine
(`engine.decide`) owns the rules common to every kind: permission, scope,
lock, re-decision only with a reason, the titled guard, commit, then
notification + history + socket.

Contract for a new kind (Wave 2 adds `acceptance_kinds.py` and
`extension_kinds.py` this way):

    from app.services.review_engine.base import ReviewKind
    from app.services.review_engine.registry import register

    class MyKind(ReviewKind):
        key = 'my_kind'
        label = 'Mi tipo'                       # Spanish, shown in the inbox
        permission = 'resource.api.decide'      # existing decision codename
        model = MyModel
        pending_statuses = ('pending',)
        decided_statuses = ('approved', 'rejected')
        ...override the hooks below...

    register(MyKind())

and add one import line to `review_engine/__init__.py` (`_KIND_MODULES`).

Hook rules:
- `apply`, `on_approved` and `on_reverted` run inside the decision
  transaction and never commit; raising a `ReviewError` (usually
  `ReviewConflict`) aborts the decision with nothing written.
- `log_decision`, `notify` and `emit` run after the commit; the engine
  commits after each of the first two and swallows (logs) their errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.utils.datetime_utils import now_local

#: Decisions every kind accepts; `status_for` maps them to the kind's status.
VALID_DECISIONS = ('approve', 'reject')


@dataclass
class Decision:
    """Outcome of `decide`."""

    item: Any
    kind: 'ReviewKind'
    status: str
    reverted: bool = False
    previous_status: Optional[str] = None


class ReviewKind:
    """Adapter of one reviewable type. Subclasses override what differs."""

    key: str = ''
    label: str = ''
    permission: str = ''
    model = None
    pending_statuses: tuple = ()
    decided_statuses: tuple = ()
    #: decision -> status written on the item.
    status_by_decision: dict = {'approve': 'approved', 'reject': 'rejected'}
    #: Spanish 404 message: unknown item and out-of-scope item are indistinguishable.
    not_found_message: str = 'Elemento no encontrado.'

    # ── Loading ──────────────────────────────────────────────────────────

    def load_for_update(self, item_uuid):
        """The item with public id `item_uuid`, row-locked; None if unknown or of another kind."""
        raise NotImplementedError

    def matches(self, item) -> bool:
        """True if `item` belongs to this kind (several kinds may share a table)."""
        return item is not None

    # ── Ownership ────────────────────────────────────────────────────────

    def program_id(self, item) -> Optional[int]:
        raise NotImplementedError

    def user_program_id(self, item) -> Optional[int]:
        raise NotImplementedError

    def student(self, item):
        """The `User` the item belongs to."""
        raise NotImplementedError

    # ── Status ───────────────────────────────────────────────────────────

    def status(self, item) -> str:
        return item.status

    def is_pending(self, item) -> bool:
        return self.status(item) in self.pending_statuses

    def status_for(self, decision: str) -> str:
        return self.status_by_decision[decision]

    # ── Decision (inside the transaction, no commit) ─────────────────────

    def apply(self, item, status: str, actor, comment: str, extra: dict) -> None:
        """Write `status` (+ reviewer, date, comment) on the item."""
        raise NotImplementedError

    def on_approved(self, item, actor) -> None:
        """Automatic effects of an approval."""

    def on_reverted(self, item, actor) -> None:
        """Undo the automatic effects of an approval being reverted (or raise ReviewConflict)."""

    # ── After the commit (best effort) ───────────────────────────────────

    def log_decision(self, item, status: str, actor, comment: str) -> None:
        """History entry of a first decision (a reversion is logged by the engine)."""

    def notify(self, item, status: str, reverted: bool) -> None:
        """Notice (+ e-mail) to the student."""

    def emit(self, item, status: str, reverted: bool) -> None:
        """Kind-specific socket event, if the old screens listen to one."""

    # ── Inbox (phase 6D, task 6) ─────────────────────────────────────────

    def pending_query(self, program_ids: Optional[set]):
        """Query of pending items in `program_ids` (None = every program)."""
        raise NotImplementedError

    def decided_query(self, program_ids: Optional[set], since: datetime):
        """Query of items decided at or after `since` in `program_ids` (None = all)."""
        raise NotImplementedError

    def title(self, item) -> str:
        """Short Spanish description of the item (document name, request...)."""
        return self.label

    def submitted_at(self, item) -> Optional[datetime]:
        raise NotImplementedError

    def decided_at(self, item) -> Optional[datetime]:
        return None

    def row(self, item) -> dict:
        """Inbox row. Keys are fixed: the inbox templates read them."""
        raise NotImplementedError

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def now():
        return now_local()

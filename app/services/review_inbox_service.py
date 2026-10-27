"""
"Por revisar" inbox (phase 6D): one list of everything the actor may decide,
across every review kind (`app/services/review_engine/`).

Framework-agnostic: the caller passes the actor; no request, no current_user.

Rules:
- A kind is visible only when the actor holds its decision permission; an
  invisible kind is neither listed nor counted.
- The program scope always applies (`program_scope_service`). A `program_id`
  filter outside the scope (or unparseable) yields an empty result, like the
  other listing services, which filter rather than fail; the page route
  decides whether to answer 404.
- Pending view: oldest submission first, with whole days waiting and an
  `overdue` flag past `OVERDUE_DAYS`. Decided view: decisions of the last
  `DECIDED_WINDOW_DAYS` days, newest first.

Paging across kinds (items live in different tables): read only the
(id, date) keys of each visible kind, merge them in Python, slice the page,
then load full rows for that page with one bulk query per kind
(`ReviewKind.inbox_rows`, eager-loaded).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func

from app.services import file_access_service
from app.services import program_scope_service as scope_service
from app.services.review_engine import KINDS
from app.utils.datetime_utils import now_local, to_local_timezone

VIEW_PENDING = 'pending'
VIEW_DECIDED = 'decided'
VIEWS = (VIEW_PENDING, VIEW_DECIDED)

#: Days of waiting after which a pending item is flagged.
OVERDUE_DAYS = 7
#: How far back the decided view looks.
DECIDED_WINDOW_DAYS = 30

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100


# ── Helpers ─────────────────────────────────────────────────────────────


def _naive_local(value: Optional[datetime]) -> Optional[datetime]:
    """`value` as a naive local datetime (the DB columns are naive local time)."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return to_local_timezone(value).replace(tzinfo=None)
    return value


def _now() -> datetime:
    return _naive_local(now_local())


def _days_waiting(submitted: Optional[datetime], now: datetime) -> int:
    if submitted is None:
        return 0
    return max(0, (now - _naive_local(submitted)).days)


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _program_ids(actor, program_id) -> Optional[set]:
    """Programs to list: the actor's scope (None = all), narrowed by `program_id`."""
    scope = scope_service.accessible_program_ids(actor)
    if program_id is None or program_id == '':
        return scope
    if not scope_service.program_in_scope(actor, program_id):
        return set()
    return {int(program_id)}


def _count(query, kind) -> int:
    return query.order_by(None).with_entities(func.count(kind.model.id)).scalar() or 0


def _keys(kind, view: str, program_ids, since: datetime) -> list:
    """[(date, id)] of the kind's items in the view (dates naive local)."""
    if view == VIEW_PENDING:
        query, attr = kind.pending_query(program_ids), kind.submitted_attr
    else:
        query, attr = kind.decided_query(program_ids, since), kind.decided_attr
    return [(_naive_local(ts), item_id)
            for item_id, ts in query.with_entities(kind.model.id, getattr(kind.model, attr)).all()]


def _file_missing(row: dict) -> bool:
    """True when the row points at a stored file that is no longer on disk.

    Rows without a file (extensions, a submission resolved without upload)
    are not "missing". The stored
    path comes in the row's `file_path` (no extra query per item).
    """
    if not row.get('file_url'):
        return False
    return not file_access_service.stored_file_exists(row.get('file_path') or '')


# ── Public API ──────────────────────────────────────────────────────────


def visible_kinds(actor) -> list:
    """Kinds whose decision permission `actor` holds, in registry order."""
    if actor is None:
        return []
    return [kind for kind in KINDS.values() if actor.has_permission(kind.permission)]


def list_items(actor, *, program_id=None, kind=None, view: str = VIEW_PENDING,
               page: int = 1, per_page: int = DEFAULT_PER_PAGE) -> dict:
    """
    One page of the inbox.

    Returns {'items', 'total', 'page', 'pages', 'per_page', 'counts', 'kinds', 'view'}:
    - items: `kind.row(item)` + 'kind', 'days_waiting' (int in the pending
      view, None in the decided view) and 'overdue' (days_waiting > 7).
    - counts: pending items per visible kind (program filter applied, kind
      filter ignored), so the tabs always show every kind's backlog.
    - kinds: [(key, label)] of the visible kinds.
    - every item also carries 'file_missing' (stored file gone from disk: the
      row is still listed and decidable, the template shows "Archivo no disponible").
    An unknown or invisible `kind` filter, or a program out of scope, gives
    no items.
    """
    view = view if view in VIEWS else VIEW_PENDING
    per_page = min(max(_to_int(per_page, DEFAULT_PER_PAGE), 1), MAX_PER_PAGE)
    page = max(_to_int(page, 1), 1)

    kinds = visible_kinds(actor)
    program_ids = _program_ids(actor, program_id)
    now = _now()
    since = now - timedelta(days=DECIDED_WINDOW_DAYS)
    no_programs = program_ids is not None and not program_ids

    counts = {k.key: 0 for k in kinds}
    selected = [k for k in kinds if kind in (None, '', k.key)]

    # (kind_index, kind, [(date, id)]) for each selected kind.
    keyed = []
    if not no_programs:
        for index, k in enumerate(kinds):
            if view == VIEW_PENDING:
                # The pending keys double as the counts: one query per kind.
                keys = _keys(k, view, program_ids, since)
                counts[k.key] = len(keys)
                if k in selected:
                    keyed.append((index, k, keys))
            else:
                counts[k.key] = _count(k.pending_query(program_ids), k)
                if k in selected:
                    keyed.append((index, k, _keys(k, view, program_ids, since)))

    merged = [(ts, index, item_id, k) for index, k, keys in keyed for ts, item_id in keys]
    if view == VIEW_PENDING:
        # Oldest first; an item without date goes last.
        merged.sort(key=lambda e: (e[0] is None, e[0] or datetime.min, e[1], e[2]))
    else:
        merged.sort(key=lambda e: (e[0] or datetime.min, -e[1], e[2]), reverse=True)

    total = len(merged)
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    window = merged[(page - 1) * per_page: page * per_page]

    ids_by_kind: dict = {}
    for _ts, _index, item_id, k in window:
        ids_by_kind.setdefault(k.key, (k, []))[1].append(item_id)
    rows_by_kind = {key: k.inbox_rows(ids) for key, (k, ids) in ids_by_kind.items()}

    items = []
    for ts, _index, item_id, k in window:
        row = rows_by_kind[k.key].get(item_id)
        if row is None:  # vanished between the two reads
            continue
        row = dict(row, kind=k.key)
        row['file_missing'] = _file_missing(row)
        row['approved'] = row['status'] == k.status_for('approve')
        if view == VIEW_PENDING:
            days = _days_waiting(ts, now)
            row['days_waiting'] = days
            row['overdue'] = days > OVERDUE_DAYS
        else:
            row['days_waiting'] = None
            row['overdue'] = False
        items.append(row)

    return {
        'items': items,
        'total': total,
        'page': page,
        'pages': pages,
        'per_page': per_page,
        'counts': counts,
        'kinds': [(k.key, k.label) for k in kinds],
        'view': view,
    }


def pending_total(actor) -> int:
    """Pending items the actor may decide, in scope (nav badge): one count per visible kind."""
    kinds = visible_kinds(actor)
    if not kinds:
        return 0
    program_ids = scope_service.accessible_program_ids(actor)
    if program_ids is not None and not program_ids:
        return 0
    return sum(_count(k.pending_query(program_ids), k) for k in kinds)


def program_options(actor) -> list:
    """[(id, name)] of the programs in the actor's scope, for the filter select."""
    from app.services import review_service
    return [(p.id, p.name) for p in review_service.reviewable_programs(actor)]


def get_row(actor, kind: str, item_uuid) -> dict:
    """
    The inbox row of one item (for the decision modal), plus 'pending'.

    Same refusals as `review_engine.decide`: unknown kind or item outside the
    actor's scope -> ReviewNotFound (404), no decision permission ->
    ReviewForbidden (403). Read-only: the item is loaded WITHOUT a row lock
    (only `review_engine.decide` locks), so opening the modal never blocks
    a concurrent decision.
    """
    from app.services.review_engine import ReviewForbidden, ReviewNotFound, get_kind

    kind_obj = get_kind(kind)
    if actor is None or not actor.has_permission(kind_obj.permission):
        raise ReviewForbidden('No tienes permiso para decidir este tipo de revisión.')
    item = kind_obj.load(item_uuid)
    if item is None or not scope_service.program_in_scope(actor, kind_obj.program_id(item)):
        raise ReviewNotFound(kind_obj.not_found_message)
    row = dict(kind_obj.row(item), kind=kind_obj.key, pending=kind_obj.is_pending(item))
    row['file_missing'] = _file_missing(row)
    row['approved'] = row['status'] == kind_obj.status_for('approve')
    return row


def min_extension_date() -> str:
    """Earliest `granted_until` the decision modal offers (ISO date): tomorrow.

    The engine refuses a grant that is already over (`ExtensionKind.apply`);
    this only keeps the date picker from offering past days.
    """
    return (now_local().date() + timedelta(days=1)).isoformat()

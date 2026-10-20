"""Context for the applicant admission panel when it is re-rendered as a fragment.

The admission screen mutates documents (upload / replace / delete) and refreshes
itself without a full reload. Each mutation runs the SAME service as the JSON
API (``submissions_service``), recomputes ``get_admission_state`` exactly once
and hands the page route everything the partials need.

Framework-agnostic: the route passes the user and the raw inputs.
"""
from __future__ import annotations

from typing import Iterable, Optional

from app.services import programs_service, submissions_service
from app.services.admission_service import get_admission_state
from app.services.errors import NotFoundError
from app.services.submissions_service import NotEnrolled

#: ``admission_status`` values for which the page shows a status banner instead of
#: the document tabs (mirrors ``_body.html``).
BANNER_STATUSES = frozenset({'interview_completed', 'deliberation', 'accepted', 'rejected'})


def item_key(item: dict):
    """Public key of a processed step: the combined id or the step id."""
    return item['id'] if item['is_combined'] else item['step'].id


def pane_dom_id(item: dict) -> str:
    return f"pane-{item_key(item)}"


def _item_has_step(item: dict, step_id: int) -> bool:
    if item['is_combined']:
        return step_id in (item['step1'].id, item['step2'].id)
    return item['step'].id == step_id


def _csv(value: Optional[str]) -> set[str]:
    return {part.strip() for part in (value or '').split(',') if part.strip()}


def _resolve_program(slug: str):
    program = programs_service.find_program_by_slug(slug)
    if program is None:
        raise NotFoundError("Programa no encontrado.", code='PROGRAM_NOT_FOUND')
    return program


def _resolve_enrollment(user, program):
    up = programs_service.find_user_program(user.id, program.id)
    if not up:
        raise NotEnrolled("Debes inscribirte antes de subir documentos.")
    return up


def build_panel_context(user, program, up, *, active_pane: Optional[str] = None,
                        step_id: Optional[int] = None,
                        client_locked: Iterable[str] | str | None = None) -> dict:
    """State of the panel plus what a fragment needs to know about the swap.

    Args:
        active_pane: DOM id of the pane the browser shows (``pane-12``); used by
            a refresh, where the server cannot know which tab is open.
        step_id: Step a mutation touched; its item becomes the active one.
        client_locked: pane ids whose tab the browser currently shows locked
            (list or comma separated). Only panes whose lock changed are re-sent.

    Returns the ``get_admission_state`` dict plus ``program``, ``active_item``
    (None when the page shows a status banner instead of the tabs) and
    ``stale_items`` (other items whose locked flag differs from the browser's).
    """
    state = get_admission_state(user.id, program.id, up)
    items = state['processed_steps']

    active = None
    if state['admission_status'] not in BANNER_STATUSES and items:
        if step_id is not None:
            active = next((i for i in items if _item_has_step(i, step_id)), None)
        if active is None and active_pane:
            active = next((i for i in items if pane_dom_id(i) == active_pane), None)
        if active is None:
            active = items[0]

    if isinstance(client_locked, str) or client_locked is None:
        client_locked = _csv(client_locked)
    else:
        client_locked = set(client_locked)
    stale = [
        i for i in items
        if i is not active and (pane_dom_id(i) in client_locked) != bool(i['locked'])
    ]
    return {**state, 'program': program, 'active_item': active, 'stale_items': stale}


def panel_for(user, slug: str, *, active_pane: Optional[str] = None) -> dict:
    """Panel context for a plain refresh (realtime events, after an extension)."""
    program = _resolve_program(slug)
    up = _resolve_enrollment(user, program)
    return build_panel_context(user, program, up, active_pane=active_pane)


def upload_document(user, slug: str, archive_uuid, file, *,
                    client_locked: Optional[str] = None) -> dict:
    """Upload / replace one document, then return the refreshed panel context.

    Validation (size, extension, program, enrollment, step locks) is exactly the
    JSON API's: it is the same ``submissions_service.upload_submission``.
    """
    program = _resolve_program(slug)
    sub, archive, program, _ps = submissions_service.upload_submission(
        user, archive_uuid, program.id, None, file)
    submissions_service.notify_new_submission(user, sub, archive, program)

    up = _resolve_enrollment(user, program)
    return build_panel_context(
        user, program, up, step_id=archive.step_id, client_locked=client_locked)


def delete_document(user, slug: str, sub_uuid, *, client_locked: Optional[str] = None) -> dict:
    """Delete the caller's own document of this program, then refresh the panel."""
    program = _resolve_program(slug)
    step_id = submissions_service.delete_own_submission(user.id, sub_uuid, program.id)
    up = _resolve_enrollment(user, program)
    return build_panel_context(
        user, program, up, step_id=step_id, client_locked=client_locked)

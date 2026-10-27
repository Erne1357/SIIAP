"""
Unified review engine (phase 6D): one `decide()` for everything the staff
approves or rejects, over the existing tables.

    from app.services import review_engine
    review_engine.decide(actor, 'permanence_doc', sub_uuid, 'reject', 'Falta firma')
    review_engine.decide(actor, 'permanence_doc', sub_uuid, 'approve',
                         revert_reason='Se revisó de nuevo')   # change a decision

Kinds register themselves on import (see `base.py` for the contract). To add
one, create `review_engine/<name>_kinds.py` calling `register(...)` and list
the module in `_KIND_MODULES` below.
"""
import importlib
import importlib.util

from app.services.review_engine.base import VALID_DECISIONS, Decision, ReviewKind
from app.services.review_engine.engine import decide, decide_item
from app.services.review_engine.errors import (
    ReviewConflict, ReviewError, ReviewForbidden, ReviewNotFound,
)
from app.services.review_engine.registry import KINDS, get_kind, register

#: Modules that register kinds, imported in this order. A module that does
#: not exist yet is skipped, so a later wave only adds its file (and, if it
#: is not listed here, one line).
_KIND_MODULES = (
    'submission_kinds',   # admission_doc, permanence_doc, leave_request, conclusion_doc
    'acceptance_kinds',   # phase 6D wave 2: enrollment_receipt
    'extension_kinds',    # phase 6D wave 2: extension
)

for _name in _KIND_MODULES:
    _module = f'{__name__}.{_name}'
    if importlib.util.find_spec(_module) is not None:
        importlib.import_module(_module)

__all__ = [
    'KINDS', 'VALID_DECISIONS', 'Decision', 'ReviewConflict', 'ReviewError',
    'ReviewForbidden', 'ReviewKind', 'ReviewNotFound', 'decide', 'decide_item',
    'get_kind', 'register',
]

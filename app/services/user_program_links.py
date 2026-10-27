# app/services/user_program_links.py
"""
Resolve which UserProgram a document or request belongs to.

`Submission` and `ExtensionRequest` used to be keyed by `user_id` only; the
program came from `program_step.program_id`. A user may hold several
programs, so new rows also store `user_program_id`, resolved here.
"""
from typing import Optional

from app.models.program_step import ProgramStep
from app.models.user_program import UserProgram


def resolve_user_program_id(user_id: int, program_step_id: int) -> Optional[int]:
    """UserProgram of `user_id` in the program that owns `program_step_id`, or None."""
    step = ProgramStep.query.get(program_step_id)
    if step is None:
        return None
    up = UserProgram.query.filter_by(user_id=user_id, program_id=step.program_id).first()
    return up.id if up else None

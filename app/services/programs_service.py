# app/services/programs_service.py
from sqlalchemy.orm import joinedload, selectinload
from app import db
from app.models.program import Program
from app.models.step import Step
from app.models.program_step import ProgramStep
from app.models.user_program import UserProgram

class AlreadyEnrolledError(Exception): ...
class ProgramNotFound(Exception): ...

def list_programs():
    return Program.query.order_by(Program.name).all()

def get_program_by_slug(slug: str):
    program = (Program.query.filter_by(slug=slug)
        .options(
            joinedload(Program.program_steps)
              .joinedload(ProgramStep.step)
              .joinedload(Step.phase),
            joinedload(Program.program_steps)
              .joinedload(ProgramStep.step)
              .selectinload(Step.archives)
        )
        .first())
    if not program:
        raise ProgramNotFound()
    return program

def enroll_user_once(program_id: int, user_id: int):
    program = Program.query.get(program_id)
    if not program:
        raise ProgramNotFound()

    already = UserProgram.query.filter_by(user_id=user_id).first()
    if already:
        raise AlreadyEnrolledError("Ya estás inscrito en un programa.")

    db.session.add(UserProgram(user_id=user_id, program_id=program.id))
    db.session.commit()
    return program

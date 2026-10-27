"""World shared by the review engine tests (phase 6D)."""
from types import SimpleNamespace

import pytest

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission
from app.models.semester_enrollment import SemesterEnrollment
from tests.support.factories import (
    enroll, get_or_create_role, grant, make_academic_period, make_program, make_user,
)

DECIDE_PERMS = ('admin_review.api.decide', 'permanence.api.review_doc')


def _phase(name):
    phase = Phase.query.filter_by(name=name).first()
    if phase is None:
        phase = Phase(name=name, description=name)
        db.session.add(phase)
        db.session.flush()
    return phase


def _step(phase_name, name, programs):
    step = Step(name=name, description=name, phase_id=_phase(phase_name).id)
    db.session.add(step)
    db.session.flush()
    for program in programs:
        db.session.add(ProgramStep(sequence=1, program_id=program.id, step_id=step.id))
    db.session.flush()
    return step


def _archive(step, name, key=None):
    archive = Archive(name=name, description=name, file_path=None, step_id=step.id)
    archive.archive_key = key
    db.session.add(archive)
    db.session.flush()
    return archive


@pytest.fixture
def world(app):
    coord_role = get_or_create_role('program_admin')
    grant(coord_role, *DECIDE_PERMS)
    pg_role = get_or_create_role('postgraduate_admin')
    grant(pg_role, *DECIDE_PERMS, 'academic_periods.api.create')

    coordinator = make_user('program_admin')
    other_coordinator = make_user('program_admin')
    postgrad = make_user('postgraduate_admin')
    program = make_program(coordinator)
    other_program = make_program(other_coordinator)
    period = make_academic_period()

    student = make_user('student')
    up = enroll(student, program, 'enrolled')
    up.academic_status = 'active'
    up.current_semester = 2
    enrollment = SemesterEnrollment(user_program_id=up.id, academic_period_id=period.id,
                                    semester_number=2, status='active',
                                    enrollment_confirmed=True)
    db.session.add(enrollment)

    other_student = make_user('student')
    other_up = enroll(other_student, other_program, 'enrolled')
    other_up.academic_status = 'active'

    programs = (program, other_program)
    admission_doc = _archive(_step('admission', 'Documentos', programs), 'Acta de nacimiento')
    permanence_step = _step('permanence', 'Permanencia', programs)
    permanence_doc = _archive(permanence_step, 'Constancia de calificaciones')
    leave_doc = _archive(permanence_step, 'Solicitud de Baja Temporal', 'leave_request')
    conclusion_doc = _archive(_step('conclusion', 'Requisitos Generales', programs),
                              'Documento de Tesis Final', 'conclusion_thesis_document')
    db.session.commit()

    def submit(archive, status=None, owner=None):
        owner = owner or up
        if status is None:
            status = 'review' if archive.step.phase.name == 'permanence' else 'pending'
        ps = ProgramStep.query.filter_by(program_id=owner.program_id,
                                         step_id=archive.step_id).first()
        sub = Submission(file_path=f'{owner.user_id}/x/{archive.id}.pdf', status=status,
                         user_id=owner.user_id, archive_id=archive.id, program_step_id=ps.id,
                         semester=2, user_program_id=owner.id)
        sub.academic_period_id = period.id
        db.session.add(sub)
        db.session.commit()
        return sub

    return SimpleNamespace(
        coordinator=coordinator, other_coordinator=other_coordinator, postgrad=postgrad,
        program=program, other_program=other_program, period=period, student=student,
        up=up, enrollment=enrollment, other_student=other_student, other_up=other_up,
        archives={'admission_doc': admission_doc, 'permanence_doc': permanence_doc,
                  'leave_request': leave_doc, 'conclusion_doc': conclusion_doc},
        submit=submit,
    )

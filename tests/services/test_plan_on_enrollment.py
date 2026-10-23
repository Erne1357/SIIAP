"""Enrolling a student ties them to the program's current study plan (phase 6B1)."""

import io

import pytest
from werkzeug.datastructures import FileStorage

from app import db
from app.models.curriculum_plan import CurriculumPlan
from app.models.user_program import UserProgram
from app.services import acceptance_service as svc
from app.services import student_bulk_service
from tests.support.factories import (
    enroll, get_or_create_role, make_academic_period, make_program, make_user,
)


def _file():
    return FileStorage(stream=io.BytesIO(b'%PDF-1.4 x'), filename='d.pdf',
                       content_type='application/pdf')


def _plan(program, *, current=True, version=1):
    plan = CurriculumPlan(program_id=program.id, version=version,
                          name=f'Plan v{version}', is_current=current)
    db.session.add(plan)
    db.session.flush()
    return plan


@pytest.fixture
def acc(app):
    get_or_create_role('student')
    coord = make_user('program_admin')
    program = make_program(coord)
    applicant = make_user('applicant')
    period = make_academic_period('20261')
    up = enroll(applicant, program, 'accepted')
    up.admission_period_id = period.id
    db.session.commit()
    return type('A', (), dict(coord=coord, program=program, applicant=applicant, up=up))


def _approve_receipt(a):
    svc.upload_coordinator_doc(a.applicant.id, a.program.id, 'acceptance_letter', _file(), a.coord.id)
    svc.upload_coordinator_doc(a.applicant.id, a.program.id, 'course_schedule', _file(), a.coord.id)
    doc = svc.submit_enrollment_receipt(a.applicant.id, a.program.id, _file(), a.applicant.id)
    svc.review_enrollment_receipt(doc.id, a.coord.id, 'approved')


def test_control_number_sets_current_plan(acc):
    _plan(acc.program, current=False, version=1)
    current = _plan(acc.program, current=True, version=2)
    _approve_receipt(acc)
    up = svc.assign_control_number(acc.applicant.id, acc.program.id, 'M1', acc.coord.id)
    assert up.curriculum_plan_id == current.id


def test_control_number_without_plan_leaves_none(acc):
    _approve_receipt(acc)
    up = svc.assign_control_number(acc.applicant.id, acc.program.id, 'M2', acc.coord.id)
    assert up.curriculum_plan_id is None


def test_existing_plan_is_not_overwritten(acc):
    old = _plan(acc.program, current=False, version=1)
    _plan(acc.program, current=True, version=2)
    acc.up.curriculum_plan_id = old.id
    db.session.commit()
    _approve_receipt(acc)
    up = svc.assign_control_number(acc.applicant.id, acc.program.id, 'M3', acc.coord.id)
    assert up.curriculum_plan_id == old.id


def test_bulk_created_student_gets_current_plan(app):
    get_or_create_role('student')
    admin = make_user('postgraduate_admin')
    program = make_program(make_user('program_admin'), duration_semesters=4)
    plan = _plan(program)
    period = make_academic_period('20221')
    db.session.commit()
    result = student_bulk_service.create_student_individual({
        'first_name': 'Pedro', 'last_name': 'Lopez', 'mother_last_name': 'Soto',
        'email': 'pedro.plan@test.local', 'control_number': 'M22110098',
        'program_slug': program.slug, 'current_semester': 1,
        'admission_period_code': period.code, 'has_conacyt': False,
    }, created_by_id=admin.id)
    up = db.session.get(UserProgram, result['user_program_id'])
    assert up.curriculum_plan_id == plan.id

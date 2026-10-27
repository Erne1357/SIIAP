"""Phase 6B3 Task B: informative PDFs (kardex, report card, acta)."""

import pytest

from app import db
from app.models.course_enrollment import CourseEnrollment
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from app.schemas.curriculum import CourseGroupIn
from app.services import academic_documents_service as docs
from app.services import course_enrollment_service as enroll_svc
from app.services import course_group_service as group_svc
from app.services import grading_service as grading
from app.services.errors import DomainError, NotFoundError
from tests.support.factories import (
    enroll, grant, make_academic_period, make_program, make_user,
)

RECORD = ('students.page.view_record', 'students.api.view_record', 'kardex.page.export_pdf')

#: a page-level permission denial redirects (see permissions._abort_403)
DENIED = (302, 303, 403)


@pytest.fixture
def fake_pdf(monkeypatch):
    """Skip weasyprint in route tests; keep the rendered HTML for assertions."""
    seen = {}
    real_render = docs.render_template

    def fake(template, **ctx):
        seen['html'] = real_render(template, **ctx)
        return b'%PDF-fake'

    monkeypatch.setattr(docs, 'render_pdf', lambda template, **ctx: fake(template, **ctx))
    return seen


@pytest.fixture
def w(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    program = make_program(coord)
    make_program(other)
    plan = CurriculumPlan(program_id=program.id, version=2, name='Plan', is_current=True)
    db.session.add(plan)
    db.session.flush()
    math = Subject(plan_id=plan.id, name='Matemáticas', key='MAT', credits=5,
                   suggested_semester=1, kind='required', sequence=0)
    algo = Subject(plan_id=plan.id, name='Algoritmos', key='ALG', credits=4,
                   suggested_semester=1, kind='required', sequence=1)
    db.session.add_all([math, algo])
    db.session.flush()
    period = make_academic_period()
    teacher, other_teacher = make_user('teacher'), make_user('teacher')
    student = make_user('student', first_name='Ana', last_name='Zapata',
                        control_number='M2100001')
    up = enroll(student, program, admission_status='enrolled')
    UserProgram.query.filter_by(id=up.id).update(
        {'academic_status': 'active', 'curriculum_plan_id': plan.id, 'current_semester': 1})
    db.session.expire(up)
    grant(student.role, 'kardex.page.view_own', 'kardex.page.export_own_pdf')
    grant(coord.role, *RECORD, 'grades.page.export_acta')
    grant(other.role, *RECORD, 'grades.page.export_acta')
    grant(teacher.role, 'grades.page.export_acta')
    w = {'coord': coord, 'other': other, 'program': program, 'plan': plan, 'math': math,
         'algo': algo, 'period': period, 'teacher': teacher, 'other_teacher': other_teacher,
         'student': student, 'up': up}
    w['group'] = group_svc.save_group(program.id, CourseGroupIn(
        subject_id=math.id, academic_period_id=period.id, group_code='A', capacity=10,
        teacher_id=teacher.id), coord.id)
    w['enrollment'] = enroll_svc.enroll(w['group'].id, up.id, coord.id)
    return w


def _close(w):
    grading.save_draft(w['group'].id, {w['enrollment'].id: '85'}, w['teacher'].id)
    grading.close_acta(w['group'].id, w['teacher'].id)


def _add_enrolled_algo(w):
    row = CourseEnrollment(user_program_id=w['up'].id, subject_id=w['algo'].id,
                           academic_period_id=w['period'].id, attempt=1,
                           attempt_type='ordinary', status='enrolled')
    db.session.add(row)
    db.session.flush()


def _record_url(w, tail='kardex.pdf'):
    return f"/academic-documents/students/{w['student'].uuid}/{tail}"


# ---------------------------------------------------------------- service
def test_report_card_shows_en_captura_for_enrolled_rows(w):
    _add_enrolled_algo(w)
    ctx = docs.report_card_context(w['up'].id, w['period'].id)
    by_name = {r['name']: r for r in ctx['rows']}
    assert by_name['Algoritmos']['value'] == 'En captura'
    assert by_name['Matemáticas']['group'] == 'A'
    assert ctx['average'] is None


def test_report_card_average_counts_passed_grades(w):
    _close(w)
    ctx = docs.report_card_context(w['up'].id, w['period'].id)
    assert ctx['average'] == 85
    assert ctx['rows'][0]['result'] == 'Aprobada'


def test_report_card_unknown_period_is_not_found(w):
    other = make_academic_period()
    with pytest.raises(NotFoundError):
        docs.report_card_context(w['up'].id, other.id)


def test_periods_of_lists_only_periods_with_rows(w):
    make_academic_period()
    assert [p.id for p in docs.periods_of(w['up'].id)] == [w['period'].id]


def test_acta_context_requires_closed_acta(w):
    with pytest.raises(DomainError, match='aún no está cerrada'):
        docs.acta_context(w['group'].id)
    _close(w)
    assert docs.acta_context(w['group'].id)['rows'][0]['value'] == '85'


def test_safe_filename_sanitizes():
    assert docs.safe_filename('acta', 'A/B C', None, 'ñ1') == 'acta_A-B-C_-1'


# ---------------------------------------------------------------- own routes
def test_own_kardex_pdf(w, login, fake_pdf):
    res = login(w['student']).get('/academic-documents/kardex.pdf')
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert res.data == b'%PDF-fake'
    assert 'kardex_M2100001.pdf' in res.headers['Content-Disposition']
    html = fake_pdf['html']
    assert 'Documento informativo, sin validez oficial' in html
    assert 'Ana Zapata' in html and 'M2100001' in html and 'Versión 2' in html


def test_own_kardex_without_permission_is_403(w, login, fake_pdf):
    other_student = make_user('applicant')
    enroll(other_student, w['program'], admission_status='enrolled')
    assert login(other_student).get('/academic-documents/kardex.pdf').status_code in DENIED


def test_own_report_card_pdf(w, login, fake_pdf):
    _add_enrolled_algo(w)
    res = login(w['student']).get(f"/academic-documents/report-card/{w['period'].id}.pdf")
    assert res.status_code == 200 and res.mimetype == 'application/pdf'
    assert f"boleta_M2100001_{w['period'].code}.pdf" in res.headers['Content-Disposition']
    assert 'En captura' in fake_pdf['html']


def test_own_report_card_unknown_period_is_404(w, login, fake_pdf):
    other = make_academic_period()
    res = login(w['student']).get(f'/academic-documents/report-card/{other.id}.pdf')
    assert res.status_code == 404


def test_foreign_program_param_is_404(w, login, fake_pdf):
    res = login(w['student']).get('/academic-documents/kardex.pdf?program=999999')
    assert res.status_code == 404


# ---------------------------------------------------------------- record routes
def test_coordinator_in_scope_downloads(w, login, fake_pdf):
    res = login(w['coord']).get(_record_url(w))
    assert res.status_code == 200 and res.mimetype == 'application/pdf'
    res = login(w['coord']).get(_record_url(w, f"report-card/{w['period'].id}.pdf"))
    assert res.status_code == 200


def test_other_coordinator_gets_404(w, login, fake_pdf):
    assert login(w['other']).get(_record_url(w)).status_code == 404
    assert login(w['other']).get(
        _record_url(w, f"report-card/{w['period'].id}.pdf")).status_code == 404


def test_unknown_student_is_the_same_404(w, login, fake_pdf):
    res = login(w['coord']).get('/academic-documents/students/'
                                '00000000-0000-0000-0000-000000000000/kardex.pdf')
    assert res.status_code == 404


def test_student_cannot_use_record_route(w, login, fake_pdf):
    assert login(w['student']).get(_record_url(w)).status_code in DENIED


# ---------------------------------------------------------------- acta
def _acta_url(w):
    return f"/academic-documents/groups/{w['group'].uuid}/acta.pdf"


def test_open_acta_is_refused(w, login, fake_pdf):
    res = login(w['teacher']).get(_acta_url(w))
    assert res.status_code in (302, 303)   # DomainError on a page: redirect + flash


def test_closed_acta_for_teacher_and_coordinator(w, login, fake_pdf):
    _close(w)
    res = login(w['teacher']).get(_acta_url(w))
    assert res.status_code == 200 and res.mimetype == 'application/pdf'
    assert f"acta_MAT_A_{w['period'].code}.pdf" in res.headers['Content-Disposition']
    assert 'Nombre y firma del docente' in fake_pdf['html']
    assert login(w['coord']).get(_acta_url(w)).status_code == 200


def test_acta_of_another_teacher_or_coordinator_is_404(w, login, fake_pdf):
    _close(w)
    assert login(w['other_teacher']).get(_acta_url(w)).status_code == 404
    assert login(w['other']).get(_acta_url(w)).status_code == 404


# ---------------------------------------------------------------- real render
def test_real_weasyprint_render_of_kardex(w, app):
    _add_enrolled_algo(w)
    with app.test_request_context():
        pdf = docs.render_pdf('pdf/kardex.html', **docs.kardex_context(w['up'].id))
    assert pdf.startswith(b'%PDF')

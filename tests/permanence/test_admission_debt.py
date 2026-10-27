"""
Phase 6C, owner's decision 5: an admission document with a granted extension
(prórroga) whose `granted_until` passed undelivered blocks re-enrolling in the
next semester until it is delivered; the enrolled student sees and uploads it.
"""
import io
from datetime import timedelta
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from app import db
from app.models import Archive, ExtensionRequest, Phase, ProgramStep, Step, Submission
from app.models.semester_enrollment import SemesterEnrollment
from app.models.user_program import UserProgram
from app.services import admission_debt_service as debt
from app.services import permanence_service, semester_transition_service
from app.services.errors import DomainError, NotFoundError
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, grant, make_academic_period, make_program, make_user

HX = {'HX-Request': 'true'}


def _naive_now():
    return now_local().replace(tzinfo=None)


def _pdf(name='titulo.pdf'):
    return FileStorage(stream=io.BytesIO(b'%PDF-1.4 test'), filename=name,
                       content_type='application/pdf')


@pytest.fixture
def w(app):
    coord = make_user('program_admin')
    program = make_program(coord)
    student = make_user('student')
    up = enroll(student, program, 'enrolled')
    UserProgram.query.filter_by(id=up.id).update({'academic_status': 'active'})

    phase = Phase.query.filter_by(name='admission').first()
    if phase is None:
        phase = Phase(name='admission', description='admission')
        db.session.add(phase)
        db.session.flush()
    step = Step(name='Requisitos de Maestrías', description='r', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    ps = ProgramStep(sequence=1, program_id=program.id, step_id=step.id)
    db.session.add(ps)
    db.session.flush()
    title = Archive(name='Título de Licenciatura', description='t', file_path=None,
                    step_id=step.id)
    cv = Archive(name='Curriculum Vitae', description='cv', file_path=None, step_id=step.id)
    db.session.add_all([title, cv])
    db.session.flush()

    ext = ExtensionRequest(user_id=student.id, archive_id=title.id, program_step_id=ps.id,
                           requested_by=student.id, reason='Título en trámite',
                           requested_until=_naive_now() - timedelta(days=1),
                           user_program_id=up.id)
    ext.status = 'granted'
    ext.granted_until = _naive_now() - timedelta(days=1)
    db.session.add(ext)

    source = make_academic_period(is_active=True)
    target = make_academic_period(is_active=False)
    db.session.add(SemesterEnrollment(user_program_id=up.id, academic_period_id=source.id,
                                      semester_number=1, status='active',
                                      enrollment_confirmed=True))
    grant(student.role, 'submissions.api.create', 'permanence.api.view_status')
    db.session.commit()
    return SimpleNamespace(coord=coord, program=program, student=student, up=up, ps=ps,
                           title=title, cv=cv, ext=ext, source=source, target=target)


def _submit(w, status):
    sub = Submission(file_path=f'{w.student.id}/admission/t.pdf', status=status,
                     user_id=w.student.id, archive_id=w.title.id, program_step_id=w.ps.id,
                     semester=0, user_program_id=w.up.id)
    db.session.add(sub)
    db.session.commit()
    return sub


def _codes(w):
    result = semester_transition_service.evaluate_student(w.up.id, w.source.id, w.target.id)
    return [b['code'] for b in result['blockers']]


def test_overdue_undelivered_document_blocks_re_enrollment(w):
    docs = debt.overdue_admission_documents(w.up)
    assert [d['archive'].name for d in docs] == ['Título de Licenciatura']
    assert 'admission_document_debt' in _codes(w)
    with pytest.raises(DomainError, match='Título de Licenciatura'):
        permanence_service.confirm_semester_enrollment(w.up.id, w.target.id, w.coord.id,
                                                       force=True)
    db.session.rollback()
    assert SemesterEnrollment.query.filter_by(academic_period_id=w.target.id).count() == 0


def test_extension_still_in_force_does_not_block(w):
    w.ext.granted_until = _naive_now() + timedelta(days=5)
    db.session.commit()
    assert debt.overdue_admission_documents(w.up) == []
    assert 'admission_document_debt' not in _codes(w)
    # Still visible to the student: they owe it, just not yet overdue.
    assert [d['archive'].id for d in debt.pending_extension_documents(w.up)] == [w.title.id]


def test_delivered_document_unblocks_and_rejected_reblocks(w):
    sub = _submit(w, 'pending')
    assert debt.overdue_admission_documents(w.up) == []
    assert 'admission_document_debt' not in _codes(w)
    sub.status = 'rejected'
    db.session.commit()
    assert 'admission_document_debt' in _codes(w)
    sub.status = 'approved'
    db.session.commit()
    assert debt.pending_extension_documents(w.up) == []
    permanence_service.confirm_semester_enrollment(w.up.id, w.target.id, w.coord.id, force=True)


def _reject(w, **kw):
    w.ext.status = 'rejected'
    w.ext.granted_until = None
    w.ext.decided_at = _naive_now() - timedelta(hours=2)
    for k, v in kw.items():
        setattr(w.ext, k, v)
    db.session.commit()


def test_rejected_undelivered_extension_blocks(w):
    _reject(w)
    docs = debt.overdue_admission_documents(w.up)
    assert [d['archive'].id for d in docs] == [w.title.id] and docs[0]['rejected']
    assert 'admission_document_debt' in _codes(w)
    assert 'rechazada' in debt.debt_message(docs)


def test_rejected_while_applicant_without_up_link_still_blocks(w):
    _reject(w, user_program_id=None)
    assert len(debt.overdue_admission_documents(w.up)) == 1


def test_rejected_then_later_granted_not_expired_does_not_block(w):
    _reject(w)
    later = ExtensionRequest(user_id=w.student.id, archive_id=w.title.id,
                             program_step_id=w.ps.id, requested_by=w.student.id,
                             reason='otra', requested_until=_naive_now() + timedelta(days=9),
                             user_program_id=w.up.id)
    later.status = 'granted'
    later.decided_at = _naive_now() - timedelta(hours=1)
    later.granted_until = _naive_now() + timedelta(days=9)
    db.session.add(later)
    db.session.commit()
    assert debt.overdue_admission_documents(w.up) == []
    assert 'admission_document_debt' not in _codes(w)


def test_granted_then_later_rejected_blocks(w):
    w.ext.granted_until = _naive_now() + timedelta(days=9)
    w.ext.decided_at = _naive_now() - timedelta(hours=3)
    later = ExtensionRequest(user_id=w.student.id, archive_id=w.title.id,
                             program_step_id=w.ps.id, requested_by=w.student.id,
                             reason='otra', requested_until=_naive_now() + timedelta(days=9),
                             user_program_id=w.up.id)
    later.status = 'rejected'
    later.decided_at = _naive_now() - timedelta(hours=1)
    db.session.add(later)
    db.session.commit()
    assert len(debt.overdue_admission_documents(w.up)) == 1


def test_delivered_document_unblocks_a_rejected_extension(w):
    _reject(w)
    sub = _submit(w, 'pending')
    assert debt.overdue_admission_documents(w.up) == []
    assert 'admission_document_debt' not in _codes(w)
    sub.status = 'rejected'
    db.session.commit()
    assert 'admission_document_debt' in _codes(w)


def test_upload_allowed_for_a_rejected_extension(w):
    _reject(w)
    assert [d['archive'].id for d in debt.pending_extension_documents(w.up)] == [w.title.id]
    sub = debt.upload_extension_document(w.student, w.up.id, w.title.uuid, _pdf())
    assert sub.status == 'pending'
    assert debt.overdue_admission_documents(w.up) == []


def test_dashboard_shows_rejected_extension(w, login):
    _reject(w)
    html = login(w.student).get('/user/dashboard').get_data(as_text=True)
    assert 'Prórroga rechazada' in html and 'Título de Licenciatura' in html


def test_enrolled_student_uploads_overdue_document(w):
    sub = debt.upload_extension_document(w.student, w.up.id, w.title.uuid, _pdf())
    assert sub.status == 'pending' and sub.archive_id == w.title.id
    assert debt.overdue_admission_documents(w.up) == []
    assert 'admission_document_debt' not in _codes(w)


def test_upload_only_for_archives_with_a_granted_extension(w):
    with pytest.raises(NotFoundError):
        debt.upload_extension_document(w.student, w.up.id, w.cv.uuid, _pdf())
    other = make_user('student')
    db.session.commit()
    with pytest.raises(NotFoundError):
        debt.upload_extension_document(other, w.up.id, w.title.uuid, _pdf())


def test_dashboard_lists_and_uploads_the_document(w, login):
    c = login(w.student)
    html = c.get('/user/dashboard').get_data(as_text=True)
    assert 'Documentos de admisión con prórroga' in html
    assert 'Título de Licenciatura' in html
    assert 'No podrás reinscribirte' in html

    res = c.post(f'/user/dashboard/extension-documents/{w.title.uuid}', headers=HX,
                 data={'user_program': w.up.id, 'file': (io.BytesIO(b'%PDF-1.4 x'), 't.pdf')},
                 content_type='multipart/form-data')
    assert res.status_code == 200
    assert 'siiap:flash' in res.headers.get('HX-Trigger', '')
    assert 'En revisión' in res.get_data(as_text=True)
    assert Submission.query.filter_by(archive_id=w.title.id, status='pending').count() == 1

    res = c.post(f'/user/dashboard/extension-documents/{w.cv.uuid}', headers=HX,
                 data={'user_program': w.up.id, 'file': (io.BytesIO(b'%PDF-1.4 x'), 'c.pdf')},
                 content_type='multipart/form-data')
    assert res.status_code == 404


def test_coordinator_sees_the_blocker_in_the_trajectory_tab(w, login):
    grant(w.coord.role, 'students.page.view_record', 'students.api.view_record')
    db.session.commit()
    res = login(w.coord).get(f'/students/{w.student.uuid}/record/trajectory', headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'trajectoryAdmissionDebt' in html and 'Título de Licenciatura' in html

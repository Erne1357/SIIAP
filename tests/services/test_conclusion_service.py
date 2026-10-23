"""conclusion_service: thesis, committees, conditions, requirements, grade exam, titling."""

import io
import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from app.utils.datetime_utils import now_local
from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission
from app.models.admission_condition import AdmissionCondition
from app.models.thesis import ThesisMember
from app.models.user_history import UserHistory
from app.models.notification import Notification
from app.services import conclusion_service as svc
from app.services import deliberation_service
from app.services.errors import ConflictError, DomainError, NotFoundError
from tests.support.factories import enroll, get_or_create_role, grant, make_program, make_user


# ─── Builders ────────────────────────────────────────────────────────────────

def _phase(name):
    phase = Phase.query.filter_by(name=name).first()
    if phase is None:
        phase = Phase(name=name, description=name)
        db.session.add(phase)
        db.session.flush()
    return phase


def _step(phase_name, name, program, sequence=1):
    step = Step(name=name, description=name, phase_id=_phase(phase_name).id)
    db.session.add(step)
    db.session.flush()
    db.session.add(ProgramStep(sequence=sequence, program_id=program.id, step_id=step.id))
    db.session.flush()
    return step


def _archive(step, name, key=None, institution=False):
    archive = Archive(name=name, description=name, file_path=None, step_id=step.id)
    archive.archive_key = key
    archive.issued_by_institution = institution
    archive.allow_coordinator_upload = institution
    db.session.add(archive)
    db.session.flush()
    return archive


def _submit(up, archive, status='approved'):
    ps = ProgramStep.query.filter_by(program_id=up.program_id, step_id=archive.step_id).first()
    sub = Submission(file_path=f'{up.user_id}/x/{archive.id}.pdf', status=status,
                     user_id=up.user_id, archive_id=archive.id, program_step_id=ps.id,
                     semester=None, user_program_id=up.id)
    db.session.add(sub)
    db.session.flush()
    return sub


def _set_status(up, status):
    type(up).query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


def _pdf(name='doc.pdf'):
    return FileStorage(stream=io.BytesIO(b'%PDF-1.4 test'), filename=name,
                       content_type='application/pdf')


@pytest.fixture
def ctx(app):
    coordinator = make_user('program_admin')
    program = make_program(coordinator)
    student = make_user('student')
    up = enroll(student, program, 'enrolled')
    _set_status(up, 'active')

    adm = _step('admission', 'Requisitos de Maestrías', program, 1)
    title_ms = _archive(adm, 'Título', 'admission_degree_title_ms')
    english_ms = _archive(adm, 'Comprobante Inglés', 'admission_english_ms')

    general = _step('conclusion', 'Requisitos Generales', program, 1)
    prev_degree = _archive(general, 'Título del Grado Anterior', 'conclusion_previous_degree')
    language = _archive(general, 'Constancia de Segundo Idioma', 'conclusion_second_language')
    thesis_doc = _archive(general, 'Documento de Tesis Final', 'conclusion_thesis_document')
    originality = _archive(general, 'Carta de Originalidad', 'conclusion_originality_letter',
                           institution=True)
    _step('conclusion', 'Encuesta Fin de Programa', program, 3)  # no archives

    postgrad_role = get_or_create_role('postgraduate_admin')
    grant(postgrad_role, 'academic_periods.api.create')
    postgrad = make_user('postgraduate_admin')
    db.session.commit()
    return SimpleNamespace(
        coordinator=coordinator, program=program, student=student, up=up, postgrad=postgrad,
        title_ms=title_ms, english_ms=english_ms, prev_degree=prev_degree, language=language,
        thesis_doc=thesis_doc, originality=originality,
    )


def _schedule_past(ctx, when, place='Sala'):
    """Schedule an exam (future, as the service demands) and move it to `when`."""
    exam = svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) + timedelta(days=2), place)
    exam.scheduled_at = when
    db.session.commit()
    return exam


def _ready_for_exam(ctx):
    """Thesis + board + every requirement satisfied, student graduated."""
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Optimización de inventarios')
    for role in ('president', 'secretary', 'vocal'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'exam', role,
                       external_name=f'Dr. {role}', external_institution='UACJ')
    _set_status(ctx.up, 'graduated')
    _submit(ctx.up, ctx.title_ms)
    _submit(ctx.up, ctx.english_ms)
    _submit(ctx.up, ctx.thesis_doc)
    _submit(ctx.up, ctx.originality)
    db.session.commit()


# ─── Thesis and members ──────────────────────────────────────────────────────

def test_register_and_update_thesis_logs_history(ctx):
    thesis = svc.register_thesis(ctx.coordinator, ctx.up.id, '  Mi tesis  ', 'Logística')
    assert thesis.title == 'Mi tesis'
    assert thesis.registered_at == now_local().date()

    svc.update_thesis(ctx.coordinator, ctx.up.id, title='Otra tesis')
    actions = [h.action for h in UserHistory.query.filter_by(user_id=ctx.student.id)]
    assert 'thesis_registered' in actions and 'thesis_updated' in actions

    with pytest.raises(ConflictError):
        svc.register_thesis(ctx.coordinator, ctx.up.id, 'Duplicada')


def test_thesis_needs_a_current_or_graduated_student(ctx):
    _set_status(ctx.up, 'withdrawn')
    with pytest.raises(DomainError, match='baja definitiva'):
        svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')


def test_out_of_scope_coordinator_gets_not_found(ctx):
    other = make_user('program_admin')
    make_program(other)
    db.session.commit()
    with pytest.raises(NotFoundError, match=svc.STUDENT_NOT_FOUND_MESSAGE):
        svc.register_thesis(other, ctx.up.id, 'Tesis')
    with pytest.raises(NotFoundError, match=svc.STUDENT_NOT_FOUND_MESSAGE):
        svc.register_thesis(other, 999999, 'Tesis')


def test_members_validate_role_body_and_person(ctx):
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    teacher = make_user('program_admin')
    inactive = make_user('program_admin', is_active=False)
    db.session.commit()

    director = svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'director', user_id=teacher.id)
    assert director.display_name.startswith('Prueba')

    with pytest.raises(DomainError, match='no corresponde'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'president', external_name='X')
    with pytest.raises(ConflictError, match='ya tiene'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'director', external_name='Otro')
    with pytest.raises(DomainError, match='inactivo'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'advisor', user_id=inactive.id)
    with pytest.raises(DomainError, match='externo es obligatorio'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'advisor')
    with pytest.raises(DomainError, match='no ambos'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'advisor',
                       user_id=teacher.id, external_name='X')

    advisor = svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'advisor',
                             external_name='Dra. Externa', external_institution='UNAM')
    assert advisor.is_external
    svc.remove_member(ctx.coordinator, ctx.up.id, advisor.id)
    assert db.session.get(ThesisMember, advisor.id) is None
    actions = [h.action for h in UserHistory.query.filter_by(user_id=ctx.student.id)]
    assert actions.count('thesis_member_added') == 2
    assert 'thesis_member_removed' in actions


def test_database_enforces_one_director(ctx):
    thesis = svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    db.session.add(ThesisMember(thesis_id=thesis.id, body='tutorial', role='director',
                                external_name='A'))
    db.session.add(ThesisMember(thesis_id=thesis.id, body='tutorial', role='director',
                                external_name='B'))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_my_theses_lists_tutorial_memberships(ctx):
    teacher = make_user('program_admin')
    db.session.commit()
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'codirector', user_id=teacher.id)

    rows = svc.my_theses(teacher)
    assert len(rows) == 1
    assert rows[0]['roles'] == ['codirector']
    assert rows[0]['student'].id == ctx.student.id
    assert svc.my_theses(ctx.coordinator) == []


# ─── Requirements, reuse and conditions ──────────────────────────────────────

def _by_key(items):
    return {i['archive'].archive_key: i for i in items}


def test_requirements_states_and_reuse(ctx):
    _submit(ctx.up, ctx.title_ms)                        # approved admission title
    _submit(ctx.up, ctx.english_ms, status='pending')    # not approved: no reuse
    _submit(ctx.up, ctx.thesis_doc, status='rejected')
    db.session.commit()

    items = _by_key(svc.requirements(ctx.up))
    assert list(items) == ['conclusion_previous_degree', 'conclusion_second_language',
                           'conclusion_thesis_document', 'conclusion_originality_letter']
    assert items['conclusion_previous_degree']['status'] == 'reused'
    assert items['conclusion_previous_degree']['reused_from'].archive_id == ctx.title_ms.id
    assert items['conclusion_second_language']['status'] == 'missing'
    assert items['conclusion_thesis_document']['status'] == 'rejected'
    assert items['conclusion_originality_letter']['status'] == 'institution_pending'


def test_pending_condition_blocks_reuse(ctx):
    # The condition exists before the admission title is approved (a condition
    # created against an already satisfied requirement is born met).
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Entregar título',
                                archive_uuid=ctx.prev_degree.uuid)
    assert cond.status == 'pending'
    _submit(ctx.up, ctx.title_ms)
    db.session.commit()
    items = _by_key(svc.requirements(ctx.up))
    assert items['conclusion_previous_degree']['status'] == 'missing'
    assert items['conclusion_previous_degree']['blocked_by_condition']

    svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'met')
    assert _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']['status'] == 'reused'


def test_waive_needs_note_and_resolves_once(ctx):
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Promedio mínimo')
    with pytest.raises(DomainError, match='motivo'):
        svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'waived')
    svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'waived',
                          note='Acuerdo del consejo')
    assert cond.status == 'waived' and cond.resolved_by == ctx.coordinator.id
    with pytest.raises(ConflictError):
        svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'met')
    actions = [h.action for h in UserHistory.query.filter_by(user_id=ctx.student.id)]
    assert 'admission_condition_created' in actions
    assert 'admission_condition_resolved' in actions


def test_student_upload_only_after_graduation(ctx):
    with pytest.raises(DomainError, match='después del egreso'):
        svc.upload_requirement(ctx.student, ctx.thesis_doc.uuid, ctx.up.id, _pdf())

    _set_status(ctx.up, 'graduated')
    sub = svc.upload_requirement(ctx.student, ctx.thesis_doc.uuid, ctx.up.id, _pdf())
    assert sub.status == 'pending' and sub.user_program_id == ctx.up.id
    assert sub.file_path.startswith(f'{ctx.student.id}/conclusion/')

    with pytest.raises(DomainError, match='emite la institución'):
        svc.upload_requirement(ctx.student, ctx.originality.uuid, ctx.up.id, _pdf())

    other = make_user('student')
    db.session.commit()
    with pytest.raises(NotFoundError):
        svc.upload_requirement(other, ctx.thesis_doc.uuid, ctx.up.id, _pdf())


def test_upload_lands_in_the_conclusion_review_inbox(ctx):
    from app.services import review_service

    _set_status(ctx.up, 'graduated')
    sub = svc.upload_requirement(ctx.student, ctx.thesis_doc.uuid, ctx.up.id, _pdf())
    listed = review_service.list_submissions_for_review(ctx.coordinator, phase='conclusion')
    assert [s.id for s in listed] == [sub.id]
    assert review_service.pending_counts_by_phase(ctx.coordinator)['conclusion'] == 1


def test_coordinator_uploads_institution_document_approved(ctx):
    _set_status(ctx.up, 'graduated')
    sub = svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.originality, _pdf())
    assert sub.status == 'approved' and sub.uploaded_by_role == 'coordinator'
    assert _by_key(svc.requirements(ctx.up))['conclusion_originality_letter']['status'] \
        == 'institution_done'
    with pytest.raises(DomainError, match='lo entrega el estudiante'):
        svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.thesis_doc, _pdf())


# ─── Exam and titling ────────────────────────────────────────────────────────

def test_exam_blockers_list_what_is_missing(ctx):
    svc.create_condition(ctx.coordinator, ctx.up.id, 'Curso propedéutico')
    blockers = svc.exam_blockers(ctx.up)
    assert 'El estudiante debe estar egresado.' in blockers
    assert 'Falta registrar la tesis.' in blockers
    assert any('Documento de Tesis Final' in b for b in blockers)
    assert any('Curso propedéutico' in b for b in blockers)
    assert any('sínodo' in b for b in blockers)


def test_schedule_requires_no_blockers(ctx):
    with pytest.raises(DomainError, match='No se puede agendar'):
        svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) + timedelta(days=7), 'Sala')


def test_full_flow_schedule_approve_and_revert(ctx):
    _ready_for_exam(ctx)
    assert svc.exam_blockers(ctx.up) == []
    assert svc.progress(ctx.up)['stage'] == 'ready'

    when = now_local().replace(tzinfo=None).replace(microsecond=0) - timedelta(days=1)
    exam = _schedule_past(ctx, when, 'Auditorio')
    assert svc.progress(ctx.up) == {'stage': 'exam_scheduled', 'label': 'Examen agendado',
                                    'percent': 90}
    with pytest.raises(ConflictError):
        svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) + timedelta(days=9),
                          'Otra sala')
    with pytest.raises(ConflictError, match='sínodo'):
        svc.add_member(ctx.coordinator, ctx.up.id, 'exam', 'substitute', external_name='S')

    with pytest.raises(DomainError, match='unanimidad'):
        svc.record_exam_result(ctx.coordinator, ctx.up.id, exam.uuid, 'approved',
                               acta_folio='A-1')
    svc.record_exam_result(ctx.coordinator, ctx.up.id, exam.uuid, 'approved', verdict='unanimous',
                           honorific_mention=True, acta_folio='A-1', held_on=when.date())
    db.session.refresh(ctx.up)
    assert ctx.up.academic_status == 'titled'
    assert ctx.up.titled_at == when.date()
    assert exam.status == 'approved' and exam.honorific_mention
    assert svc.progress(ctx.up)['percent'] == 100
    assert Notification.query.filter_by(user_id=ctx.student.id,
                                        type='grade_exam_result').count() == 1

    with pytest.raises(NotFoundError):
        svc.revert_titled(make_user('program_admin'), ctx.up.id, 'error')
    with pytest.raises(DomainError, match='motivo'):
        svc.revert_titled(ctx.postgrad, ctx.up.id, '  ')
    svc.revert_titled(ctx.postgrad, ctx.up.id, 'Acta capturada por error')
    db.session.refresh(ctx.up)
    assert ctx.up.academic_status == 'graduated' and ctx.up.titled_at is None


def test_suspended_exam_keeps_graduated_and_allows_rescheduling(ctx):
    _ready_for_exam(ctx)
    when = now_local().replace(tzinfo=None).replace(microsecond=0) - timedelta(days=2)
    exam = _schedule_past(ctx, when, 'Sala 1')
    svc.record_exam_result(ctx.coordinator, ctx.up.id, exam.uuid, 'suspended', verdict='unanimous',
                           honorific_mention=True)
    assert exam.status == 'suspended' and exam.verdict is None and not exam.honorific_mention
    assert ctx.up.academic_status == 'graduated'

    second = svc.schedule_exam(ctx.coordinator, ctx.up.id, when + timedelta(days=30), 'Sala 2')
    svc.cancel_exam(ctx.coordinator, ctx.up.id, second.uuid, 'Sinodal enfermo')
    assert second.status == 'cancelled'
    with pytest.raises(ConflictError):
        svc.record_exam_result(ctx.coordinator, ctx.up.id, second.uuid, 'approved',
                               verdict='majority',
                               acta_folio='B-2')
    assert [e.status for e in svc.exams(ctx.up)] == ['cancelled', 'suspended']


def test_exam_of_another_program_is_not_found(ctx):
    _ready_for_exam(ctx)
    exam = svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) + timedelta(days=1), 'Sala')
    outsider = make_user('program_admin')
    db.session.commit()
    with pytest.raises(NotFoundError, match=svc.EXAM_NOT_FOUND_MESSAGE):
        svc.cancel_exam(outsider, ctx.up.id, exam.uuid)
    with pytest.raises(NotFoundError, match=svc.EXAM_NOT_FOUND_MESSAGE):
        svc.cancel_exam(outsider, ctx.up.id, 'not-a-uuid')


def test_progress_stages_before_graduation(ctx):
    assert svc.progress(ctx.up)['stage'] == 'not_started'
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    assert svc.progress(ctx.up) == {'stage': 'thesis', 'label': 'Tesis registrada',
                                    'percent': 15}
    svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'director', external_name='Dr. X')
    assert svc.progress(ctx.up)['percent'] == 25
    _set_status(ctx.up, 'graduated')
    assert svc.progress(ctx.up)['stage'] == 'requirements'


# ─── Deliberation: conditional acceptance with conditions ────────────────────

def test_conditional_acceptance_creates_conditions(ctx, monkeypatch):
    applicant = make_user('applicant')
    up = enroll(applicant, ctx.program, 'deliberation')
    db.session.commit()
    monkeypatch.setattr('app.utils.files.save_user_doc',
                        lambda *a, **k: f'{applicant.id}/acceptance/dictamen.pdf')

    deliberation_service.accept_applicant(
        applicant.id, ctx.program.id, ctx.coordinator.id, 'Condicionado',
        is_conditional=True, dictamen_file=_pdf(),
        conditions=[
            {'description': 'Entregar título', 'archive_key': 'conclusion_previous_degree',
             'due_date': date(2027, 6, 30)},
            {'description': 'Cursar propedéutico', 'archive_key': None, 'due_date': None},
        ],
    )
    rows = AdmissionCondition.query.filter_by(user_program_id=up.id) \
        .order_by(AdmissionCondition.id).all()
    assert [(r.description, r.archive_id, r.status) for r in rows] == [
        ('Entregar título', ctx.prev_degree.id, 'pending'),
        ('Cursar propedéutico', None, 'pending'),
    ]
    assert rows[0].due_date == date(2027, 6, 30)


def test_conditional_acceptance_rejects_unknown_requirement(ctx, monkeypatch):
    applicant = make_user('applicant')
    up = enroll(applicant, ctx.program, 'deliberation')
    db.session.commit()
    monkeypatch.setattr('app.utils.files.save_user_doc', lambda *a, **k: 'x.pdf')

    with pytest.raises(DomainError, match='no existe'):
        deliberation_service.accept_applicant(
            applicant.id, ctx.program.id, ctx.coordinator.id, None,
            is_conditional=True, dictamen_file=_pdf(),
            conditions=[{'description': 'X', 'archive_key': 'admission_english_ms'}],
        )
    db.session.rollback()
    assert db.session.get(type(up), up.id).admission_status == 'deliberation'


def test_unconditional_acceptance_ignores_conditions(ctx):
    applicant = make_user('applicant')
    up = enroll(applicant, ctx.program, 'deliberation')
    db.session.commit()
    deliberation_service.accept_applicant(
        applicant.id, ctx.program.id, ctx.coordinator.id,
        conditions=[{'description': 'No aplica'}])
    assert AdmissionCondition.query.filter_by(user_program_id=up.id).count() == 0


def test_accept_schema_parses_conditions_from_multipart_json():
    from app.schemas.deliberation import AcceptApplicantIn

    body = AcceptApplicantIn.model_validate({
        'is_conditional': 'true',
        'conditions': '[{"description": " Título ", "archive_key": "", "due_date": "2027-01-31"}]',
    })
    assert body.conditions[0].description == 'Título'
    assert body.conditions[0].archive_key is None
    assert body.conditions[0].due_date == date(2027, 1, 31)
    assert AcceptApplicantIn.model_validate({}).conditions == []


# ─── Review fixes (phase 6C hardening) ───────────────────────────────────────

def _types(user_id):
    return [n.type for n in Notification.query.filter_by(user_id=user_id)]


def test_schedule_refuses_a_past_datetime(ctx):
    _ready_for_exam(ctx)
    with pytest.raises(DomainError, match='pasado'):
        svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) - timedelta(days=3), 'Sala')
    assert svc.current_exam(ctx.up) is None


def test_approved_result_rechecks_blockers(ctx):
    _ready_for_exam(ctx)
    exam = _schedule_past(ctx, now_local().replace(tzinfo=None).replace(microsecond=0) - timedelta(days=1))
    svc.create_condition(ctx.coordinator, ctx.up.id, 'Constancia pendiente')

    with pytest.raises(DomainError, match='No se puede titular') as err:
        svc.record_exam_result(ctx.coordinator, ctx.up.id, exam.uuid, 'approved',
                               verdict='unanimous', acta_folio='A-9')
    assert any('Constancia pendiente' in b for b in err.value.fields['blockers'])
    db.session.rollback()
    db.session.refresh(ctx.up)
    assert ctx.up.academic_status == 'graduated'


def test_held_on_is_neither_future_nor_before_the_scheduled_date(ctx):
    _ready_for_exam(ctx)
    when = now_local().replace(tzinfo=None).replace(microsecond=0) - timedelta(days=2)
    exam = _schedule_past(ctx, when)
    with pytest.raises(DomainError, match='anterior a la fecha agendada'):
        svc.record_exam_result(ctx.coordinator, ctx.up.id, exam.uuid, 'suspended',
                               held_on=when.date() - timedelta(days=1))
    with pytest.raises(DomainError, match='futura'):
        svc.record_exam_result(ctx.coordinator, ctx.up.id, exam.uuid, 'suspended',
                               held_on=now_local().date() + timedelta(days=5))


def test_condition_and_exam_are_bound_to_the_user_program(ctx):
    other_up = enroll(make_user('student'), ctx.program, 'enrolled')
    _set_status(other_up, 'active')
    db.session.commit()
    foreign = svc.create_condition(ctx.coordinator, other_up.id, 'Ajena')
    with pytest.raises(NotFoundError, match=svc.CONDITION_NOT_FOUND_MESSAGE):
        svc.resolve_condition(ctx.coordinator, ctx.up.id, foreign.uuid, 'met')
    assert foreign.status == 'pending'

    _ready_for_exam(ctx)
    exam = svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) + timedelta(days=1), 'Sala')
    with pytest.raises(NotFoundError, match=svc.EXAM_NOT_FOUND_MESSAGE):
        svc.cancel_exam(ctx.coordinator, other_up.id, exam.uuid)
    with pytest.raises(NotFoundError, match=svc.EXAM_NOT_FOUND_MESSAGE):
        svc.record_exam_result(ctx.coordinator, other_up.id, exam.uuid, 'suspended')
    assert exam.status == 'scheduled'


def test_upload_file_names_carry_the_user_program(ctx):
    _set_status(ctx.up, 'graduated')
    sub = svc.upload_requirement(ctx.student, ctx.thesis_doc.uuid, ctx.up.id, _pdf())
    assert sub.file_path == \
        f'{ctx.student.id}/conclusion/conclusion_thesis_document_up{ctx.up.id}.pdf'
    inst = svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.originality, _pdf())
    assert inst.file_path.endswith(f'conclusion_originality_letter_up{ctx.up.id}.pdf')


def _details(entry):
    raw = entry.details
    return json.loads(raw) if isinstance(raw, str) else raw


def test_institution_upload_needs_issued_archive_and_graduated_or_titled(ctx):
    with pytest.raises(DomainError, match='egresado o titulado'):
        svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.originality, _pdf())

    ctx.thesis_doc.allow_coordinator_upload = True  # still not issued by the institution
    _set_status(ctx.up, 'titled')
    db.session.commit()
    with pytest.raises(DomainError, match='lo entrega el estudiante'):
        svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.thesis_doc, _pdf())

    first = svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.originality, _pdf())
    old_path = first.file_path
    svc.upload_institution_document(ctx.coordinator, ctx.up, ctx.originality, _pdf('v2.pdf'))
    entries = (UserHistory.query.filter_by(user_id=ctx.student.id,
                                           action='institution_document_uploaded')
               .order_by(UserHistory.id).all())
    assert len(entries) == 2
    assert _details(entries[0])['replaced_file_path'] is None
    assert _details(entries[1])['replaced_file_path'] == old_path


def test_create_condition_refused_for_titled_or_withdrawn(ctx):
    for status in ('titled', 'withdrawn'):
        _set_status(ctx.up, status)
        db.session.commit()
        with pytest.raises(DomainError, match='No se pueden agregar condiciones'):
            svc.create_condition(ctx.coordinator, ctx.up.id, 'Tarde')
    assert AdmissionCondition.query.count() == 0


def test_student_is_notified_of_conclusion_changes(ctx):
    teacher = make_user('teacher')
    db.session.commit()
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    member = svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'director', user_id=teacher.id)
    svc.remove_member(ctx.coordinator, ctx.up.id, member.id)
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Curso')
    svc.resolve_condition(ctx.coordinator, ctx.up.id, cond.uuid, 'met')

    types = _types(ctx.student.id)
    for expected in ('thesis_registered', 'thesis_member_added', 'thesis_member_removed',
                     'admission_condition_created', 'admission_condition_resolved'):
        assert expected in types
    urls = {n.action_url for n in Notification.query.filter_by(user_id=ctx.student.id)}
    assert urls == {'/conclusion/'}


def test_cancel_uses_its_own_notification_type(ctx):
    _ready_for_exam(ctx)
    exam = svc.schedule_exam(ctx.coordinator, ctx.up.id, now_local().replace(tzinfo=None) + timedelta(days=4), 'Sala')
    svc.cancel_exam(ctx.coordinator, ctx.up.id, exam.uuid, 'Sinodal enfermo')
    types = _types(ctx.student.id)
    assert types.count('grade_exam_scheduled') == 1
    assert types.count('grade_exam_cancelled') == 1


def test_internal_member_must_be_a_teacher_choice(ctx):
    svc.register_thesis(ctx.coordinator, ctx.up.id, 'Tesis')
    classmate = make_user('student')
    applicant = make_user('applicant', is_internal=True)
    db.session.commit()
    for person in (classmate, applicant):
        with pytest.raises(DomainError, match='personal interno'):
            svc.add_member(ctx.coordinator, ctx.up.id, 'tutorial', 'advisor', user_id=person.id)
    assert svc.get_thesis(ctx.up).members == []


def test_own_conclusion_submission_beats_reuse(ctx):
    _submit(ctx.up, ctx.title_ms)                              # reusable admission title
    own = _submit(ctx.up, ctx.prev_degree, status='rejected')  # but the student uploaded one
    db.session.commit()
    item = _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']
    assert item['status'] == 'rejected' and item['reused_from'] is None
    assert item['submission'].id == own.id and not item['satisfied']

    own.status = 'pending'
    db.session.commit()
    assert _by_key(svc.requirements(ctx.up))['conclusion_previous_degree']['status'] == 'pending'


def test_review_approval_auto_resolves_the_linked_condition(ctx):
    from app.services import review_service

    other_up = enroll(make_user('student'), ctx.program, 'enrolled')
    _set_status(other_up, 'graduated')
    _set_status(ctx.up, 'graduated')
    db.session.commit()
    mine = svc.create_condition(ctx.coordinator, ctx.up.id, 'Entregar tesis final',
                                archive_uuid=ctx.thesis_doc.uuid)
    unrelated = svc.create_condition(ctx.coordinator, ctx.up.id, 'Otra cosa')
    theirs = svc.create_condition(ctx.coordinator, other_up.id, 'Entregar tesis final',
                                  archive_uuid=ctx.thesis_doc.uuid)

    sub = svc.upload_requirement(ctx.student, ctx.thesis_doc.uuid, ctx.up.id, _pdf())
    review_service.decide_submission(ctx.coordinator, sub.id, 'approve')

    db.session.expire_all()
    mine = db.session.get(AdmissionCondition, mine.id)
    assert mine.status == 'met'
    assert mine.resolved_by == ctx.coordinator.id
    assert mine.resolution_note == svc.AUTO_RESOLVE_NOTE
    assert db.session.get(AdmissionCondition, unrelated.id).status == 'pending'
    assert db.session.get(AdmissionCondition, theirs.id).status == 'pending'
    assert UserHistory.query.filter_by(user_id=ctx.student.id,
                                       action='admission_condition_resolved').count() == 1


def test_review_rejection_leaves_the_condition_pending(ctx):
    from app.services import review_service

    _set_status(ctx.up, 'graduated')
    db.session.commit()
    cond = svc.create_condition(ctx.coordinator, ctx.up.id, 'Entregar tesis final',
                                archive_uuid=ctx.thesis_doc.uuid)
    sub = svc.upload_requirement(ctx.student, ctx.thesis_doc.uuid, ctx.up.id, _pdf())
    review_service.decide_submission(ctx.coordinator, sub.id, 'reject', 'Falta firma')
    db.session.expire_all()
    assert db.session.get(AdmissionCondition, cond.id).status == 'pending'

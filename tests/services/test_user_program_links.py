"""New Submission / ExtensionRequest rows store the owning user_program_id."""

from datetime import timedelta
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app import db
from app.models.archive import Archive
from app.models.document_mapping import DocumentMapping
from app.models.extension_request import ExtensionRequest
from app.models.phase import Phase
from app.models.program_step import ProgramStep
from app.models.step import Step
from app.models.submission import Submission
from app.services import coordinator_service, submissions_service
from app.services.extensions_service import ExtensionsService
from app.services.program_changes_service import ProgramChangesService
from app.utils.datetime_utils import now_local
from tests.support.factories import enroll, make_program, make_user


def _structure(program, name='Doc'):
    phase = Phase.query.first() or Phase(name='admission', description='d')
    db.session.add(phase)
    db.session.flush()
    step = Step(name=f'Paso {name}', description='', phase_id=phase.id)
    db.session.add(step)
    db.session.flush()
    ps = ProgramStep(sequence=1, program_id=program.id, step_id=step.id)
    archive = Archive(name=name, description='', file_path=None, step_id=step.id)
    db.session.add_all([ps, archive])
    db.session.flush()
    return ps, archive


@pytest.fixture
def scene(app):
    coordinator = make_user('program_admin')
    program = make_program(coordinator)
    other = make_program(coordinator)
    applicant = make_user('applicant')
    enroll(applicant, other)  # decoy: first UP is NOT the target program
    up = enroll(applicant, program)
    ps, archive = _structure(program)
    db.session.commit()
    return dict(coordinator=coordinator, program=program, applicant=applicant,
                up=up, ps=ps, archive=archive)


def test_coordinator_upload_stores_user_program_id(scene):
    sub = coordinator_service.upload_for_student(
        student_id=scene['applicant'].id, user_program=scene['up'],
        archive=scene['archive'], file=None, decision='approve', notes='',
        uploader_id=scene['coordinator'].id)
    assert sub.user_program_id == scene['up'].id


def test_extension_request_stores_user_program_id(app):
    coordinator = make_user('program_admin')
    program = make_program(coordinator)
    applicant = make_user('applicant')
    up = enroll(applicant, program)
    _, archive = _structure(program)
    db.session.commit()
    er = ExtensionsService.create_request(
        applicant.id, archive.id, applicant.id, 'motivo',
        now_local() + timedelta(days=5))
    assert er.user_program_id == up.id


def test_program_change_copy_points_to_destination_up(app):
    coordinator = make_user('program_admin')
    origin = make_program(coordinator)
    dest = make_program(coordinator)
    applicant = make_user('applicant')
    up = enroll(applicant, origin)
    ps_o, arch_o = _structure(origin, 'Acta')
    ps_d, arch_d = _structure(dest, 'Acta')
    db.session.add(Submission(file_path='a.pdf', status='approved',
                              user_id=applicant.id, archive_id=arch_o.id,
                              program_step_id=ps_o.id, semester=None,
                              user_program_id=up.id))
    db.session.flush()
    # The UserProgram has already been moved to the destination program.
    up.program_id = dest.id
    db.session.add(DocumentMapping(from_program_id=origin.id, to_program_id=dest.id,
                                   from_archive_id=arch_o.id, to_archive_id=arch_d.id,
                                   mapping_rule='equivalent'))
    db.session.commit()
    from app.models.program_change_request import ProgramChangeRequest
    req = ProgramChangeRequest(applicant_id=applicant.id, from_program_id=origin.id,
                               to_program_id=dest.id)
    db.session.add(req)
    db.session.flush()
    ProgramChangesService._apply_change(req)
    db.session.commit()
    copy = Submission.query.filter_by(program_step_id=ps_d.id).one()
    assert copy.user_program_id == up.id


@pytest.fixture
def stub_save(monkeypatch):
    monkeypatch.setattr(submissions_service, 'save_user_doc',
                        lambda *a, **k: 'x/admission/doc.pdf')


def _file():
    return FileStorage(stream=BytesIO(b'%PDF'), filename='d.pdf')


def test_upload_submission_new_row_stores_user_program_id(scene, stub_save):
    sub, *_ = submissions_service.upload_submission(
        scene['applicant'], str(scene['archive'].uuid), scene['program'].id, None, _file())
    assert sub.user_program_id == scene['up'].id


def test_upload_submission_fills_null_on_existing_row(scene, stub_save):
    old = Submission(file_path='old.pdf', status='rejected',
                     user_id=scene['applicant'].id, archive_id=scene['archive'].id,
                     program_step_id=scene['ps'].id, semester=0)
    db.session.add(old)
    db.session.commit()
    assert old.user_program_id is None
    sub, *_ = submissions_service.upload_submission(
        scene['applicant'], str(scene['archive'].uuid), scene['program'].id, None, _file())
    assert sub.id == old.id
    assert sub.user_program_id == scene['up'].id

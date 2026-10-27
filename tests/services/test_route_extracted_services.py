"""Service functions extracted from routes in phase 4b (retention policies, submissions, tasks)."""

import pytest

from app import db
from app.models import Archive, Phase, Step
from app.models.retention_policy import RetentionPolicy
from app.models.task_log import TaskLog
from app.services import retention_service, submissions_service, task_log_service
from app.services.errors import NotFoundError
from tests.support.factories import make_user


@pytest.fixture
def archive(app):
    phase = Phase('admission', 'd')
    db.session.add(phase)
    db.session.flush()
    step = Step('Documentos', 'd', phase.id)
    db.session.add(step)
    db.session.flush()
    arch = Archive(name='CURP', description='d', file_path='x.pdf', step_id=step.id)
    db.session.add(arch)
    db.session.commit()
    return arch


class TestRetentionPolicies:
    def test_upsert_creates_then_updates(self, archive):
        pid, created = retention_service.upsert_policy(str(archive.uuid), False, 3, 'graduated')
        assert created is True
        pid2, created2 = retention_service.upsert_policy(str(archive.uuid), True, None, 'dropped')
        assert (pid2, created2) == (pid, False)
        row = db.session.get(RetentionPolicy, pid)
        assert row.keep_forever is True and row.keep_years is None and row.apply_after == 'dropped'

    def test_upsert_unknown_archive_is_not_found(self, app):
        with pytest.raises(NotFoundError, match='Archivo no existe'):
            retention_service.upsert_policy('00000000-0000-0000-0000-000000000000', False, 1, 'graduated')

    def test_list_serialises_archive_as_uuid(self, archive):
        retention_service.upsert_policy(str(archive.uuid), False, 2, 'enrollment')
        items = retention_service.list_policies()
        assert items[0]['archive_id'] == str(archive.uuid)
        assert items[0]['keep_years'] == 2

    def test_update_and_delete_missing_policy(self, app):
        with pytest.raises(NotFoundError, match='Política no encontrada'):
            retention_service.update_policy(9999, False, 1, 'graduated')
        with pytest.raises(NotFoundError, match='Política no encontrada'):
            retention_service.delete_policy(9999)

    def test_delete_policy(self, archive):
        pid, _ = retention_service.upsert_policy(str(archive.uuid), False, 1, 'graduated')
        assert retention_service.delete_policy(pid) == pid
        assert db.session.get(RetentionPolicy, pid) is None

    def test_purge_ignores_unknown_uuids(self, app):
        admin = make_user('postgraduate_admin')
        db.session.commit()
        assert retention_service.purge_with_history(
            ['00000000-0000-0000-0000-000000000000'], admin.id) == 0


class TestSubmissions:
    def test_delete_foreign_or_missing_answers_the_same(self, app):
        import uuid
        owner = make_user('applicant')
        db.session.commit()
        with pytest.raises(NotFoundError) as missing:
            submissions_service.delete_own_submission(owner.id, uuid.uuid4())
        assert str(missing.value) == submissions_service.SUBMISSION_NOT_FOUND_MESSAGE

    def test_upload_without_parameters_is_bad_request(self, app):
        user = make_user('applicant')
        db.session.commit()
        with pytest.raises(submissions_service.SubmissionError) as err:
            submissions_service.upload_submission(user, None, None, None, None)
        assert err.value.code == 'BAD_REQUEST' and err.value.status_code == 400


class TestTaskLog:
    def test_manual_task_is_logged_and_paginated(self, app):
        user = make_user('postgraduate_admin')
        db.session.commit()
        task_log_service.log_manual_task('abc', 'app.tasks.x', {'k': 1}, user.id)
        page = task_log_service.paginate_task_logs(1, 10, triggered_by='manual')
        assert [t.task_id for t in page.items] == ['abc']
        assert TaskLog.query.filter_by(task_id='abc').one().status == 'pending'

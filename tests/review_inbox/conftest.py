"""World shared by the review inbox tests (phase 6D, task 6).

Reuses the review engine `world` (programs, students, archives, `submit`)
and adds factories for the two other tables the inbox merges:
enrollment receipts (`AcceptanceDocument`) and extensions (`ExtensionRequest`).
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import db
from app.models import ExtensionRequest, ProgramStep
from app.models.acceptance_document import AcceptanceDocument
from app.utils.datetime_utils import now_local
from tests.review_engine.conftest import world  # noqa: F401  (fixture re-export)
from tests.support.factories import get_or_create_role, grant

#: Decision permissions of the wave-2 kinds (receipt, extension).
EXTRA_PERMS = ('acceptance.api.review_doc', 'extensions.api.decide')


def naive_now():
    return now_local().replace(tzinfo=None)


def ago(days, minutes=5):
    """A naive local datetime `days` whole days (and a few minutes) back."""
    return naive_now() - timedelta(days=days, minutes=minutes)


@pytest.fixture
def inbox(world):  # noqa: F811
    def grant_all():
        for role in ('program_admin', 'postgraduate_admin'):
            grant(get_or_create_role(role), *EXTRA_PERMS)
        db.session.commit()

    def submission(kind, owner=None, days=1, status=None, review_date=None):
        sub = world.submit(world.archives[kind], status=status, owner=owner)
        sub.upload_date = ago(days)
        sub.review_date = review_date
        db.session.commit()
        return sub

    def receipt(owner=None, days=1, status='uploaded', reviewed_at=None):
        owner = owner or world.up
        doc = AcceptanceDocument(user_program_id=owner.id, document_type='enrollment_receipt',
                                 file_path=f'{owner.user_id}/r.pdf', status=status,
                                 uploaded_by_id=owner.user_id, uploaded_at=ago(days))
        doc.reviewed_at = reviewed_at
        db.session.add(doc)
        db.session.commit()
        return doc

    def extension(owner=None, days=1, status='pending', decided_at=None):
        owner = owner or world.up
        archive = world.archives['admission_doc']
        ps = ProgramStep.query.filter_by(program_id=owner.program_id,
                                         step_id=archive.step_id).first()
        er = ExtensionRequest(user_id=owner.user_id, archive_id=archive.id,
                              program_step_id=ps.id, requested_by=owner.user_id,
                              reason='Título en trámite', requested_until=ago(-30),
                              user_program_id=owner.id)
        er.status = status
        er.created_at = ago(days)
        er.decided_at = decided_at
        db.session.add(er)
        db.session.commit()
        return er

    return SimpleNamespace(world=world, grant_all=grant_all, submission=submission,
                           receipt=receipt, extension=extension)

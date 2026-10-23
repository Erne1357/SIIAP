"""Phase 6C: a business error in the conditions of a conditional acceptance is a 400, not a 500."""

import io
import json

from app import db
from app.models.user_program import UserProgram
from tests.support.factories import enroll, grant, make_program, make_user


def test_unknown_condition_requirement_is_a_spanish_400(app, login):
    coordinator = make_user('program_admin')
    grant(coordinator.role, 'deliberation.api.decide')
    program = make_program(coordinator)
    applicant = make_user('applicant')
    up = enroll(applicant, program, 'deliberation')
    db.session.commit()

    res = login(coordinator).post(
        f'/api/v1/deliberation/user/{applicant.uuid}/program/{program.id}/accept',
        data={
            'is_conditional': 'true',
            'conditions': json.dumps([{'description': 'Entregar título',
                                       'archive_key': 'conclusion_no_existe'}]),
            'dictamen_file': (io.BytesIO(b'%PDF-1.4 dictamen'), 'dictamen.pdf'),
        },
        content_type='multipart/form-data',
    )
    assert res.status_code == 400
    body = res.get_json()
    assert body['error']['code'] == 'BUSINESS_ERROR'
    assert body['error']['message'] == 'El requisito de conclusión indicado no existe.'
    db.session.expire_all()
    assert db.session.get(UserProgram, up.id).admission_status == 'deliberation'

# tests/program_transfer/test_transfer_keeps_history.py
"""
Pins today's transfer behaviour (phase 6A): the transfer still overwrites
UserProgram.program_id, but leaves an `executed` ProgramChangeRequest and a
UserHistory row naming origin and destination.
"""

from app import db
from app.models.program_change_request import ProgramChangeRequest, EXECUTED
from app.models.user_history import UserHistory
from app.models.user_program import UserProgram


def _login(client, user, password='Test1234!'):
    resp = client.post('/api/v1/auth/login',
                       json={'username': user.username, 'password': password})
    try:
        return resp.get_json().get('data', {}).get('csrf_token', '')
    except Exception:
        return ''


def test_transfer_overwrites_program_and_keeps_audit_trail(
        app, client, applicant, from_program, to_program, enrollment,
        structure, open_period):
    up_id = enrollment.id
    token = _login(client, applicant)
    resp = client.post(
        '/api/v1/program-changes/execute',
        json={'from_program_id': from_program.id, 'to_program_id': to_program.id},
        headers={'X-CSRFToken': token},
    )
    assert resp.status_code == 200

    up = db.session.get(UserProgram, up_id)
    assert up.program_id == to_program.id

    req = ProgramChangeRequest.query.one()
    assert req.status == EXECUTED
    assert req.from_program_id == from_program.id
    assert req.to_program_id == to_program.id

    rows = UserHistory.query.filter_by(user_id=applicant.id).all()
    blob = ' '.join(f'{r.action} {r.details}' for r in rows)
    assert from_program.name in blob
    assert to_program.name in blob

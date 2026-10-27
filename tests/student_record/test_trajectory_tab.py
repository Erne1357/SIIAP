"""Phase 6A: the record's "Trayectoria" tab (fragment routes + withdrawal guard)."""

import json
from datetime import date

import pytest
from flask import g

from app import db
from app.models.user_program import UserProgram
from tests.permanence.conftest import make_enrollment, make_period, make_user_program
from tests.support.factories import grant, make_program, make_user

HX = {'HX-Request': 'true'}
VIEW = ('students.page.view_record', 'students.api.view_record')


def _set_status(up, status):
    UserProgram.query.filter_by(id=up.id).update({'academic_status': status})
    db.session.expire(up)


@pytest.fixture
def world(app):
    coord = make_user('program_admin')
    other = make_user('program_admin')
    program = make_program(coord, duration_semesters=4)
    make_program(other)
    student = make_user('student')
    period = make_period('20241', date(2024, 1, 15))
    up = make_user_program(student, program, period)
    _set_status(up, 'active')
    make_enrollment(up, period, 1, status='completed')
    grant(coord.role, *VIEW, 'permanence.api.withdraw', 'permanence.api.register_graduation')
    grant(other.role, *VIEW)
    return {'coord': coord, 'other': other, 'student': student, 'up': up, 'program': program}


def _base(w):
    return f"/students/{w['student'].uuid}/record/trajectory"


def _status(w):
    db.session.expire_all()
    return db.session.get(UserProgram, w['up'].id).academic_status


def _flash(res):
    return json.loads(res.headers['HX-Trigger'])['siiap:flash']['message']


def test_get_fragment_for_coordinator(world, login):
    res = login(world['coord']).get(_base(world), headers=HX)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Estado académico' in html
    assert 'Semestre 1 de 4' in html
    assert 'trajectoryWithdrawForm' in html


def test_non_htmx_get_redirects_to_record_tab(world, login):
    res = login(world['coord']).get(_base(world))
    assert res.status_code == 302
    assert res.headers['Location'].endswith(f"/students/{world['student'].uuid}/record?tab=trayectoria")


def test_other_program_coordinator_gets_404(world, login):
    assert login(world['other']).get(_base(world), headers=HX).status_code == 404


def test_unknown_program_param_is_404(world, login):
    assert login(world['coord']).get(_base(world) + '?program=99999', headers=HX).status_code == 404


def test_without_permission_is_403(world, login):
    nobody = make_user('student')
    assert login(nobody).get(_base(world), headers=HX).status_code == 403


def test_withdraw_form_hidden_without_permission(world, login):
    db.session.commit()
    from app.models.role_permission import RolePermission
    from app.models.permission import Permission
    perm = Permission.query.filter_by(codename='permanence.api.withdraw').one()
    RolePermission.query.filter_by(role_id=world['coord'].role_id, permission_id=perm.id).delete()
    html = login(world['coord']).get(_base(world), headers=HX).get_data(as_text=True)
    assert 'trajectoryWithdrawForm' not in html
    assert 'trajectoryGraduateForm' in html


def test_withdraw_without_reason_keeps_status(world, login):
    res = login(world['coord']).post(_base(world) + '/withdraw', headers=HX,
                                     data={'reason': '  ', 'program': world['program'].id})
    assert res.status_code >= 400
    assert _flash(res) == 'El motivo es obligatorio.'
    assert _status(world) == 'active'


def test_withdraw_ok(world, login):
    res = login(world['coord']).post(_base(world) + '/withdraw', headers=HX,
                                     data={'reason': 'Abandono', 'program': world['program'].id})
    assert res.status_code == 200
    assert _status(world) == 'withdrawn'
    html = res.get_data(as_text=True)
    assert 'Abandono' in html
    assert 'trajectoryWithdrawForm' not in html


def test_graduate_ok(world, login):
    res = login(world['coord']).post(_base(world) + '/graduate', headers=HX,
                                     data={'graduated_at': '2026-07-31'})
    assert res.status_code == 200
    assert _status(world) == 'graduated'
    assert '31 de julio de 2026' in res.get_data(as_text=True)


def test_graduate_requires_date(world, login):
    res = login(world['coord']).post(_base(world) + '/graduate', headers=HX, data={})
    assert res.status_code >= 400
    assert _status(world) == 'active'


def test_graduate_invalid_date(world, login):
    res = login(world['coord']).post(_base(world) + '/graduate', headers=HX,
                                     data={'graduated_at': 'nope'})
    assert res.status_code == 400
    assert _status(world) == 'active'


def test_out_of_scope_cannot_withdraw(world, login):
    grant(world['other'].role, 'permanence.api.withdraw')
    res = login(world['other']).post(_base(world) + '/withdraw', headers=HX, data={'reason': 'x'})
    assert res.status_code == 404
    assert _status(world) == 'active'


def test_revert_needs_its_permission(world, login):
    login(world['coord']).post(_base(world) + '/withdraw', headers=HX, data={'reason': 'Error'})
    assert _status(world) == 'withdrawn'
    res = login(world['coord']).post(_base(world) + '/revert-withdrawal', headers=HX,
                                     data={'reason': 'Capturada por error'})
    assert res.status_code == 403
    assert _status(world) == 'withdrawn'

    grant(world['coord'].role, 'permanence.api.revert_withdrawal')
    for key in ('_role_perm_cache_', '_perm_cache_'):  # per-context permission caches
        g.pop(f"{key}{world['coord'].id}", None)
    res = login(world['coord']).post(_base(world) + '/revert-withdrawal', headers=HX,
                                     data={'reason': 'Capturada por error'})
    assert res.status_code == 200
    assert _status(world) == 'active'


def test_patch_dropped_requires_withdraw_permission(world, login):
    se = make_enrollment(world['up'], make_period('20243', date(2024, 8, 15)), 2, status='active')
    db.session.commit()
    from app.models.role_permission import RolePermission
    from app.models.permission import Permission
    grant(world['coord'].role, 'permanence.api.confirm_enrollment')
    perm = Permission.query.filter_by(codename='permanence.api.withdraw').one()
    RolePermission.query.filter_by(role_id=world['coord'].role_id, permission_id=perm.id).delete()
    res = login(world['coord']).patch(f'/api/v1/permanence/semester-enrollment/{se.id}/status',
                                      json={'status': 'dropped'})
    assert res.status_code == 403

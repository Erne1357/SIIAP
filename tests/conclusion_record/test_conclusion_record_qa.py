# ruff: noqa: F811  (pytest fixtures imported from the sibling module)
"""
Phase 6C QA follow-up on the coordinator's Conclusión tab:
- bug 3: no mutation form is offered where the service would refuse it;
- decision 6: «No aplica» from the requirements table (route + HTML).
"""
from datetime import timedelta

from app import db
from app.models.conclusion_requirement_override import ConclusionRequirementOverride
from app.services import conclusion_service as svc
from app.utils.datetime_utils import now_local
from tests.conclusion_record.test_conclusion_record_pages import (  # noqa: F401  (fixture)
    HX, _base, _ready, _status, world,
)

MUTATION_MARKERS = ('conclusionThesisForm', 'conclusionMemberForm-tutorial',
                    'conclusionMemberForm-exam', 'conclusionConditionForm', '/remove"',
                    '/resolve"', 'notApplicable-', '/upload"')


def _html(world, login):
    res = login(world.coord).get(_base(world), headers=HX)
    assert res.status_code == 200
    return res.get_data(as_text=True)


def _with_member_and_condition(world):
    svc.register_thesis(world.coord, world.up.id, 'Tesis')
    svc.add_member(world.coord, world.up.id, 'tutorial', 'director', external_name='Dr. X')
    svc.create_condition(world.coord, world.up.id, 'Curso propedéutico')


def test_titled_file_is_read_only(world, login):
    _with_member_and_condition(world)
    _status(world.up, 'titled')
    db.session.commit()
    html = _html(world, login)
    for marker in MUTATION_MARKERS:
        if marker == '/upload"':
            continue  # institution documents are still issued for a titled student
        assert marker not in html, marker
    assert 'Tesis' in html and 'Dr. X' in html and 'Curso propedéutico' in html


def test_withdrawn_file_is_read_only(world, login):
    _with_member_and_condition(world)
    _status(world.up, 'withdrawn')
    db.session.commit()
    html = _html(world, login)
    for marker in MUTATION_MARKERS:
        assert marker not in html, marker


def test_board_edits_hidden_while_exam_is_scheduled(world, login):
    _ready(world)
    svc.schedule_exam(world.coord, world.up.id,
                      now_local().replace(tzinfo=None) + timedelta(days=3), 'Sala')
    html = _html(world, login)
    assert 'conclusionMemberForm-exam' not in html
    assert 'conclusionMemberForm-tutorial' in html
    assert 'El sínodo no se modifica mientras haya un examen agendado.' in html


def test_institution_upload_hidden_before_graduation(world, login):
    html = _html(world, login)
    assert f'/requirements/{world.cert.uuid}/upload' not in html
    _status(world.up, 'graduated')
    db.session.commit()
    assert f'/requirements/{world.cert.uuid}/upload' in _html(world, login)


def test_not_applicable_route_marks_and_undoes(world, login):
    c = login(world.coord)
    html = _html(world, login)
    assert f'notApplicable-{world.doc.uuid}' in html
    assert 'hx-confirm' in html

    res = c.post(_base(world) + f'/requirements/{world.doc.uuid}/override', headers=HX,
                 data={'kind': 'not_applicable', 'reason': '<b>Exento</b>'})
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert 'No aplica' in body
    assert '&lt;b&gt;Exento&lt;/b&gt;' in body and '<b>Exento</b>' not in body
    assert 'siiap:flash' in res.headers.get('HX-Trigger', '')
    assert ConclusionRequirementOverride.query.count() == 1

    res = c.post(_base(world) + f'/requirements/{world.doc.uuid}/override', headers=HX,
                 data={'kind': 'not_applicable', 'reason': 'otra'})
    assert res.status_code == 409

    res = c.post(_base(world) + f'/requirements/{world.doc.uuid}/override/remove', headers=HX,
                 data={'kind': 'not_applicable'})
    assert res.status_code == 200
    assert ConclusionRequirementOverride.query.count() == 0


def test_not_applicable_out_of_scope_is_404(world, login):
    res = login(world.other).post(_base(world) + f'/requirements/{world.doc.uuid}/override',
                                  headers=HX, data={'kind': 'not_applicable', 'reason': 'x'})
    assert res.status_code == 404
    assert ConclusionRequirementOverride.query.count() == 0


def test_not_applicable_needs_reason(world, login):
    res = login(world.coord).post(_base(world) + f'/requirements/{world.doc.uuid}/override',
                                  headers=HX, data={'kind': 'not_applicable', 'reason': ' '})
    assert res.status_code == 400
    assert ConclusionRequirementOverride.query.count() == 0

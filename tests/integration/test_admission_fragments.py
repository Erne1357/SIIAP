"""Admission screen: upload / replace / delete as htmx fragments (plan phase 02).

Same service and validation as POST/DELETE /api/v1/submissions, but the answer
is the pane that changed (HX-Retarget + morph) plus the tabs and the stepper out
of band, and the flash travels in HX-Trigger.
"""

import io
import json
import re

import pytest

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission, UserProgram
from tests.integration.auth_support import fake_redis, grant_codename, isolate_globals  # noqa: F401
from tests.support.factories import enroll, make_program, make_user

HX = {'HX-Request': 'true'}


def _pdf(name='doc.pdf'):
    return (io.BytesIO(b'%PDF-1.4 test'), name)


def _flash(resp):
    return json.loads(resp.headers['HX-Trigger'])['siiap:flash']


@pytest.fixture
def env(app):
    """Two programs with steps 1, 2, 3 and 4 (last: locked until 1-3 are approved)."""
    grant_codename('applicant', 'submissions.api.upload', 'submissions.api.create',
                   'submissions.api.delete_own')
    program = make_program()
    other = make_program()
    phase = Phase('admission', 'd')
    db.session.add(phase)
    db.session.flush()
    steps, archives = {}, {}
    for prog in (program, other):
        for seq in (1, 2, 3, 4):
            st = Step(f'Paso {seq}', 'd', phase.id)
            db.session.add(st)
            db.session.flush()
            ps = ProgramStep(program_id=prog.id, step_id=st.id, sequence=seq)
            db.session.add(ps)
            db.session.flush()
            ar = Archive(f'Doc {seq}', 'd', None, st.id)
            db.session.add(ar)
            db.session.flush()
            steps[(prog.id, seq)], archives[(prog.id, seq)] = ps, ar
    user = make_user('applicant')
    enroll(user, program)
    other_user = make_user('applicant')
    enroll(other_user, program)
    db.session.commit()
    return type('E', (), dict(program=program, other=other, steps=steps, archives=archives,
                              user=user, other_user=other_user))


def _sub(env, user, seq, status='approved', program=None):
    program = program or env.program
    s = Submission('f.pdf', status, user.id, env.archives[(program.id, seq)].id,
                   env.steps[(program.id, seq)].id, None)
    s.uploaded_by = user.id
    db.session.add(s)
    db.session.commit()
    return s


def _upload(client, env, seq, *, program=None, slug=None, locked='', filename='doc.pdf'):
    program = program or env.program
    return client.post(
        f'/programs/admission/{slug or program.slug}/submissions',
        data={'archive_id': str(env.archives[(program.id, seq)].uuid), 'locked': locked,
              'file': _pdf(filename)},
        content_type='multipart/form-data', headers=HX)


def _count(user):
    return Submission.query.filter_by(user_id=user.id).count()


def _step_id(env, seq):
    return env.steps[(env.program.id, seq)].step_id


def _combined_key(env):
    return f"combined-{_step_id(env, 2)}-{_step_id(env, 3)}"


class TestPage:
    def test_full_page_still_renders_without_htmx(self, env, login):
        resp = login(env.user).get(f'/programs/admission/{env.program.slug}')
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        for marker in ('id="admission-body"', 'id="admission-stepper"', 'id="admission-refresh"',
                       'id="stepTabContent"', 'id="uploadForm"', 'hx-history="false"',
                       'hx-ext="morph"'):
            assert marker in html
        step1 = _step_id(env, 1)
        assert f'id="pane-{step1}"' in html and f'id="tab-item-{step1}"' in html
        assert f'id="upload-btn-d-{env.archives[(env.program.id, 1)].uuid}"' in html
        # the tab strip is not an out-of-band payload on a normal page load
        assert 'hx-swap-oob' not in html

    def test_unenrolled_user_is_redirected(self, env, login):
        resp = login(make_user('applicant')).get(f'/programs/admission/{env.program.slug}')
        assert resp.status_code == 302


class TestUpload:
    def test_returns_pane_oob_tabs_stepper_and_flash(self, env, login):
        resp = _upload(login(env.user), env, 1)
        assert resp.status_code == 200
        step = _step_id(env, 1)
        assert resp.headers['HX-Retarget'] == f'#pane-{step}'
        assert resp.headers['HX-Reswap'] == 'morph:outerHTML'
        assert 'HX-Request' in resp.headers['Vary']
        assert _flash(resp) == {'level': 'success', 'message': 'Documento enviado exitosamente.'}

        html = resp.get_data(as_text=True)
        # main swap: the pane, active, not out of band
        assert f'<div class="tab-pane fade show active" id="pane-{step}"' in html
        # every tab <li> out of band, only the touched one active
        for seq in (1, 4):
            assert f'id="tab-item-{_step_id(env, seq)}" hx-swap-oob="morph"' in html
        assert f'id="tab-item-{_combined_key(env)}" hx-swap-oob="morph"' in html
        assert 'id="admission-stepper" hx-swap-oob="morph"' in html
        assert html.count('aria-selected="true"') == 1
        assert f'id="arow-{env.archives[(env.program.id, 1)].uuid}"' in html
        assert Submission.query.filter_by(user_id=env.user.id).one().status == 'pending'

    def test_replace_keeps_one_submission(self, env, login):
        c = login(env.user)
        _upload(c, env, 1)
        resp = _upload(c, env, 1)
        assert resp.status_code == 200 and _count(env.user) == 1

    def test_combined_step_pane_is_the_target(self, env, login):
        resp = _upload(login(env.user), env, 2)
        key = _combined_key(env)
        assert resp.headers['HX-Retarget'] == f'#pane-{key}'
        assert f'id="pane-{key}"' in resp.get_data(as_text=True)

    def test_locked_step_is_refused_and_changes_nothing(self, env, login):
        resp = _upload(login(env.user), env, 4)
        assert resp.status_code == 409
        assert resp.headers['HX-Reswap'] == 'none'
        assert resp.get_data() == b'' and _flash(resp)['level'] == 'danger'
        assert _count(env.user) == 0

    def test_archive_of_another_program_is_refused(self, env, login):
        # the archive belongs to `other`, the URL names `program`
        resp = login(env.user).post(
            f'/programs/admission/{env.program.slug}/submissions',
            data={'archive_id': str(env.archives[(env.other.id, 1)].uuid), 'file': _pdf()},
            content_type='multipart/form-data', headers=HX)
        assert resp.status_code == 409 and resp.headers['HX-Reswap'] == 'none'
        assert _count(env.user) == 0

    def test_not_enrolled_is_refused(self, env, login):
        stranger = make_user('applicant')
        resp = _upload(login(stranger), env, 1)
        assert resp.status_code == 403 and resp.headers['HX-Reswap'] == 'none'
        assert _count(stranger) == 0

    def test_unknown_program_slug_is_404(self, env, login):
        resp = _upload(login(env.user), env, 1, slug='no-existe')
        assert resp.status_code == 404 and resp.headers['HX-Reswap'] == 'none'

    def test_disallowed_extension_is_refused(self, env, login):
        resp = _upload(login(env.user), env, 1, filename='virus.exe')
        assert resp.status_code == 400 and resp.headers['HX-Reswap'] == 'none'
        assert _count(env.user) == 0

    def test_missing_file_is_refused(self, env, login):
        resp = login(env.user).post(
            f'/programs/admission/{env.program.slug}/submissions',
            data={'archive_id': str(env.archives[(env.program.id, 1)].uuid)},
            content_type='multipart/form-data', headers=HX)
        assert resp.status_code == 400 and resp.headers['HX-Reswap'] == 'none'

    def test_without_permission_is_403(self, env, login):
        nobody = make_user('student')
        enroll(nobody, env.program)
        resp = _upload(login(nobody), env, 1)
        assert resp.status_code == 403 and resp.headers['HX-Reswap'] == 'none'

    def test_only_panes_whose_lock_changed_travel_out_of_band(self, env, login):
        for seq in (1, 2, 3):
            _sub(env, env.user, seq)
        last = _step_id(env, 4)
        c = login(env.user)
        # step 4 is unlocked now; replacing doc 1 locks it again
        html = _upload(c, env, 1, locked='').get_data(as_text=True)
        assert re.search(rf'id="pane-{last}"[^>]*hx-swap-oob="morph"', html)
        assert 'Completa y aprueba el paso anterior.' in html
        # the browser already shows it locked: no pane for it
        html = _upload(c, env, 1, locked=f'pane-{last}').get_data(as_text=True)
        assert f'id="pane-{last}"' not in html

    def test_json_api_still_works(self, env, login):
        resp = login(env.user).post(
            '/api/v1/submissions',
            data={'archive_id': str(env.archives[(env.program.id, 1)].uuid),
                  'program_slug': env.program.slug, 'file': _pdf()},
            content_type='multipart/form-data')
        assert resp.status_code == 201
        assert resp.get_json()['data']['submission']['status'] == 'pending'

    def test_plain_post_redirects_back(self, env, login):
        resp = login(env.user).post(
            f'/programs/admission/{env.program.slug}/submissions',
            data={'archive_id': str(env.archives[(env.program.id, 1)].uuid), 'file': _pdf()},
            content_type='multipart/form-data')
        assert resp.status_code == 302 and _count(env.user) == 1


class TestOobConsistency:
    """htmx logs htmx:oobErrorNoTarget when an out-of-band id is not in the page."""

    @staticmethod
    def _oob(html):
        return re.findall(r'<(?:li|div)\b[^>]*?\bid="([^"]+)"[^>]*?hx-swap-oob="([^"]*)"', html, re.S)

    def _check(self, env, login, locked):
        c = login(env.user)
        page_ids = set(re.findall(r'\bid="([^"]+)"',
                                  c.get(f'/programs/admission/{env.program.slug}').get_data(as_text=True)))
        html = _upload(c, env, 1, locked=locked).get_data(as_text=True)
        oob = self._oob(html)
        assert oob, 'the response carries no out-of-band elements'
        for id_, value in oob:
            assert id_ in page_ids, f'hx-swap-oob target #{id_} is not in the page'
            # "style:selector" is htmx syntax: a colon would turn the style into a selector
            assert value == 'morph', value
        assert html.count('hx-swap-oob') == len(oob)

    def test_every_oob_id_exists_in_the_page(self, env, login):
        self._check(env, login, '')

    def test_including_a_lock_changed_pane(self, env, login):
        for seq in (1, 2, 3):
            _sub(env, env.user, seq)
        self._check(env, login, '')


class TestDelete:
    def test_deletes_and_returns_the_pane(self, env, login):
        sub = _sub(env, env.user, 1, 'pending')
        resp = login(env.user).delete(
            f'/programs/admission/{env.program.slug}/submissions/{sub.uuid}', headers=HX)
        assert resp.status_code == 200
        assert resp.headers['HX-Retarget'] == f'#pane-{_step_id(env, 1)}'
        assert resp.headers['HX-Reswap'] == 'morph:outerHTML'
        assert _flash(resp)['message'] == 'Archivo eliminado.'
        assert _count(env.user) == 0
        html = resp.get_data(as_text=True)
        assert 'id="admission-stepper" hx-swap-oob' in html
        assert f'id="delete-btn-d-{env.archives[(env.program.id, 1)].uuid}"' not in html

    def test_delete_button_carries_confirm_and_focus_fallback(self, env, login):
        sub = _sub(env, env.user, 1, 'pending')
        html = login(env.user).get(f'/programs/admission/{env.program.slug}').get_data(as_text=True)
        arch = env.archives[(env.program.id, 1)].uuid
        assert f'hx-delete="/programs/admission/{env.program.slug}/submissions/{sub.uuid}"' in html
        assert 'hx-confirm="¿Eliminar este archivo?"' in html
        assert f'data-focus-fallback="upload-btn-d-{arch}"' in html

    def test_other_users_submission_is_404_and_untouched(self, env, login):
        theirs = _sub(env, env.other_user, 1, 'pending')
        resp = login(env.user).delete(
            f'/programs/admission/{env.program.slug}/submissions/{theirs.uuid}', headers=HX)
        assert resp.status_code == 404 and resp.headers['HX-Reswap'] == 'none'
        assert _count(env.other_user) == 1

    def test_submission_of_another_program_is_404_and_untouched(self, env, login):
        enroll(env.user, env.other)
        db.session.commit()
        mine = _sub(env, env.user, 1, 'pending', program=env.other)
        resp = login(env.user).delete(
            f'/programs/admission/{env.program.slug}/submissions/{mine.uuid}', headers=HX)
        assert resp.status_code == 404 and resp.headers['HX-Reswap'] == 'none'
        assert _count(env.user) == 1

    def test_same_message_for_missing_and_foreign(self, env, login):
        theirs = _sub(env, env.other_user, 1, 'pending')
        c = login(env.user)
        base = f'/programs/admission/{env.program.slug}/submissions/'
        foreign = c.delete(base + str(theirs.uuid), headers=HX)
        missing = c.delete(base + '00000000-0000-4000-8000-000000000000', headers=HX)
        assert _flash(foreign) == _flash(missing)


class TestRefresh:
    def test_panel_returns_body_and_stepper_oob(self, env, login):
        key = _combined_key(env)
        resp = login(env.user).get(
            f'/programs/admission/{env.program.slug}/panel?active=pane-{key}', headers=HX)
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200 and 'HX-Request' in resp.headers['Vary']
        assert 'id="stepTab"' in html and 'id="stepTabContent"' in html
        assert 'id="admission-stepper" hx-swap-oob="morph"' in html
        assert 'id="admission-body"' not in html
        # the tab the browser had open stays the active one
        assert html.count('aria-selected="true"') == 1
        at = html.index(f'id="tab-{key}"')
        assert 'nav-link active' in html[at - 60:at]
        assert 'aria-selected="true"' in html[at:at + 300]

    def test_banner_status_replaces_the_tabs(self, env, login):
        up = UserProgram.query.filter_by(user_id=env.user.id, program_id=env.program.id).one()
        up.admission_status = 'deliberation'
        db.session.commit()
        html = login(env.user).get(
            f'/programs/admission/{env.program.slug}/panel', headers=HX).get_data(as_text=True)
        assert 'Tu expediente está en deliberación' in html and 'id="stepTab"' not in html

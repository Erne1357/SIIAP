"""Invariants of the GitHub Actions workflows (CI gates the deploy)."""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.infra

WORKFLOWS = Path(__file__).resolve().parents[2] / '.github' / 'workflows'


def _load(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding='utf-8'))
    # PyYAML reads the bare key `on` as boolean True.
    data['on'] = data.pop(True, data.get('on'))
    return data


@pytest.fixture(scope='module')
def tests_wf():
    return _load('_tests.yml')


@pytest.fixture(scope='module')
def deploy_wf():
    return _load('deploy.yml')


def test_reusable_suite_has_single_stable_result_check(tests_wf):
    result = tests_wf['jobs']['result']
    assert result['name'] == 'Resultado'
    assert result['if'] == 'always()'
    other_jobs = set(tests_wf['jobs']) - {'result'}
    assert set(result['needs']) == other_jobs


def test_full_lane_runs_postgres_and_e2e(tests_wf):
    for job in ('postgres', 'e2e'):
        assert tests_wf['jobs'][job]['if'] == "inputs.lane == 'full'"


def test_postgres_job_uses_production_major_version(tests_wf):
    image = tests_wf['jobs']['postgres']['services']['postgres']['image']
    db_dockerfile = (WORKFLOWS.parents[1] / 'docker' / 'Dockerfile.db').read_text()
    assert image.split(':')[1].split('-')[0] == '18'
    assert 'FROM postgres:18' in db_dockerfile


def test_ci_runs_on_pull_requests_to_main():
    ci = _load('ci.yml')
    assert ci['on']['pull_request']['branches'] == ['main']
    assert ci['jobs']['tests']['uses'] == './.github/workflows/_tests.yml'


def test_deploy_requires_green_tests_and_tip_of_main(deploy_wf):
    jobs = deploy_wf['jobs']
    assert set(jobs['gate']['needs']) >= {'tests', 'smoke'}
    assert "needs.tests.result == 'success'" in jobs['gate']['if']
    assert "needs.smoke.result == 'success'" in jobs['gate']['if']
    assert 'gate' in jobs['deploy']['needs']
    assert "needs.gate.outputs.superseded == 'false'" in jobs['deploy']['if']


def test_deploy_is_serialized_and_never_cancelled(deploy_wf):
    concurrency = deploy_wf['jobs']['deploy']['concurrency']
    assert concurrency['cancel-in-progress'] is False


def test_deploy_runs_the_script_of_the_deployed_commit(deploy_wf):
    script = deploy_wf['jobs']['deploy']['steps'][0]['with']['script']
    assert 'git show "${{ github.sha }}:docker/scripts/deploy.sh"' in script
    assert 'bash .deploy/deploy-run.sh "${{ github.sha }}"' in script
    assert 'mktemp' not in script and '/tmp' not in script
    assert 'docker compose' not in script, 'el workflow no debe orquestar contenedores; eso es deploy.sh'


def test_hotfix_lane_verifies_after_deploy(deploy_wf):
    jobs = deploy_wf['jobs']
    assert jobs['smoke']['with']['lane'] == 'smoke'
    assert 'deploy' in jobs['verify']['needs']
    assert jobs['verify']['with']['lane'] == 'full'
    assert 'verify' in jobs['verify-alert']['needs']


def test_workflows_have_least_privilege_tokens():
    for path in WORKFLOWS.glob('*.yml'):
        data = _load(path.name)
        assert data.get('permissions') == {'contents': 'read'}, path.name

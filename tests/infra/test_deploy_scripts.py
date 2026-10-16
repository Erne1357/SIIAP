"""
Contract tests for the blue-green deploy scripts (docker/scripts/*.sh).

They run the real bash functions against throwaway git repositories and
directories — no Docker, no server.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.infra

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'docker' / 'scripts'
DEPLOY = SCRIPTS / 'deploy.sh'
COMMON = SCRIPTS / '_common.sh'

needs_bash = pytest.mark.skipif(shutil.which('bash') is None, reason='bash no disponible')
needs_git = pytest.mark.skipif(shutil.which('git') is None, reason='git no disponible')


def _bash(script: str, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(['bash', '-c', script], cwd=cwd, capture_output=True, text=True,
                          env={'PATH': '/usr/bin:/bin:/usr/local/bin', 'HOME': str(cwd), **(env_extra or {})})


@needs_bash
@pytest.mark.parametrize('script', sorted(SCRIPTS.glob('*.sh')), ids=lambda p: p.name)
def test_scripts_parse(script):
    result = subprocess.run(['bash', '-n', str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('name', ['deploy.sh', 'rollback.sh'])
def test_scripts_are_strict(name):
    text = (SCRIPTS / name).read_text(encoding='utf-8')
    assert 'set -Eeuo pipefail' in text


def test_scripts_never_write_outside_project_dir():
    """The deploy user may only touch /home/cuaderno/SIIAP on the shared host."""
    for path in SCRIPTS.glob('*.sh'):
        text = path.read_text(encoding='utf-8')
        assert 'mktemp' not in text, f'{path.name}: mktemp escribe en /tmp'
        assert not re.search(r'(?<![\w$])/tmp/', text), f'{path.name}: escribe en /tmp'
        assert '/home/cuaderno/backups' not in text, f'{path.name}: respaldos fuera del proyecto'
        # Host-wide pruning would delete images of the co-hosted ITCJ stack.
        assert not re.search(r'docker (image|system) prune', text), f'{path.name}: prune global'


def test_deploy_takes_lock_before_touching_checkout():
    text = DEPLOY.read_text(encoding='utf-8')
    lock = re.search(r'^flock -n 9', text, re.M).start()
    reset = re.search(r'^git reset --hard', text, re.M).start()
    assert lock < reset


def test_deploy_backs_up_before_migrating_and_migrates_before_switching():
    text = DEPLOY.read_text(encoding='utf-8')
    order = ['pg_dump', 'flask db upgrade', 'wait_healthy "$NEW"', 'write_upstream "$NEW"',
             'nginx_apply', 'write_state active-color', 'restart_workers', 'retire_color "$ACTIVE"']
    positions = [text.index(marker) for marker in order]
    assert positions == sorted(positions), dict(zip(order, positions))


def test_deploy_never_restarts_nginx():
    for path in SCRIPTS.glob('*.sh'):
        text = path.read_text(encoding='utf-8')
        assert not re.search(r'(restart|stop|--force-recreate)\s+nginx', text), path.name
        assert '-s reload' in COMMON.read_text(encoding='utf-8')


# ── resolve_deploy_target ──────────────────────────────────────────────────

def _extract_resolver() -> str:
    text = DEPLOY.read_text(encoding='utf-8')
    match = re.search(r'# >>> resolve_deploy_target\n(.*?)# <<< resolve_deploy_target', text, re.S)
    assert match, 'marcadores de resolve_deploy_target ausentes en deploy.sh'
    return match.group(1)


@pytest.fixture
def repo(tmp_path):
    """origin with main: c1 → c2 → c3, plus a commit c_side not on main."""
    if shutil.which('git') is None:
        pytest.skip('git no disponible')
    origin, work = tmp_path / 'origin.git', tmp_path / 'work'
    run = lambda *a, cwd=work: subprocess.run(['git', *a], cwd=cwd, check=True,  # noqa: E731
                                              capture_output=True, text=True).stdout.strip()
    subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True)
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(work)], check=True)
    run('config', 'user.email', 't@t')
    run('config', 'user.name', 't')
    shas = {}
    for name in ('c1', 'c2', 'c3'):
        (work / 'f').write_text(name)
        run('add', 'f')
        run('commit', '-qm', name)
        shas[name] = run('rev-parse', 'HEAD')
    run('remote', 'add', 'origin', str(origin))
    run('push', '-q', 'origin', 'main')
    run('fetch', '-q', 'origin')
    run('checkout', '-qb', 'side', shas['c2'])
    (work / 'g').write_text('side')
    run('add', 'g')
    run('commit', '-qm', 'side')
    shas['side'] = run('rev-parse', 'HEAD')
    run('checkout', '-q', 'main')
    return work, shas


def _resolve(work, target, live=''):
    script = _extract_resolver() + f'\nresolve_deploy_target "{target}" "{live}"'
    return _bash(script, work)


@needs_bash
@needs_git
class TestResolveDeployTarget:
    def test_tip_of_main_resolves_to_full_sha(self, repo):
        work, shas = repo
        result = _resolve(work, shas['c3'][:8], shas['c2'])
        assert result.returncode == 0
        assert result.stdout.strip() == shas['c3']

    def test_empty_target_means_origin_main(self, repo):
        work, shas = repo
        assert _resolve(work, '').stdout.strip() == shas['c3']

    def test_older_than_live_is_a_noop(self, repo):
        work, shas = repo
        assert _resolve(work, shas['c1'], shas['c3']).returncode == 3

    def test_redeploying_the_live_sha_is_allowed(self, repo):
        work, shas = repo
        assert _resolve(work, shas['c3'], shas['c3']).returncode == 0

    def test_commit_not_on_main_is_refused(self, repo):
        work, shas = repo
        assert _resolve(work, shas['side']).returncode == 1

    def test_unknown_sha_is_refused(self, repo):
        work, _ = repo
        assert _resolve(work, 'deadbeefdeadbeef').returncode == 1

    def test_first_deploy_without_live_state(self, repo):
        work, shas = repo
        assert _resolve(work, shas['c2'], '').returncode == 0

    def test_live_sha_unknown_to_git_does_not_block(self, repo):
        """After a history rewrite the recorded SHA may no longer exist."""
        work, shas = repo
        assert _resolve(work, shas['c2'], 'f' * 40).returncode == 0


# ── helpers in _common.sh ──────────────────────────────────────────────────

@needs_bash
def test_write_upstream_targets_color_and_static_release(tmp_path):
    (tmp_path / '.deploy' / 'nginx').mkdir(parents=True)
    result = _bash(f'. "{COMMON.as_posix()}"; STATE_DIR=.deploy; write_upstream green abc123def456', tmp_path)
    assert result.returncode == 0, result.stderr
    conf = (tmp_path / '.deploy' / 'nginx' / 'upstream.conf').read_text()
    assert 'upstream siiap_app' in conf
    assert 'server web-green:5000;' in conf
    assert re.search(r'map \$host \$static_release \{\s*default "abc123def456";', conf)
    assert not (tmp_path / '.deploy' / 'nginx' / 'upstream.conf.tmp').exists()


@needs_bash
@pytest.mark.parametrize('color,other', [('blue', 'green'), ('green', 'blue'), ('', 'blue')])
def test_other_color(tmp_path, color, other):
    result = _bash(f'. "{COMMON.as_posix()}"; other_color "{color}"', tmp_path)
    assert result.stdout.strip() == other


@needs_bash
def test_write_state_is_atomic_and_readable(tmp_path):
    (tmp_path / '.deploy').mkdir()
    script = f'. "{COMMON.as_posix()}"; write_state active-color blue; read_state active-color; read_state missing'
    result = _bash(script, tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == 'blue'


def test_upstream_name_matches_nginx_config():
    nginx = (ROOT / 'docker' / 'nginx' / 'nginx.conf').read_text(encoding='utf-8')
    common = COMMON.read_text(encoding='utf-8')
    assert 'upstream siiap_app' in common
    assert '$static_release' in common and '$static_release' in nginx
    assert 'http://siiap_app' in nginx


def test_probe_matches_ready_payload_keys():
    """probe_public greps the JSON produced by /ready; keep both in sync."""
    health = (ROOT / 'app' / 'routes' / 'api' / 'health_api.py').read_text(encoding='utf-8')
    common = COMMON.read_text(encoding='utf-8')
    assert "'status': 'ready'" in health and '"status": ?"ready"' in common
    assert "'version':" in health and '\\"version\\": ?' in common

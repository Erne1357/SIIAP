"""Invariants of the production compose file, nginx config and image build."""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.infra

ROOT = Path(__file__).resolve().parents[2]
DOCKER = ROOT / 'docker'


@pytest.fixture(scope='module')
def prod():
    return yaml.safe_load((DOCKER / 'docker-compose.prod.yml').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def nginx_conf():
    return (DOCKER / 'nginx' / 'nginx.conf').read_text(encoding='utf-8')


def _env(service) -> dict:
    env = service.get('environment') or {}
    if isinstance(env, list):
        env = dict(item.split('=', 1) for item in env)
    return env


# ── compose ────────────────────────────────────────────────────────────────

def test_there_is_no_single_web_service(prod):
    assert 'web' not in prod['services']
    assert {'web-blue', 'web-green'} <= set(prod['services'])


@pytest.mark.parametrize('color', ['blue', 'green'])
def test_colors_live_behind_their_profile(prod, color):
    service = prod['services'][f'web-{color}']
    assert service['profiles'] == [color]
    assert _env(service)['INSTANCE_COLOR'] == color


def test_colors_are_identical_except_color(prod):
    blue, green = dict(prod['services']['web-blue']), dict(prod['services']['web-green'])
    for svc in (blue, green):
        svc.pop('profiles')
        svc['environment'] = {k: v for k, v in _env(svc).items() if k != 'INSTANCE_COLOR'}
    assert blue == green


def test_every_app_service_runs_the_same_release_image(prod):
    for name in ('web-blue', 'web-green', 'celery-worker', 'celery-beat'):
        assert prod['services'][name]['image'] == 'siiap-app:${IMAGE_TAG:-latest}', name


def test_only_web_colors_build(prod):
    builders = {n for n, s in prod['services'].items() if 'build' in s}
    assert builders == {'web-blue', 'web-green', 'db'}


def test_no_long_running_service_migrates(prod):
    for name in ('web-blue', 'web-green', 'celery-worker', 'celery-beat'):
        assert _env(prod['services'][name]).get('SKIP_MIGRATIONS') == 'true', name


def test_static_version_follows_the_release(prod):
    for name in ('web-blue', 'web-green', 'celery-worker', 'celery-beat'):
        assert _env(prod['services'][name]).get('STATIC_VERSION') == '${IMAGE_TAG:-latest}', name


def test_web_readiness_probe(prod):
    test = ' '.join(prod['services']['web-blue']['healthcheck']['test'])
    assert '/ready' in test


def test_infra_has_no_profile(prod):
    for name in ('db', 'redis', 'nginx', 'celery-worker', 'celery-beat'):
        assert 'profiles' not in prod['services'][name], name


def test_postgres_18_volume_layout(prod):
    assert 'pgdata18:/var/lib/postgresql' in prod['services']['db']['volumes']
    # The PG16 volume stays declared: it is the way back.
    assert 'pgdata' in prod['volumes'] and 'pgdata18' in prod['volumes']


def test_nginx_only_on_loopback_8081(prod):
    assert prod['services']['nginx']['ports'] == ['127.0.0.1:8081:80']


def test_nginx_mounts_directories_not_single_files(prod):
    """A single-file bind mount keeps the old inode after `git reset --hard`."""
    for volume in prod['services']['nginx']['volumes']:
        source = volume.split(':')[0]
        assert not re.search(r'\.(conf|cfg)$', source), volume
    command = prod['services']['nginx']['command']
    assert '/etc/nginx/siiap/nginx.conf' in command


def test_nginx_does_not_depend_on_a_color(prod):
    assert 'depends_on' not in prod['services']['nginx']


def test_web_mounts_database_read_only_and_never_bakes_it(prod):
    assert '../database:/app/database:ro' in prod['services']['web-blue']['volumes']


def test_e2e_stack_never_uses_database_dir():
    lines = (DOCKER / 'docker-compose.e2e.yml').read_text(encoding='utf-8').splitlines()
    code = [line for line in lines if not line.lstrip().startswith('#')]
    assert not any('database' in line and 'DATABASE_URL' not in line for line in code)


# ── nginx ──────────────────────────────────────────────────────────────────

def test_nginx_routes_through_the_generated_upstream(nginx_conf):
    assert 'include /etc/nginx/siiap-runtime/upstream.conf;' in nginx_conf
    targets = re.findall(r'proxy_pass\s+([^;]+);', nginx_conf)
    assert targets and all(t.startswith('http://siiap_app') for t in targets), targets
    assert 'web:5000' not in nginx_conf


def test_static_served_from_release_directory(nginx_conf):
    block = nginx_conf[nginx_conf.index('location /static/'):]
    assert 'root /srv/static/$static_release;' in block[:400]


def test_ready_is_not_public(nginx_conf):
    block = nginx_conf[nginx_conf.index('location = /ready'):]
    block = block[:block.index('}')]
    assert 'deny all;' in block


@pytest.mark.parametrize('header', ['X-Content-Type-Options', 'Referrer-Policy', 'X-Frame-Options',
                                    'Permissions-Policy'])
def test_security_headers_also_on_static(nginx_conf, header):
    assert nginx_conf.count(f'add_header {header}') >= 2


def test_body_limit_above_app_limit(nginx_conf):
    nginx_mb = int(re.search(r'client_max_body_size (\d+)M;', nginx_conf).group(1))
    config = (ROOT / 'app' / 'config.py').read_text(encoding='utf-8')
    app_mb = int(re.search(r'MAX_CONTENT_LENGTH = (\d+) \* 1024 \* 1024', config).group(1))
    assert nginx_mb > app_mb


def test_canonical_host_matches_app_config(nginx_conf):
    config = (ROOT / 'app' / 'config.py').read_text(encoding='utf-8')
    host = re.search(r"CANONICAL_PRODUCTION_BASE_URL = 'https://([^']+)'", config).group(1)
    assert f'set $app_public_host "{host}";' in nginx_conf


# ── image build ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('pattern', ['.git', 'database', 'instance', '*.sql', '*.dump', '.env*',
                                     'backups', '.deploy', 'tests', 'venv'])
def test_dockerignore_keeps_data_out_of_the_image(pattern):
    lines = (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
    assert pattern in lines


def test_db_image_has_its_own_ignore_file():
    text = (DOCKER / 'Dockerfile.db.dockerignore').read_text(encoding='utf-8')
    assert '!database/DDL/0*.sql' in text and '!database/DML/0*.sql' in text


def test_python_version_is_the_same_everywhere():
    prod = re.search(r'FROM python:(\d+\.\d+)', (DOCKER / 'Dockerfile').read_text()).group(1)
    test = re.search(r'FROM python:(\d+\.\d+)', (DOCKER / 'Dockerfile.test').read_text()).group(1)
    ci = re.search(r'PYTHON_VERSION: "(\d+\.\d+)"',
                   (ROOT / '.github' / 'workflows' / '_tests.yml').read_text()).group(1)
    assert prod == test == ci


def test_dev_requirements_extend_production():
    assert (ROOT / 'requirements-dev.txt').read_text().splitlines()[2] == '-r requirements.txt'
    assert 'pytest' not in (ROOT / 'requirements.txt').read_text()


def test_gitignore_keeps_deploy_state_local():
    lines = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
    for entry in ('.deploy/', 'backups/', '*.dump', 'database/*'):
        assert entry in lines, entry

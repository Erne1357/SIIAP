"""Unit tests: history_formatter, validate_password_strength and app/config.py bootstrap checks."""

import importlib
import json
from types import SimpleNamespace

import pytest

from app.utils.history_formatter import HistoryFormatter as H
from app.routes.api.auth_api import validate_password_strength


# --- HistoryFormatter -------------------------------------------------------

@pytest.mark.parametrize('action,expected', [
    ('password_reset', 'Contraseña restablecida'),
    ('password_changed', 'Contraseña actualizada'),
    ('deactivated', 'Usuario desactivado'),
    ('activated', 'Usuario activado'),
    ('profile_completed', 'Perfil completado exitosamente'),
    ('created', 'Usuario creado en el sistema'),
    ('deleted', 'Usuario eliminado'),
    ('program_enrolled', 'Inscrito a un programa'),
    ('event_registered', 'Registrado a un evento'),
])
def test_default_messages_without_details(action, expected):
    assert H.format_details(action, None) == expected
    assert H.format_details(action, '') == expected


def test_unknown_action_without_details():
    assert H.format_details('weird_action', None) == 'Acción realizada: weird_action'


def test_unknown_action_with_details_generic_fallback():
    assert H.format_details('weird', json.dumps({'x': 1})) == 'Acción realizada: weird'


def test_generic_includes_reason():
    out = H.format_details('deactivated', json.dumps({'reason': 'inactividad'}))
    assert out == 'Usuario desactivado (inactividad)'


@pytest.mark.parametrize('key', ['reason', 'comment', 'message', 'description'])
def test_generic_important_keys(key):
    out = H.format_details('weird', json.dumps({key: 'zzz'}))
    assert out.endswith('(zzz)')


def test_generic_empty_important_value_ignored():
    assert H.format_details('weird', json.dumps({'reason': ''})) == 'Acción realizada: weird'


def test_non_json_details_returned_raw():
    assert H.format_details('weird', 'texto libre') == 'texto libre'


def test_dict_details_accepted():
    assert H.format_details('program_enrolled', {'program_name': 'MII'}) == 'Inscrito al programa MII'


def test_json_array_details_does_not_crash_known_action():
    # json.loads gives a list; formatters call .get on it. Document current behavior.
    try:
        out = H.format_details('weird', '[1,2]')
    except Exception as e:  # pragma: no cover
        pytest.fail(f'raised {e!r}')
    assert isinstance(out, str)


def test_program_enrolled():
    assert H.format_details('program_enrolled', json.dumps({'program_name': 'Maestría en X'})) == 'Inscrito al programa Maestría en X'


def test_program_enrolled_missing_name():
    assert 'programa desconocido' in H.format_details('program_enrolled', '{"a":1}')


def test_transfer_requested_with_reason():
    out = H.format_details('program_transfer_requested', json.dumps({'from_program': 'A', 'to_program': 'B', 'reason': 'cambio'}))
    assert out == 'Solicitó cambio de A a B (Motivo: cambio)'


def test_transfer_requested_without_reason():
    out = H.format_details('program_transfer_requested', json.dumps({'from_program': 'A', 'to_program': 'B'}))
    assert out == 'Solicitó cambio de A a B'


def test_transferred_with_docs():
    out = H.format_details('program_transferred', json.dumps({'from_program': 'A', 'to_program': 'B', 'documents_moved': 3, 'documents_lost': 1}))
    assert out == 'Cambio de programa completado: de A a B. 3 documentos transferidos, 1 documentos perdidos'


def test_transferred_no_docs():
    out = H.format_details('program_transferred', json.dumps({'from_program': 'A', 'to_program': 'B'}))
    assert out == 'Cambio de programa completado: de A a B'


@pytest.mark.parametrize('admin,expected', [
    (False, "Subió documento 'Acta' para MII"),
    (True, "Coordinador subió documento 'Acta' del programa MII"),
])
def test_document_uploaded(admin, expected):
    d = {'archive_name': 'Acta', 'program_name': 'MII', 'uploaded_by_admin': admin}
    assert H.format_details('document_uploaded', json.dumps(d)) == expected


@pytest.mark.parametrize('admin,expected', [
    (False, "Eliminó documento 'Acta' de MII"),
    (True, "Coordinador eliminó documento 'Acta' del programa MII"),
])
def test_document_deleted(admin, expected):
    d = {'archive_name': 'Acta', 'program_name': 'MII', 'deleted_by_admin': admin}
    assert H.format_details('document_deleted', json.dumps(d)) == expected


@pytest.mark.parametrize('status,text', [
    ('approved', 'aprobado'), ('rejected', 'rechazado'), ('pending', 'puesto en revisión'), ('other', 'other'),
])
def test_document_reviewed(status, text):
    out = H.format_details('document_reviewed', json.dumps({'archive_name': 'A', 'review_status': status}))
    assert out == f"Documento 'A' fue {text}"


def test_document_reviewed_with_comment():
    out = H.format_details('document_reviewed', json.dumps({'archive_name': 'A', 'review_status': 'rejected', 'reviewer_comment': 'borroso'}))
    assert out.endswith('(Comentario: borroso)')


def test_document_purged_default_reason():
    assert H.format_details('document_purged', '{"archive_name":"A"}') == "Documento 'A' eliminado por política de retención"


def test_extension_requested_variants():
    base = {'archive_name': 'A', 'requested_until': '2026-01-01'}
    assert H.format_details('extension_requested', json.dumps(base)) == "Solicitó prórroga para 'A' hasta 2026-01-01"
    out = H.format_details('extension_requested', json.dumps({**base, 'requested_by_admin': True, 'reason': 'x'}))
    assert out == "Coordinador solicitó prórroga para 'A' hasta 2026-01-01 (Motivo: x)"


@pytest.mark.parametrize('decision,text', [('granted', 'aprobada'), ('rejected', 'rechazada'), ('cancelled', 'cancelada'), ('zz', 'zz')])
def test_extension_decided(decision, text):
    out = H.format_details('extension_decided', json.dumps({'archive_name': 'A', 'decision': decision}))
    assert out == f"Prórroga para 'A' fue {text}"


def test_extension_decided_granted_until_and_condition():
    d = {'archive_name': 'A', 'decision': 'granted', 'granted_until': '2026-02-02', 'condition_text': 'entregar'}
    assert H.format_details('extension_decided', json.dumps(d)) == "Prórroga para 'A' fue aprobada hasta 2026-02-02 (Condiciones: entregar)"


def test_extension_rejected_ignores_granted_until():
    d = {'archive_name': 'A', 'decision': 'rejected', 'granted_until': '2026-02-02'}
    assert 'hasta' not in H.format_details('extension_decided', json.dumps(d))


@pytest.mark.parametrize('etype,text', [('interview', 'entrevista'), ('workshop', 'taller'), ('conference', 'conferencia'), ('meeting', 'reunión'), ('x', 'x')])
def test_event_registered_types(etype, text):
    out = H.format_details('event_registered', json.dumps({'event_title': 'E', 'event_type': etype}))
    assert out == f"Se registró al evento 'E' ({text})"


def test_event_registered_no_type():
    assert H.format_details('event_registered', '{"event_title":"E"}') == "Se registró al evento 'E'"


def test_appointment_assigned_formats_iso():
    out = H.format_details('appointment_assigned', json.dumps({'event_title': 'E', 'appointment_datetime': '2026-07-31T14:30:00'}))
    assert out == "Se le asignó cita para 'E' el 31/07/2026 a las 14:30"


def test_appointment_assigned_z_suffix():
    out = H.format_details('appointment_assigned', json.dumps({'event_title': 'E', 'appointment_datetime': '2026-07-31T14:30:00Z'}))
    assert '31/07/2026 a las 14:30' in out


def test_appointment_assigned_unparseable_kept():
    out = H.format_details('appointment_assigned', json.dumps({'event_title': 'E', 'appointment_datetime': 'mañana'}))
    assert out.endswith('el mañana')


def test_appointment_cancelled_variants():
    assert H.format_details('appointment_cancelled', '{"event_title":"E"}') == "Cita para 'E' fue cancelada"
    out = H.format_details('appointment_cancelled', json.dumps({'event_title': 'E', 'cancelled_by_admin': True, 'reason': 'lluvia'}))
    assert out == "Cita para 'E' fue cancelada por coordinador (Motivo: lluvia)"


def test_appointment_cancelled_default_user_reason_hidden():
    out = H.format_details('appointment_cancelled', json.dumps({'event_title': 'E', 'reason': 'Cancelada por el usuario'}))
    assert 'Motivo' not in out


def test_control_number_assigned():
    out = H.format_details('control_number_assigned', json.dumps({'control_number': 'M123', 'program': 'MII'}))
    assert out == 'Se asignó número de control M123 para MII'


def test_archive_created_and_deleted():
    assert H.format_details('archive_created', '{"archive_name":"A","step_name":"S"}') == "Creó el archivo 'A' en el paso S"
    out = H.format_details('archive_deleted', json.dumps({'archive_name': 'A', 'archive_description': 'd', 'force_used': True}))
    assert out == "Eliminó el archivo 'A' (d) (eliminación forzada)"


def test_archive_updated_translates_fields():
    d = {'archive_name': 'A', 'step_name': 'S', 'changes': {'name': 1, 'required': 2, 'custom': 3}}
    out = H.format_details('archive_updated', json.dumps(d))
    assert out == "Modificó el archivo 'A' en el paso S (cambió: nombre, obligatoriedad, custom)"


def test_archive_updated_single_change_and_no_changes():
    out = H.format_details('archive_updated', json.dumps({'archive_name': 'A', 'step_name': 'S', 'changes': {'description': 1}}))
    assert out.endswith('(cambió: descripción)')
    out = H.format_details('archive_updated', json.dumps({'archive_name': 'A', 'step_name': 'S', 'changes': {}}))
    assert 'cambió' not in out


@pytest.mark.parametrize('replacement,verb', [(False, 'Subió'), (True, 'Reemplazó')])
def test_template_uploaded(replacement, verb):
    d = {'archive_name': 'A', 'template_filename': 't.docx', 'was_replacement': replacement}
    assert H.format_details('template_uploaded', json.dumps(d)) == f"{verb} la plantilla 't.docx' para el archivo 'A'"


def test_role_changed_translates():
    out = H.format_details('role_changed', json.dumps({'old_role': 'applicant', 'new_role': 'program_admin'}))
    assert out == 'Rol cambiado de solicitante a coordinador de programa'


def test_role_changed_unknown_role_kept():
    out = H.format_details('role_changed', json.dumps({'old_role': 'x', 'new_role': 'student'}))
    assert out == 'Rol cambiado de x a student'


@pytest.mark.parametrize('fields,expected', [
    ({'a': 1}, 'Actualizó a'),
    ({'a': 1, 'b': 2, 'c': 3}, 'Actualizó a, b, c'),
    ({'a': 1, 'b': 2, 'c': 3, 'd': 4}, 'Actualizó 4 campos de información personal'),
    ([], 'Actualizó información personal'),
    # Regression: an empty dict used to render "Actualizó " with nothing after it.
    ({}, 'Actualizó información personal'),
])
def test_basic_info_updated(fields, expected):
    out = H.format_details('basic_info_updated', json.dumps({'changed_fields': fields}))
    assert out == expected


def test_basic_info_updated_without_changed_fields():
    assert H.format_details('basic_info_updated', '{"x":1}') == 'Actualizó información personal'


def test_format_history_entry_object_and_dict():
    f = H()
    obj = SimpleNamespace(action='program_enrolled', details=json.dumps({'program_name': 'P'}))
    assert f.format_history_entry(obj) == 'Inscrito al programa P'
    assert f.format_history_entry({'action': 'created'}) == 'Usuario creado en el sistema'
    assert f.format_history_entry(SimpleNamespace(action='created', details=None)) == 'Usuario creado en el sistema'


def test_format_entry_dict_adds_fields():
    entry = {'action': 'created', 'details': '', 'timestamp': '2026-07-31T14:30:00'}
    out = H.format_history_entry_dict(entry)
    assert out['formatted_details'] == 'Usuario creado en el sistema'
    assert out['raw_details'] == ''
    assert out['date_only'] == '31/07/2026' and out['time_only'] == '14:30'
    assert entry.get('formatted_details') is None  # input not mutated


def test_format_entry_dict_bad_timestamp_degrades():
    out = H.format_history_entry_dict({'action': 'created', 'timestamp': 'bad'})
    assert out['formatted_timestamp'] == 'bad' and out['date_only'] == ''


def test_format_entry_dict_formatted_timestamp_is_spanish():
    # Regression: strftime('%B') printed 'July' (the app sets no Spanish locale).
    out = H.format_history_entry_dict({'action': 'created', 'timestamp': '2026-07-31T14:30:00'})
    assert out['formatted_timestamp'] == '31 de julio de 2026 a las 14:30'


# --- validate_password_strength --------------------------------------------

@pytest.mark.parametrize('pw', ['Abcdef1!', 'Zz9#aaaa', 'Contraseña1!', 'A1b2c3d4$', 'x' * 20 + 'X1!'])
def test_password_valid(pw):
    assert validate_password_strength(pw) == (True, 'Contraseña válida')


@pytest.mark.parametrize('pw,fragment', [
    ('', '8 caracteres'),
    ('Ab1!', '8 caracteres'),
    ('Abcde1!', '8 caracteres'),
    ('abcdefg1!', 'mayúscula'),
    ('ABCDEFG1!', 'minúscula'),
    ('Abcdefgh!', 'número'),
    ('Abcdefg12', 'especial'),
    ('Abcdefg1_', 'especial'),     # underscore is not in the accepted set
    ('Abcdefg1-', 'especial'),
    ('Abcdefg1 ', 'especial'),
    ('Ábcdefg1ñ', 'mayúscula'),  # only ASCII A-Z counts as uppercase
])
def test_password_invalid(pw, fragment):
    ok, msg = validate_password_strength(pw)
    assert ok is False and fragment in msg


@pytest.mark.parametrize('special', list('!@#$%^&*(),.?":{}|<>'))
def test_password_each_special_char_accepted(special):
    assert validate_password_strength(f'Abcdef1{special}')[0] is True


def test_password_exactly_eight_boundary():
    assert validate_password_strength('Abcde1!x')[0] is True
    assert validate_password_strength('Abcd1!x')[0] is False


def test_password_length_checked_first():
    assert '8 caracteres' in validate_password_strength('a')[1]


# --- app.config bootstrap ---------------------------------------------------

import app.config as cfg  # noqa: E402


@pytest.fixture
def reload_config(monkeypatch):
    """Reload app.config under patched env, then restore a pristine module."""
    def _reload():
        return importlib.reload(cfg)
    yield _reload
    monkeypatch.undo()
    importlib.reload(cfg)


@pytest.fixture
def not_pytest(monkeypatch):
    monkeypatch.setattr(cfg, '_running_under_pytest', lambda: False)


def test_running_under_pytest_true_here():
    assert cfg._running_under_pytest() is True


def test_prod_without_base_url_refuses_boot(monkeypatch, not_pytest):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    with pytest.raises(cfg.MissingProductionConfigError) as e:
        cfg._require_production_base_url()
    assert 'APP_BASE_URL' in str(e.value) and cfg.CANONICAL_PRODUCTION_BASE_URL in str(e.value)


@pytest.mark.parametrize('blank', ['', '   '])
def test_prod_blank_base_url_refuses_boot(monkeypatch, not_pytest, blank):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('APP_BASE_URL', blank)
    with pytest.raises(cfg.MissingProductionConfigError):
        cfg._require_production_base_url()


def test_prod_env_case_and_whitespace_insensitive(monkeypatch, not_pytest):
    monkeypatch.setenv('FLASK_ENV', ' Production ')
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    with pytest.raises(cfg.MissingProductionConfigError):
        cfg._require_production_base_url()


def test_prod_with_base_url_ok(monkeypatch, not_pytest):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('APP_BASE_URL', 'https://siiap.example.org')
    cfg._require_production_base_url()


@pytest.mark.parametrize('env', ['development', 'testing', 'staging', ''])
def test_non_prod_never_requires_base_url(monkeypatch, not_pytest, env):
    monkeypatch.setenv('FLASK_ENV', env)
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    cfg._require_production_base_url()


def test_unset_flask_env_defaults_to_development(monkeypatch, not_pytest):
    monkeypatch.delenv('FLASK_ENV', raising=False)
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    cfg._require_production_base_url()


def test_pytest_detection_bypasses_check(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    cfg._require_production_base_url()  # still under pytest -> no raise


def test_module_import_fails_in_prod_without_base_url(monkeypatch, reload_config):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
    import sys
    saved = sys.modules.pop('pytest')
    try:
        # reload redefines the exception class, so match on the base type
        with pytest.raises(RuntimeError, match='APP_BASE_URL'):
            importlib.reload(cfg)
    finally:
        sys.modules['pytest'] = saved


def test_static_version_from_env(monkeypatch, reload_config):
    monkeypatch.setenv('STATIC_VERSION', 'abc1234')
    assert reload_config().Config.STATIC_VERSION == 'abc1234'


@pytest.mark.parametrize('val', [None, ''])
def test_static_version_fallback(monkeypatch, reload_config, val):
    if val is None:
        monkeypatch.delenv('STATIC_VERSION', raising=False)
    else:
        monkeypatch.setenv('STATIC_VERSION', val)
    assert reload_config().Config.STATIC_VERSION == '1.0.42081201'


def test_app_base_url_trailing_slash_stripped(monkeypatch, reload_config):
    monkeypatch.setenv('APP_BASE_URL', 'https://x.org/')
    assert reload_config().Config.APP_BASE_URL == 'https://x.org'


def test_app_base_url_default_is_dev(monkeypatch, reload_config):
    monkeypatch.delenv('APP_BASE_URL', raising=False)
    assert reload_config().Config.APP_BASE_URL == cfg.DEVELOPMENT_BASE_URL


# --- fail-closed security defaults -------------------------------------------

_SECURITY_VARS = ('FLASK_DEBUG', 'SESSION_COOKIE_SECURE', 'PREFERRED_URL_SCHEME')


def _clear_security_vars(monkeypatch):
    for name in _SECURITY_VARS:
        monkeypatch.delenv(name, raising=False)


def test_prod_defaults_are_secure_when_vars_unset(monkeypatch, reload_config):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('APP_BASE_URL', 'https://siiap.example.org')
    _clear_security_vars(monkeypatch)
    c = reload_config().Config
    assert c.DEBUG is False
    assert c.SESSION_COOKIE_SECURE is True
    assert c.REMEMBER_COOKIE_SECURE is True
    assert c.PREFERRED_URL_SCHEME == 'https'


def test_dev_defaults_keep_debug_and_plain_cookies(monkeypatch, reload_config):
    monkeypatch.setenv('FLASK_ENV', 'development')
    _clear_security_vars(monkeypatch)
    c = reload_config().Config
    assert c.DEBUG is True
    assert c.SESSION_COOKIE_SECURE is False
    assert c.PREFERRED_URL_SCHEME == 'http'


def test_prod_explicit_insecure_cookie_override_is_honoured(monkeypatch, reload_config):
    # The E2E stack runs FLASK_ENV=production over plain HTTP.
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('APP_BASE_URL', 'https://siiap.example.org')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'False')
    c = reload_config().Config
    assert c.SESSION_COOKIE_SECURE is False
    assert c.REMEMBER_COOKIE_SECURE is False


@pytest.mark.parametrize('raw, expected', [
    ('true', True), ('True', True), ('1', True), (' yes ', True), ('on', True),
    ('false', False), ('0', False), ('no', False), ('anything', False),
])
def test_env_flag_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv('SIIAP_TEST_FLAG', raw)
    assert cfg._env_flag('SIIAP_TEST_FLAG', default=not expected) is expected


@pytest.mark.parametrize('raw', [None, '', '   '])
def test_env_flag_unset_or_blank_uses_default(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv('SIIAP_TEST_FLAG', raising=False)
    else:
        monkeypatch.setenv('SIIAP_TEST_FLAG', raw)
    assert cfg._env_flag('SIIAP_TEST_FLAG', default=True) is True
    assert cfg._env_flag('SIIAP_TEST_FLAG', default=False) is False


def test_prod_with_debug_enabled_refuses_boot(monkeypatch, not_pytest):
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('FLASK_DEBUG', 'True')
    with pytest.raises(cfg.MissingProductionConfigError, match='FLASK_DEBUG'):
        cfg._require_production_debug_off()


@pytest.mark.parametrize('raw', [None, 'false', '0'])
def test_prod_with_debug_off_or_unset_boots(monkeypatch, not_pytest, raw):
    monkeypatch.setenv('FLASK_ENV', 'production')
    if raw is None:
        monkeypatch.delenv('FLASK_DEBUG', raising=False)
    else:
        monkeypatch.setenv('FLASK_DEBUG', raw)
    cfg._require_production_debug_off()


def test_dev_with_debug_enabled_boots(monkeypatch, not_pytest):
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.setenv('FLASK_DEBUG', 'True')
    cfg._require_production_debug_off()

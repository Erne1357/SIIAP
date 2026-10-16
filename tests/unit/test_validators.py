"""Unit tests for app/utils/validators.py."""

import pytest

from app.utils.validators import (
    InputValidationError, validate_person_name, validate_short_text,
    NAME_MAX_LENGTH, SHORT_TEXT_MAX_LENGTH,
)


@pytest.mark.parametrize('name', [
    'José', 'María Fernanda', 'Nuñez', 'ÑANDÚ', "O'Brien", 'D’Angelo', 'Pérez-Reverte',
    'J. Carlos', 'Zoë', 'Łukasz', '李雷', 'Åsa', 'Müller',
])
def test_person_name_accepts_real_names(name):
    assert validate_person_name(name, label='nombre') == name


def test_person_name_trims_and_collapses_whitespace():
    assert validate_person_name('  Ana \t  María\n', label='nombre') == 'Ana María'


def test_person_name_nbsp_collapsed():
    assert validate_person_name('Ana María', label='nombre') == 'Ana María'


def test_person_name_nfc_normalized():
    out = validate_person_name('José', label='nombre')
    assert out == 'José' and len(out) == 4


def test_person_name_combining_mark_with_letter_accepted():
    assert validate_person_name('á', label='n')


@pytest.mark.parametrize('bad', [None, '', '   ', '\t\n'])
def test_person_name_required_empty(bad):
    with pytest.raises(InputValidationError) as e:
        validate_person_name(bad, label='nombre')
    assert 'obligatorio' in e.value.message
    assert e.value.field == 'nombre'


@pytest.mark.parametrize('bad', [None, '', '  '])
def test_person_name_optional_empty_returns_none(bad):
    assert validate_person_name(bad, label='x', required=False) is None


@pytest.mark.parametrize('bad', [123, 1.5, ['a'], {'a': 1}, True])
def test_person_name_non_string(bad):
    with pytest.raises(InputValidationError) as e:
        validate_person_name(bad, label='nombre')
    assert 'texto' in e.value.message


@pytest.mark.parametrize('bad', [
    '<script>alert(1)</script>', 'Ana<b>', 'a>b', '"><img src=x onerror=alert(1)>',
])
def test_person_name_rejects_markup(bad):
    with pytest.raises(InputValidationError):
        validate_person_name(bad, label='nombre')


@pytest.mark.parametrize('bad', [
    "Robert'); DROP TABLE user;--", 'Ana1', 'Ana_', 'Ana@x', 'a/b', 'a\\b', 'a;b', 'a(b)',
    'Ana&', '$ana', '{{7*7}}', '${x}', 'Ana, Luz', 'a=b', 'a+b', '😀 Ana',
])
def test_person_name_rejects_symbols_digits(bad):
    with pytest.raises(InputValidationError):
        validate_person_name(bad, label='nombre')


@pytest.mark.parametrize('bad', ['Ana\x00', 'Ana\x07', 'An​a', 'Ana‮', 'An‍a', '﻿Ana', 'Ana⁦'])
def test_person_name_rejects_control_and_format_chars(bad):
    with pytest.raises(InputValidationError) as e:
        validate_person_name(bad, label='nombre')
    assert 'no permitidos' in e.value.message


@pytest.mark.parametrize('bad', ["'", '-', '.', '- - .', "'-'"])
def test_person_name_requires_a_letter(bad):
    with pytest.raises(InputValidationError) as e:
        validate_person_name(bad, label='nombre')
    assert 'al menos una letra' in e.value.message


def test_person_name_length_boundary():
    ok = 'a' * NAME_MAX_LENGTH
    assert validate_person_name(ok, label='n') == ok
    with pytest.raises(InputValidationError) as e:
        validate_person_name(ok + 'a', label='n')
    assert '50' in e.value.message


def test_person_name_length_measured_after_normalization():
    raw = '  ' + 'a' * 25 + '     ' + 'b' * 23 + '  '
    assert len(validate_person_name(raw, label='n')) == 49


def test_person_name_custom_max_length():
    with pytest.raises(InputValidationError):
        validate_person_name('abcd', label='n', max_length=3)
    assert validate_person_name('abc', label='n', max_length=3) == 'abc'


def test_person_name_message_includes_label():
    with pytest.raises(InputValidationError) as e:
        validate_person_name('', label='apellido')
    assert 'apellido' in e.value.message


def test_input_validation_error_is_value_error():
    assert issubclass(InputValidationError, ValueError)
    assert InputValidationError('m').field is None


# --- validate_short_text ----------------------------------------------------

@pytest.mark.parametrize('value', ['user123', 'a@b.com', 'Beca-2026 (SEP)', 'ñandú_1', "it's", 'a&b'])
def test_short_text_permissive_charset(value):
    assert validate_short_text(value, label='x') == value


def test_short_text_optional_by_default():
    assert validate_short_text('', label='x') is None
    assert validate_short_text(None, label='x') is None


def test_short_text_required_empty():
    with pytest.raises(InputValidationError) as e:
        validate_short_text('  ', label='usuario', required=True)
    assert 'obligatorio' in e.value.message


def test_short_text_normalizes_whitespace():
    assert validate_short_text('  a   b ', label='x') == 'a b'


@pytest.mark.parametrize('bad', ['<b>', 'a>b', '<script>', 'x<'])
def test_short_text_rejects_angle_brackets(bad):
    with pytest.raises(InputValidationError):
        validate_short_text(bad, label='x')


@pytest.mark.parametrize('bad', ['a\x00b', 'a​b', 'a\x1b[0m'])
def test_short_text_rejects_control(bad):
    with pytest.raises(InputValidationError):
        validate_short_text(bad, label='x')


def test_short_text_length_boundary():
    assert validate_short_text('a' * SHORT_TEXT_MAX_LENGTH, label='x')
    with pytest.raises(InputValidationError):
        validate_short_text('a' * (SHORT_TEXT_MAX_LENGTH + 1), label='x')


def test_short_text_custom_max_for_email():
    assert validate_short_text('a' * 100, label='correo', max_length=100)
    with pytest.raises(InputValidationError):
        validate_short_text('a' * 101, label='correo', max_length=100)


@pytest.mark.parametrize('bad', [5, [], {}, False])
def test_short_text_non_string(bad):
    with pytest.raises(InputValidationError):
        validate_short_text(bad, label='x')


def test_short_text_sql_injection_string_is_allowed_as_data():
    # Boundary validation does not escape SQL; parameterized queries do.
    assert validate_short_text("' OR 1=1 --", label='x') == "' OR 1=1 --"

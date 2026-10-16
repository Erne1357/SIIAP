"""Unit tests for app/utils/datetime_utils.py and the fecha_es / fechahora_es filters."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from markupsafe import Markup

from app.utils.datetime_utils import (
    LOCAL_TZ, MONTHS_ES, MONTHS_ES_SHORT, now_local, to_local_timezone,
    format_date_es, format_time_es, format_datetime_es,
)

EXPECTED_MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
EXPECTED_SHORT = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def test_month_tables():
    assert MONTHS_ES == EXPECTED_MONTHS
    assert MONTHS_ES_SHORT == EXPECTED_SHORT


def test_local_tz_name():
    assert LOCAL_TZ.key == 'America/Ciudad_Juarez'


@freeze_time('2026-07-31 12:00:00')
def test_now_local_is_aware_in_local_tz():
    now = now_local()
    assert now.tzinfo is not None
    assert now.tzinfo.key == 'America/Ciudad_Juarez'
    # 12:00 UTC -> 06:00 in Juarez (UTC-6 in summer)
    assert (now.hour, now.day) == (6, 31)


def test_to_local_timezone_naive_assumed_local():
    dt = to_local_timezone(datetime(2026, 1, 15, 10, 30))
    assert dt.tzinfo == LOCAL_TZ
    assert (dt.hour, dt.minute) == (10, 30)


def test_to_local_timezone_aware_converted():
    dt = to_local_timezone(datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc))
    assert dt.hour == 3 and dt.day == 15  # UTC-7 in winter


def test_to_local_timezone_crosses_day_boundary():
    dt = to_local_timezone(datetime(2026, 1, 15, 3, 0, tzinfo=timezone.utc))
    assert (dt.day, dt.hour) == (14, 20)


def test_to_local_timezone_other_zone():
    tokyo = datetime(2026, 1, 15, 9, 0, tzinfo=ZoneInfo('Asia/Tokyo'))
    assert to_local_timezone(tokyo).day == 14


@pytest.mark.parametrize('month', range(1, 13))
def test_format_date_all_months_long(month):
    assert format_date_es(date(2026, month, 5)) == f'5 de {EXPECTED_MONTHS[month - 1]} de 2026'


@pytest.mark.parametrize('month', range(1, 13))
def test_format_date_all_months_short(month):
    assert format_date_es(date(2026, month, 5), 'short') == f'5 {EXPECTED_SHORT[month - 1]} 2026'


def test_format_date_numeric_zero_padded():
    assert format_date_es(date(2026, 3, 4), 'numeric') == '04/03/2026'


def test_format_date_long_no_zero_pad():
    assert format_date_es(date(2026, 7, 1)) == '1 de julio de 2026'


def test_format_date_unknown_style_falls_back_to_long():
    assert format_date_es(date(2026, 7, 31), 'bogus') == '31 de julio de 2026'


@pytest.mark.parametrize('bad', [None, '', 'not a date', 123, [], {}])
def test_format_date_invalid_returns_empty(bad):
    assert format_date_es(bad) == ''


def test_format_date_iso_string():
    assert format_date_es('2026-07-31') == '31 de julio de 2026'


def test_format_date_iso_string_z_suffix_converted_to_local():
    # 03:00Z is still the previous day in Juarez
    assert format_date_es('2026-07-31T03:00:00Z') == '30 de julio de 2026'


def test_format_date_string_whitespace_stripped():
    assert format_date_es('  2026-07-31  ') == '31 de julio de 2026'


def test_format_date_utc_aware_never_renders_wrong_day():
    dt = datetime(2026, 12, 1, 2, 0, tzinfo=timezone.utc)
    assert format_date_es(dt, 'numeric') == '30/11/2026'


def test_format_date_naive_datetime_kept():
    assert format_date_es(datetime(2026, 12, 31, 23, 59), 'numeric') == '31/12/2026'


def test_format_date_leap_day():
    assert format_date_es(date(2028, 2, 29)) == '29 de febrero de 2028'


def test_format_time_basic():
    assert format_time_es(datetime(2026, 1, 1, 9, 5)) == '09:05'


def test_format_time_midnight_and_late():
    assert format_time_es(datetime(2026, 1, 1, 0, 0)) == '00:00'
    assert format_time_es(datetime(2026, 1, 1, 23, 59)) == '23:59'


def test_format_time_converts_to_local():
    assert format_time_es(datetime(2026, 1, 1, 18, 30, tzinfo=timezone.utc)) == "11:30"


def test_format_time_date_only_is_empty():
    assert format_time_es(date(2026, 1, 1)) == ''


@pytest.mark.parametrize('bad', [None, '', 'garbage'])
def test_format_time_invalid_empty(bad):
    assert format_time_es(bad) == ''


def test_format_time_iso_string():
    assert format_time_es('2026-01-01T14:30:00') == '14:30'


def test_format_datetime_long():
    out = format_datetime_es(datetime(2026, 7, 31, 14, 30))
    assert '31 de julio de 2026 a las 14:30' in out


def test_format_datetime_short():
    assert '31 jul 2026, 14:30' in format_datetime_es(datetime(2026, 7, 31, 14, 30), 'short')


def test_format_datetime_numeric():
    assert '31/07/2026 14:30' in format_datetime_es(datetime(2026, 7, 31, 14, 30), 'numeric')


def test_format_datetime_returns_markup_time_element():
    out = format_datetime_es(datetime(2026, 7, 31, 14, 30))
    assert isinstance(out, Markup)
    assert out.startswith('<time datetime="2026-07-31T14:30:00-06:00">')
    assert out.endswith('</time>')


def test_format_datetime_include_time_false():
    out = format_datetime_es(datetime(2026, 7, 31, 14, 30), include_time=False)
    assert out.endswith('>31 de julio de 2026</time>')
    assert 'a las' not in out


def test_format_datetime_date_only_value():
    out = format_datetime_es(date(2026, 7, 31))
    assert out == '<time datetime="2026-07-31">31 de julio de 2026</time>'


@pytest.mark.parametrize('bad', [None, '', 'zzz'])
def test_format_datetime_invalid_empty_markup(bad):
    out = format_datetime_es(bad)
    assert out == '' and isinstance(out, Markup)


def test_format_datetime_unknown_style_uses_long_date_text():
    out = format_datetime_es(datetime(2026, 7, 31, 14, 30), 'bogus')
    assert '31 de julio de 2026' in out and '14:30' in out


def test_filters_registered_and_render(app):
    tpl = app.jinja_env.from_string(
        "{{ d|fecha_es }}|{{ d|fecha_es('short') }}|{{ d|fecha_es('numeric') }}|"
        "{{ d|fechahora_es }}|{{ d|fechahora_es('numeric', False) }}|{{ n|fecha_es }}|[{{ n|fechahora_es }}]"
    )
    out = tpl.render(d=datetime(2026, 7, 31, 14, 30), n=None)
    parts = out.split('|')
    assert parts[0] == '31 de julio de 2026'
    assert parts[1] == '31 jul 2026'
    assert parts[2] == '31/07/2026'
    assert parts[3] == '<time datetime="2026-07-31T14:30:00-06:00">31 de julio de 2026 a las 14:30</time>'
    assert parts[4] == '<time datetime="2026-07-31T14:30:00-06:00">31/07/2026</time>'
    assert parts[5] == ''
    assert parts[6] == '[]'

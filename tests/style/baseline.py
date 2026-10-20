"""Accepted current violation counts per rule (ratchet).

Regenerate with:  python -m tests.style.baseline --write
Only regenerate after FIXING violations (counts drop); never to hide new ones.
"""

BASELINE = {
    'css_bounce_easing': {},
    'css_components_important': {},
    'css_gradient_text': {},
    # css_hardcoded_colors: total 4 in 2 files
    'css_hardcoded_colors': {
        'app/static/css/events/view.css': 1,
        'app/static/css/program/list.css': 3,
    },
    'css_keyframes_prefix': {},
    'css_thick_side_borders': {},
    'fa_classes': {},
    'htmx_inline_js': {},
    'js_alert': {},
    # js_console_log: total 5 in 3 files
    'js_console_log': {
        'app/static/js/admin/settings/academic_periods.js': 2,
        'app/static/js/admin/settings/celery_worker.js': 2,
        'app/static/js/force_password_change.js': 1,
    },
    # js_csrf_meta_reads: total 2 in 2 files
    'js_csrf_meta_reads': {
        'app/static/js/base.js': 1,
        'app/static/js/force_password_change.js': 1,
    },
    'js_mutation_without_csrf': {},
    'prefers_color_scheme': {},
    'py_db_in_routes': {},
    'py_deprecated_auth_import': {},
    'py_flash_not_spanish': {},
    # py_naive_now: total 1 in 1 files
    'py_naive_now': {
        'app/utils/datetime_utils.py': 1,
    },
    'py_print': {},
    'py_roles_required': {},
    # strftime_month_names: total 1 in 1 files
    'strftime_month_names': {
        'app/services/email_templates.py': 1,
    },
    'tpl_hardcoded_colors': {},
    'tpl_inline_style': {},
    'tpl_inline_svg': {},
    'tpl_style_block': {},
    'tpl_tables': {},
}


def _render(current: dict) -> str:
    lines = [
        '"""Accepted current violation counts per rule (ratchet).',
        '',
        'Regenerate with:  python -m tests.style.baseline --write',
        'Only regenerate after FIXING violations (counts drop); never to hide new ones.',
        '"""',
        '',
        'BASELINE = {',
    ]
    for rule in sorted(current):
        counts = current[rule]
        if not counts:
            lines.append(f'    {rule!r}: {{}},')
            continue
        lines.append(f'    # {rule}: total {sum(counts.values())} in {len(counts)} files')
        lines.append(f'    {rule!r}: {{')
        lines.extend(f'        {path!r}: {n},' for path, n in sorted(counts.items()))
        lines.append('    },')
    lines.append('}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    import sys
    from pathlib import Path

    from tests.style.rules import RULES

    if '--write' not in sys.argv:
        sys.exit('uso: python -m tests.style.baseline --write')
    current = {rule: dict(fn()) for rule, fn in RULES.items()}
    source = Path(__file__).read_text(encoding='utf-8')
    tail = source[source.index('\n\ndef _render'):]
    Path(__file__).write_text(_render(current) + tail, encoding='utf-8')
    for rule in sorted(current):
        total = sum(current[rule].values())
        if total:
            print(f'{rule}: {total}')

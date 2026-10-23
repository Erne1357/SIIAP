"""
Ratchet: `UserProgram.academic_status` is only ever assigned inside
`app/services/academic_status_service.py` (via `transition()`).

Constructor kwargs (`UserProgram(..., academic_status='graduated')`) and
comparisons are fine; attribute assignment, `setattr(x, 'academic_status', ...)`
and `.update({... 'academic_status' ...})` on one line are flagged.
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / 'app'
ALLOWED = {APP_DIR / 'services' / 'academic_status_service.py'}
ASSIGNMENT = re.compile(r'\.academic_status\s*=(?!=)')
SETATTR = re.compile(r'''setattr\(\s*[^,]+,\s*['"]academic_status['"]''')
BULK_UPDATE = re.compile(r'''\.update\(.*['"]academic_status['"]''')
WRITE_PATTERNS = (ASSIGNMENT, SETATTR, BULK_UPDATE)


def _is_status_write(code: str) -> bool:
    return any(p.search(code) for p in WRITE_PATTERNS)


def _offenders():
    found = []
    for path in sorted(APP_DIR.rglob('*.py')):
        if path in ALLOWED:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for lineno, line in enumerate(text.splitlines(), start=1):
            code = line.split('#', 1)[0]
            if _is_status_write(code):
                found.append(f'{path.relative_to(APP_DIR.parent).as_posix()}:{lineno}: {line.strip()}')
    return found


def test_academic_status_is_only_written_by_the_state_machine():
    offenders = _offenders()
    assert not offenders, (
        'Direct write of `academic_status`; use '
        'academic_status_service.transition():\n' + '\n'.join(offenders)
    )


def test_write_patterns_match_the_bypasses_and_spare_reads():
    flagged = [
        "up.academic_status = 'graduated'",
        "setattr(up, 'academic_status', 'graduated')",
        'setattr(obj, "academic_status", value)',
        "UserProgram.query.filter_by(id=1).update({'academic_status': 'withdrawn'})",
        'row.update(dict(a=1, **{"academic_status": s}))',
    ]
    spared = [
        "if up.academic_status == 'graduated':",
        "UserProgram(user_id=1, academic_status='graduated')",
        "getattr(up, 'academic_status')",
        "up.update({'name': 'x'})",
        "filter_by(academic_status='graduated')",
    ]
    assert all(_is_status_write(c) for c in flagged)
    assert not any(_is_status_write(c) for c in spared)

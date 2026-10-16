"""Ratchet tests: no new violations, and baseline must shrink when fixes land."""

import pytest

from tests.style.baseline import BASELINE
from tests.style.rules import RULES

pytestmark = pytest.mark.style


@pytest.mark.parametrize("rule", sorted(RULES))
def test_rule_ratchet(rule):
    current = RULES[rule]()
    expected = BASELINE.get(rule, {})
    problems = []
    for path, n in sorted(current.items()):
        allowed = expected.get(path, 0)
        if n > allowed:
            problems.append(f"NEW  {path}: {n} violations (baseline {allowed})")
    for path, allowed in sorted(expected.items()):
        n = current.get(path, 0)
        if n < allowed:
            problems.append(
                f"FIXED {path}: now {n}, baseline {allowed} -> update baseline "
                f"(python -m tests.style.baseline --write)"
            )
    assert not problems, f"{rule}: {RULES[rule].__doc__}\n" + "\n".join(problems)

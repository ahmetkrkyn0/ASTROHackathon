"""Run the two standalone check-harness suites under pytest.

``test_cost_engine.py`` and ``test_traversability.py`` predate the pytest
suite: they use their own ``check()`` counter and end in ``sys.exit(1)``
rather than ``def test_*`` + ``assert``. pytest.ini therefore --ignore'd
both, which meant 65 real assertions ran only when somebody remembered to
type ``python test_cost_engine.py`` by hand. With no CI either, that was
nobody. (Backend review, #18.)

Rewriting them into pytest style would churn 65 working assertions for no
behavioural gain, so instead each is executed as a subprocess and its exit
code asserted -- the same contract the files already publish. Their output
is attached to the failure so a red run still names the failing check.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent

_HARNESS_SUITES = ("test_cost_engine.py", "test_traversability.py")


@pytest.mark.parametrize("script", _HARNESS_SUITES)
def test_standalone_harness_suite_passes(script: str) -> None:
    result = subprocess.run(
        [sys.executable, script],
        cwd=_BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"{script} reported failures:\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

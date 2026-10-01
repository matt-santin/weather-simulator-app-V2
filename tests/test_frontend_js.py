"""The JavaScript suite, run by the same command as everything else.

``./venv/bin/python -m pytest`` covers the whole project, front included, and
the project still does not depend on Node: no package.json, no install, no build
step, and this skips when ``node`` is not on the machine. Node is a test runner
here and nothing more — the pages themselves are read by the browser exactly as
they are written.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def test_javascript_suite() -> None:
    """``node --test`` over tests/js/, its output shown when it fails."""
    result = subprocess.run(
        ["node", "--test", "tests/js/**/*.test.js"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

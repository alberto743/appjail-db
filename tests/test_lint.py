# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("ruff"), reason="ruff is not installed (pip install .[test])")
def test_ruff_is_clean():
    """No unused or undefined names, no shadowed imports (pyflakes rules included), unsorted imports or other
    findings of the rule set in pyproject.toml."""
    proc = subprocess.run(["ruff", "check", "--no-cache", "src", "tests"], cwd=ROOT,
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr

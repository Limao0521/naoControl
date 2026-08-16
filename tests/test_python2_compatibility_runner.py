from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compatibility_report_renders_on_windows_console() -> None:
    environment = dict(os.environ, PYTHONIOENCODING="cp1252")
    result = subprocess.run(
        [sys.executable, "nao/scripts/test_python2_compatibility.py"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="cp1252",
    )

    assert "UnicodeEncodeError" not in result.stderr
    if "RESULTADOS: 3/3" in result.stdout:
        assert result.returncode == 0
    else:
        assert result.returncode == 1

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_SCRIPT = ROOT / "tools" / "launcher-task-settings.ps1"


def test_launcher_task_survives_battery_changes_and_restarts_after_failure():
    command = (
        f". '{SETTINGS_SCRIPT}'; "
        "$settings = New-NaoLauncherTaskSettings; "
        "[pscustomobject]@{"
        "DisallowStartIfOnBatteries=$settings.DisallowStartIfOnBatteries;"
        "StopIfGoingOnBatteries=$settings.StopIfGoingOnBatteries;"
        "RestartCount=$settings.RestartCount;"
        "StartWhenAvailable=$settings.StartWhenAvailable"
        "} | ConvertTo-Json -Compress"
    )

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "DisallowStartIfOnBatteries": False,
        "StopIfGoingOnBatteries": False,
        "RestartCount": 999,
        "StartWhenAvailable": True,
    }

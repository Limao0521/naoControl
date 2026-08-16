from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(
    b"(?:"
    + b"gsk" + b"_[A-Za-z0-9_-]{12,}|"
    + b"AI" + b"za[A-Za-z0-9_-]{20,}|"
    + b"nv" + b"api-[A-Za-z0-9_-]{12,}|"
    + b"CERT" + b"_NONE)"
)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=REPOSITORY_ROOT
    )
    return [REPOSITORY_ROOT / name.decode("utf-8") for name in output.split(b"\0") if name]


def test_tracked_files_do_not_contain_cloud_secrets_or_tls_bypasses() -> None:
    findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() in {".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".wav"}:
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if FORBIDDEN.search(line):
                findings.append(f"{path.relative_to(REPOSITORY_ROOT)}:{line_number}")

    assert findings == [], "Sensitive patterns found at: " + ", ".join(findings)

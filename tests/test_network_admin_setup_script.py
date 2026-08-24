from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "setup-nao-network-admin.ps1"


def run_pwsh(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_setup_rejects_shell_syntax_in_nao_ip(tmp_path) -> None:
    result = run_pwsh(
        [
            "-NaoIp",
            "169.254.1.2;whoami",
            "-KeyPath",
            str(tmp_path / "nao_key"),
            "-EnvFile",
            str(tmp_path / ".env"),
        ]
    )

    assert result.returncode != 0
    assert not (tmp_path / "nao_key").exists()
    assert not (tmp_path / ".env").exists()


def test_setup_writes_only_safe_broker_values_after_key_verification(tmp_path) -> None:
    key_path = tmp_path / "nao_key"
    key_path.write_text("private-placeholder", encoding="utf-8")
    key_path.with_suffix(".pub").write_text(
        "ssh-ed25519 AAAATEST naoControl-test\n", encoding="utf-8"
    )
    env_file = tmp_path / ".env"
    env_file.write_text("NVIDIA_API_KEY=keep-existing\n", encoding="utf-8")
    fake_ssh = tmp_path / "ssh-ok.ps1"
    fake_ssh.write_text(
        "$input | Out-Null\n"
        "return\n",
        encoding="utf-8",
    )

    result = run_pwsh(
        [
            "-NaoIp",
            "169.254.1.2",
            "-KeyPath",
            str(key_path),
            "-EnvFile",
            str(env_file),
            "-SshCommand",
            str(fake_ssh),
        ]
    )

    assert result.returncode == 0, result.stderr + result.stdout
    configured = env_file.read_text(encoding="utf-8")
    assert "NVIDIA_API_KEY=keep-existing" in configured
    assert "NAO_NETWORK_BROKER_ENABLED=true" in configured
    assert f"NAO_SSH_KEY={key_path.resolve()}" in configured
    assert "NAO_NETWORK_ALLOWED_ORIGINS=http://169.254.1.2:3000" in configured
    assert "private-placeholder" not in configured

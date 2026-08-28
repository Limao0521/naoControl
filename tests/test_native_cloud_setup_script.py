from pathlib import Path


SCRIPT = Path("tools/configure-nao-nemotron.ps1")


def test_setup_stores_secret_only_on_robot_and_never_echoes_it():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "Read-Host 'Pega la NVIDIA API key (no se mostrará)' -AsSecureString" in content
    assert "/home/nao/naoControl/config/nvidia_api_key" in content
    assert "chmod 600" in content
    assert "Write-Host $apiKey" not in content
    assert "ZeroFreeBSTR" in content


def test_setup_can_reuse_existing_ignored_pc_env_once():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "naoControlGatewayHost\\.env" in content
    assert "NVIDIA_API_KEY" in content
    assert "test -s /home/nao/naoControl/config/nvidia_api_key" in content

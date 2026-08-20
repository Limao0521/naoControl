from pathlib import Path


SCRIPT = Path("tools/deploy-nao.ps1")


def test_deploy_script_preserves_robot_secret_without_transferring_pc_env():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "robot_gateway.secret" in content
    assert ".env" in content
    assert "autoload.ini" not in content
    assert 'for service in control web camera intelligence' in content
    assert 'stop_nemotron.sh' not in content


def test_deploy_script_validates_nemotron_runtime_before_success():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "gateway_server.py" in content
    assert "python -m py_compile" in content
    assert "start_nemotron.sh" in content

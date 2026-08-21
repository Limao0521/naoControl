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


def test_deploy_script_does_not_apply_windows_archive_permissions_on_nao():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "--no-same-owner" in content
    assert "--no-same-permissions" in content
    assert "--mode=u+rwX,go+rX,go-w" in content

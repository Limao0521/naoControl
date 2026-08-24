from pathlib import Path
import tarfile


SCRIPT = Path("tools/deploy-nao.ps1")
PACKAGER = Path("tools/package_nao.py")


def test_deploy_script_preserves_robot_secret_without_transferring_pc_env():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "robot_gateway.secret" in content
    assert ".env" in PACKAGER.read_text(encoding="utf-8")
    assert "autoload.ini" not in content
    assert 'for service in control web camera intelligence' in content
    assert 'stop_nemotron.sh' not in content


def test_deploy_script_validates_nemotron_runtime_before_success():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "gateway_server.py" in content
    assert "python -m py_compile" in content
    assert "start_nemotron.sh" in content
    assert '"$base/nao/scripts/runtime/network_admin.py"' in content


def test_deploy_script_does_not_apply_windows_archive_permissions_on_nao():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "package_nao.py" in content
    assert ".venv\\Scripts\\python.exe" in content


def test_deploy_script_uses_nao_shell_compatible_argument_passing():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "sh -s --" not in content
    assert "| sh -s '$remoteArchive' '$startFlag'" in content


def test_deploy_script_normalizes_remote_script_to_unix_line_endings():
    content = SCRIPT.read_text(encoding="utf-8")

    assert '$remoteScript = $remoteScript.Replace("`r`n", "`n")' in content


def test_nao_archive_builder_writes_writable_directories(tmp_path):
    from tools.package_nao import build_archive

    archive = tmp_path / "naoControl.tar.gz"
    build_archive(Path(".").resolve(), archive)

    with tarfile.open(archive, "r:gz") as contents:
        runtime = contents.getmember("nao/scripts/runtime")
        assert runtime.isdir()
        assert runtime.mode & 0o200
        assert contents.getmember("config/action_registry.json").mode == 0o644
        assert "config/robot_gateway.secret" not in contents.getnames()
        assert "nao/scripts/runtime/network_admin.py" in contents.getnames()

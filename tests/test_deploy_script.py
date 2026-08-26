from pathlib import Path
import tarfile


SCRIPT = Path("tools/deploy-nao.ps1")
PACKAGER = Path("tools/package_nao.py")


def test_deploy_script_preserves_robot_secret_without_transferring_pc_env():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "robot_gateway.secret" in content
    assert ".env" in PACKAGER.read_text(encoding="utf-8")
    assert "autoload.ini" not in content
    assert 'for service in control web camera pc_bundle intelligence' in content
    assert 'stop_nemotron.sh' not in content


def test_deploy_script_validates_nemotron_runtime_before_success():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "gateway_server.py" in content
    assert "python -m py_compile" in content
    assert "start_nemotron.sh" in content
    assert '"$base/nao/scripts/runtime/network_admin.py"' in content
    assert '"$base/nao/scripts/runtime/control_server/message_security.py"' in content
    assert '"$base/nao/scripts/runtime/control_server/commands/network_commands.py"' in content
    assert '"$base/nao/scripts/runtime/intelligence/pc_gateway_launch.py"' in content
    assert '"$base/nao/scripts/runtime/interaction_state.py"' in content
    assert '"$base/nao/scripts/runtime/control_server/commands/nemotron_commands.py"' in content
    assert '"$base/nao/scripts/runtime/intelligence/provider_config.py"' in content
    assert '"$base/nao/scripts/runtime/intelligence/led_controller.py"' in content


def test_deploy_preserves_the_configured_pc_gateway_target():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "pc_gateway_target.json" in content
    assert 'cp "$base/config/pc_gateway_target.json"' in content


def test_deploy_preserves_the_selected_intelligence_provider():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "intelligence_provider.json" in content
    assert 'cp "$base/config/intelligence_provider.json"' in content


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
        assert "pc_gateway/src/nao_gateway/launcher_service.py" in contents.getnames()


def test_start_script_builds_and_serves_the_pc_gateway_bundle():
    content = Path("nao/scripts/runtime/start_nemotron.sh").read_text(encoding="utf-8")

    assert "pc_gateway_bundle.tar.gz" in content
    assert "pc_gateway config/action_registry.json" in content
    assert "config/behavior_registry.json" in content
    assert "SimpleHTTPServer 6677" in content
    assert "start_service pc_bundle" in content


def test_start_script_rebuilds_bundle_atomically_on_every_start():
    content = Path("nao/scripts/runtime/start_nemotron.sh").read_text(encoding="utf-8")

    assert "if [ ! -f \"$BUNDLE_DIR/pc_gateway_bundle.tar.gz\" ]" not in content
    assert "mktemp \"$BUNDLE_DIR/pc_gateway_bundle.tar.gz.tmp.XXXXXX\"" in content
    assert "mv \"$bundle_tmp\" \"$BUNDLE_DIR/pc_gateway_bundle.tar.gz\"" in content


def test_setup_script_registers_the_authenticated_launcher_without_copying_secrets():
    content = Path("tools/setup-nemotron-pc-host.ps1").read_text(encoding="utf-8")

    assert "NaoControlNemotronLauncher" in content
    assert "robot_gateway.secret" in content
    assert "scp.exe" in content
    assert "Write-Host $robotSecret" not in content
    assert "New-NetFirewallRule" in content
    assert "nao_gateway.launcher_service" in content
    assert "New-ScheduledTaskPrincipal" in content
    assert "RunLevel  = 'Limited'" in content
    assert "RemoteAddress = $NaoIp" in content
    assert "StrictHostKeyChecking=yes" in content


def test_setup_script_resolves_repo_root_after_parameter_binding():
    content = Path("tools/setup-nemotron-pc-host.ps1").read_text(encoding="utf-8")
    param_block = content.split(")\n\n$ErrorActionPreference", 1)[0]

    assert "$PSScriptRoot" not in param_block
    assert "if ([string]::IsNullOrWhiteSpace($RepoRoot))" in content
    assert "Join-Path $PSScriptRoot '..'" in content

from __future__ import annotations

import io
import json
import tarfile

import pytest

from nao_gateway.launcher_service import (
    BundleError,
    GatewayRuntime,
    LauncherCoordinator,
    _pid_is_running,
)
from nao_gateway.protocol import ReplayGuard, sign_envelope, verify_envelope


def bundle_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def signed_start(secret: bytes, digest: str) -> dict:
    return sign_envelope({
        "protocol_version": 1,
        "message_type": "gateway_start",
        "message_id": "launch-1",
        "issued_at_ms": 1000,
        "expires_at_ms": 5000,
        "payload": {
            "bundle_name": "pc_gateway_bundle.tar.gz",
            "bundle_sha256": digest,
        },
    }, secret)


def test_runtime_rejects_archive_path_traversal(tmp_path):
    malicious = bundle_bytes({"../outside.txt": b"no"})
    runtime = GatewayRuntime(tmp_path, bundle_fetcher=lambda *_: malicious)

    with pytest.raises(BundleError, match="unsafe bundle member"):
        runtime.install_and_start(
            "192.168.10.40", "pc_gateway_bundle.tar.gz",
            __import__("hashlib").sha256(malicious).hexdigest(),
        )
    assert not (tmp_path.parent / "outside.txt").exists()


def test_coordinator_derives_bundle_source_and_robot_url_from_client_ip(tmp_path):
    content = bundle_bytes({
        "pc_gateway/src/nao_gateway/__init__.py": b"",
        "config/action_registry.json": b"{}",
    })
    digest = __import__("hashlib").sha256(content).hexdigest()
    fetched = []
    processes = []
    (tmp_path / ".env").write_text("NVIDIA_API_KEY=local-only\n", encoding="utf-8")

    def fetch(url, maximum):
        fetched.append((url, maximum))
        return content

    def start_process(args, **kwargs):
        processes.append((args, kwargs))
        return type("Process", (), {"pid": 4321})()

    runtime = GatewayRuntime(
        tmp_path,
        bundle_fetcher=fetch,
        process_factory=start_process,
        python_executable="C:/Python/python.exe",
    )
    coordinator = LauncherCoordinator(b"x" * 32, runtime, now_ms=lambda: 1000)

    result = coordinator.handle(signed_start(b"x" * 32, digest), "192.168.10.40")

    assert result == {"status": "ready", "pid": 4321}
    assert fetched == [(
        "http://192.168.10.40:6677/pc_gateway_bundle.tar.gz",
        GatewayRuntime.MAX_BUNDLE_BYTES,
    )]
    args, options = processes[0]
    assert args[:3] == ["C:/Python/python.exe", "-u", "-m"]
    assert options["env"]["NAO_GATEWAY_URL"] == "ws://192.168.10.40:6674"
    assert options["env"]["PYTHONPATH"].endswith("pc_gateway\\src")
    assert "NVIDIA_API_KEY" not in json.dumps(result)

    response = coordinator.response("launch-1", result)
    verified = verify_envelope(response, b"x" * 32, 1000, ReplayGuard(10))
    assert verified == {"request_id": "launch-1", "status": "ready", "pid": 4321}


def test_coordinator_rejects_unsigned_or_wrong_message_without_fetching(tmp_path):
    fetched = []
    runtime = GatewayRuntime(tmp_path, bundle_fetcher=lambda *args: fetched.append(args))
    coordinator = LauncherCoordinator(b"x" * 32, runtime, now_ms=lambda: 1000)

    with pytest.raises(Exception):
        coordinator.handle({"message_type": "gateway_start"}, "192.168.10.40")
    assert fetched == []


def test_windows_pid_probe_never_uses_os_kill(monkeypatch):
    import nao_gateway.launcher_service as launcher_module

    monkeypatch.setattr(launcher_module.os, "name", "nt")
    monkeypatch.setattr(
        launcher_module.os,
        "kill",
        lambda *_: (_ for _ in ()).throw(AssertionError("os.kill must not run on Windows")),
    )

    assert _pid_is_running(99999999) is False


def test_runtime_does_not_report_ready_when_gateway_exits_during_startup(tmp_path):
    content = bundle_bytes({
        "pc_gateway/src/nao_gateway/__init__.py": b"",
        "config/action_registry.json": b"{}",
    })
    digest = __import__("hashlib").sha256(content).hexdigest()
    (tmp_path / ".env").write_text("configured=true\n", encoding="utf-8")

    class FailedProcess:
        pid = 4321

        def poll(self):
            return 1

    runtime = GatewayRuntime(
        tmp_path,
        bundle_fetcher=lambda *_: content,
        process_factory=lambda *args, **kwargs: FailedProcess(),
        startup_sleep=lambda *_: None,
    )

    with pytest.raises(BundleError, match="gateway process exited during startup"):
        runtime.install_and_start(
            "192.168.10.40", "pc_gateway_bundle.tar.gz", digest
        )
    assert not (tmp_path / "gateway.pid").exists()

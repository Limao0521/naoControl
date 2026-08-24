from __future__ import annotations

import json

import pytest

from nao.scripts.runtime.intelligence.pc_gateway_launch import (
    GatewayEntryGate,
    GatewayLaunchError,
    GatewayTargetStore,
    RemoteGatewayLauncher,
)
from nao.scripts.runtime.intelligence.protocol import (
    ReplayGuard,
    sign_envelope,
    verify_envelope,
)


def test_target_store_persists_only_a_valid_ipv4_address(tmp_path):
    path = tmp_path / "pc_gateway_target.json"
    store = GatewayTargetStore(str(path))

    assert store.load() == {"pc_ip": ""}
    assert store.save("192.168.10.25") == {"pc_ip": "192.168.10.25"}
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "pc_ip": "192.168.10.25"
    }

    with pytest.raises(GatewayLaunchError):
        store.save("192.168.10.25; powershell")


def test_remote_launcher_sends_a_signed_bounded_start_request(tmp_path):
    store = GatewayTargetStore(str(tmp_path / "target.json"))
    store.save("192.168.10.25")
    requests = []

    def transport(url, body, timeout):
        requests.append((url, body, timeout))
        request = json.loads(body)
        return sign_envelope({
            "protocol_version": 1,
            "message_type": "gateway_start_result",
            "message_id": "result-1",
            "issued_at_ms": 1000,
            "expires_at_ms": 31000,
            "payload": {
                "request_id": request["message_id"],
                "status": "ready",
                "pid": 4321,
            },
        }, b"x" * 32)

    launcher = RemoteGatewayLauncher(
        store,
        b"x" * 32,
        bundle_path=str(tmp_path / "pc_gateway_bundle.tar.gz"),
        transport=transport,
        now_ms=lambda: 1000,
    )
    (tmp_path / "pc_gateway_bundle.tar.gz").write_bytes(b"gateway bundle")

    result = launcher.start()

    assert result == {"status": "ready", "pid": 4321}
    assert requests[0][0] == "http://192.168.10.25:6676/start"
    assert requests[0][2] == 20
    envelope = json.loads(requests[0][1])
    payload = verify_envelope(envelope, b"x" * 32, 1000, ReplayGuard(10))
    assert payload["bundle_sha256"]
    assert payload["bundle_name"] == "pc_gateway_bundle.tar.gz"
    assert set(payload) == {"bundle_name", "bundle_sha256"}


def test_remote_launcher_rejects_an_unsigned_pc_response(tmp_path):
    store = GatewayTargetStore(str(tmp_path / "target.json"))
    store.save("192.168.10.25")
    bundle = tmp_path / "bundle.tar.gz"
    bundle.write_bytes(b"bundle")
    launcher = RemoteGatewayLauncher(
        store,
        b"x" * 32,
        bundle_path=str(bundle),
        transport=lambda *_: {"status": "ready", "pid": 5},
        now_ms=lambda: 1000,
    )

    with pytest.raises(Exception):
        launcher.start()


def test_remote_launcher_rejects_missing_target_without_network_call(tmp_path):
    calls = []
    launcher = RemoteGatewayLauncher(
        GatewayTargetStore(str(tmp_path / "target.json")),
        b"x" * 32,
        bundle_path=str(tmp_path / "bundle.tar.gz"),
        transport=lambda *args: calls.append(args),
    )

    with pytest.raises(GatewayLaunchError, match="pc target is not configured"):
        launcher.start()
    assert calls == []


def test_entry_gate_starts_pc_gateway_only_after_robot_safety_allows_entry():
    calls = []

    class Safety:
        def check_intelligent_entry(self):
            return True, []

    class Launcher:
        def start(self):
            calls.append("start")
            return {"status": "ready"}

    gate = GatewayEntryGate(Safety(), Launcher())

    assert gate() is True
    assert calls == ["start"]
    assert gate.last_reason == "ready"


def test_entry_gate_does_not_contact_pc_when_robot_safety_rejects():
    calls = []

    class Safety:
        def check_intelligent_entry(self):
            return False, ["robot_not_ready"]

    class Launcher:
        def start(self):
            calls.append("start")

    gate = GatewayEntryGate(Safety(), Launcher())

    assert gate() is False
    assert calls == []
    assert gate.last_reason == "robot_not_ready"

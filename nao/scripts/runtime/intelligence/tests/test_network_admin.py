from __future__ import annotations

import json
from io import StringIO

import pytest

from nao.scripts.runtime.network_admin import (
    ConnectionManagerAdapter,
    JsonAuditLog,
    NaoNotifier,
    NetworkAdminService,
    RearTactileGate,
    build_robot_service,
    main,
    process_stream,
)
from nao.scripts.runtime.intelligence.pc_gateway_launch import GatewayTargetStore


class FakeClock:
    def __init__(self, step: float = 0.25) -> None:
        self.value = 0.0
        self.step = step

    def time(self) -> float:
        return self.value

    def sleep(self, _seconds: float) -> None:
        self.value += self.step


class FakeConnectionManager:
    def __init__(self) -> None:
        self.calls = []
        self.on_connect = None
        self.networks = [
            {
                "ServiceId": "wifi_lab",
                "Name": "Laboratorio",
                "Type": "wifi",
                "State": "idle",
                "Strength": 72,
                "Security": ["psk"],
                "Favorite": True,
                "Passphrase": "must-not-leak",
            }
        ]

    def state(self):
        self.calls.append(("state",))
        return "ready"

    def interfaces(self):
        self.calls.append(("interfaces",))
        return [{"Name": "eth0", "Address": "169.254.1.2"}]

    def scan(self):
        self.calls.append(("scan",))

    def services(self):
        self.calls.append(("services",))
        return list(self.networks)

    def provisionedServices(self):
        self.calls.append(("provisionedServices",))
        return list(self.networks)

    def connect(self, service_id):
        self.calls.append(("connect", service_id))
        if self.on_connect:
            self.on_connect(service_id)

    def setServiceInput(self, reply):
        self.calls.append(("setServiceInput", reply))

    def disconnect(self, service_id):
        self.calls.append(("disconnect", service_id))

    def forget(self, service_id):
        self.calls.append(("forget", service_id))

    def service(self, service_id):
        self.calls.append(("service", service_id))
        return dict(self.networks[0], State="ready")


class FailingDisconnectManager(FakeConnectionManager):
    def disconnect(self, service_id):
        raise RuntimeError("backend failed with example-only")


class AcceptingGate:
    def wait_for_hold(self, timeout_seconds):
        return True


class RejectingGate:
    def wait_for_hold(self, timeout_seconds):
        return False


class FakeSignal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback):
        self.callback = callback
        return 7

    def disconnect(self, connection_id):
        assert connection_id == 7
        self.callback = None

    def emit(self, value):
        assert self.callback is not None
        self.callback(value)


class FakeMemory:
    def __init__(self) -> None:
        self.signal = FakeSignal()

    def subscriber(self, event_name):
        assert event_name == "NetworkServiceInputRequired"
        return type("Subscriber", (), {"signal": self.signal})()

    def getData(self, key):
        assert key == "RearTactilTouched"
        return 1.0


class RecordingNotifier:
    def __init__(self) -> None:
        self.calls = []

    def pending(self, operation):
        self.calls.append(("pending", operation))

    def completed(self, operation):
        self.calls.append(("completed", operation))

    def rejected(self, operation):
        self.calls.append(("rejected", operation))


class RecordingAudit:
    def __init__(self) -> None:
        self.events = []

    def write(self, event):
        self.events.append(event)


class FakeSession:
    def __init__(self, services) -> None:
        self.services = services
        self.requests = []
        self.connections = []

    def connect(self, url):
        self.connections.append(url)

    def service(self, name):
        self.requests.append(name)
        return self.services[name]


class FakePostTts:
    def __init__(self) -> None:
        self.calls = []
        self.post = self

    def say(self, text):
        self.calls.append(text)


class FakeLeds:
    def __init__(self) -> None:
        self.calls = []

    def fadeRGB(self, group, color, duration):
        self.calls.append((group, color, duration))


def test_releasing_rear_sensor_resets_hold_timer() -> None:
    readings = iter([1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0])
    clock = FakeClock(step=1.0)
    gate = RearTactileGate(
        lambda: next(readings),
        clock.time,
        clock.sleep,
        hold_seconds=3.0,
        poll_seconds=1.0,
    )

    assert gate.wait_for_hold(timeout_seconds=10.0) is True
    assert clock.time() >= 6.0


def test_rear_sensor_timeout_does_not_accept_partial_holds() -> None:
    clock = FakeClock(step=1.0)
    gate = RearTactileGate(
        lambda: 0.0,
        clock.time,
        clock.sleep,
        hold_seconds=3.0,
        poll_seconds=1.0,
    )

    assert gate.wait_for_hold(timeout_seconds=4.0) is False


def test_disconnect_requires_confirmation_before_state_change() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), RejectingGate())

    result = service.execute({"operation": "disconnect", "service_id": "wifi_lab"})

    assert result["status"] == "confirmation_timeout"
    assert manager.calls == []


def test_confirmed_disconnect_calls_allowlisted_manager_method() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), AcceptingGate())

    result = service.execute({"operation": "disconnect", "service_id": "wifi_lab"})

    assert result == {
        "status": "completed",
        "operation": "disconnect",
        "data": {"service_id": "wifi_lab"},
    }
    assert manager.calls == [("disconnect", "wifi_lab")]


def test_mutation_audits_pending_and_completion_without_passphrase() -> None:
    manager = FakeConnectionManager()
    notifier = RecordingNotifier()
    audit = RecordingAudit()
    service = NetworkAdminService(
        ConnectionManagerAdapter(manager),
        AcceptingGate(),
        notifier=notifier,
        audit_log=audit,
    )

    result = service.execute(
        {
            "operation": "connect",
            "service_id": "wifi_lab",
            "passphrase": "example-only",
        }
    )

    assert result["status"] == "completed"
    assert notifier.calls == [("pending", "connect"), ("completed", "connect")]
    assert audit.events == [
        {"operation": "connect", "status": "pending_confirmation"},
        {"operation": "connect", "status": "completed"},
    ]
    assert "example-only" not in json.dumps(audit.events)


def test_confirmation_timeout_is_audited_and_announced() -> None:
    notifier = RecordingNotifier()
    audit = RecordingAudit()
    service = NetworkAdminService(
        ConnectionManagerAdapter(FakeConnectionManager()),
        RejectingGate(),
        notifier=notifier,
        audit_log=audit,
    )

    result = service.execute({"operation": "forget", "service_id": "wifi_lab"})

    assert result["status"] == "confirmation_timeout"
    assert notifier.calls == [("pending", "forget"), ("rejected", "forget")]
    assert audit.events[-1] == {
        "operation": "forget",
        "status": "confirmation_timeout",
    }


def test_scan_returns_only_allowlisted_network_fields() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), RejectingGate())

    result = service.execute({"operation": "scan"})

    assert result["status"] == "completed"
    assert result["data"]["services"] == [
        {
            "ServiceId": "wifi_lab",
            "Name": "Laboratorio",
            "Type": "wifi",
            "State": "idle",
            "Strength": 72,
            "Security": ["psk"],
            "Favorite": True,
        }
    ]
    assert "Passphrase" not in json.dumps(result)


def test_status_reports_interfaces_without_credentials() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), RejectingGate())

    result = service.execute({"operation": "status"})

    assert result == {
        "status": "completed",
        "operation": "status",
        "data": {
            "state": "ready",
            "interfaces": [{"Name": "eth0", "Address": "169.254.1.2"}],
            "services": [
                {
                    "ServiceId": "wifi_lab",
                    "Name": "Laboratorio",
                    "Type": "wifi",
                    "State": "idle",
                    "Strength": 72,
                    "Security": ["psk"],
                    "Favorite": True,
                }
            ],
        },
    }


def test_profiles_returns_provisioned_services_without_passphrases() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), RejectingGate())

    result = service.execute({"operation": "profiles"})

    assert result["status"] == "completed"
    assert result["data"]["profiles"][0]["ServiceId"] == "wifi_lab"
    assert "must-not-leak" not in json.dumps(result)


def test_confirmed_forget_calls_allowlisted_manager_method() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), AcceptingGate())

    result = service.execute({"operation": "forget", "service_id": "wifi_lab"})

    assert result["status"] == "completed"
    assert manager.calls == [("forget", "wifi_lab")]


def test_connect_supplies_requested_passphrase_and_redacts_result() -> None:
    manager = FakeConnectionManager()
    memory = FakeMemory()
    manager.on_connect = lambda service_id: memory.signal.emit(
        [
            ["ServiceId", service_id],
            ["Passphrase", [["Requirement", "Mandatory"], ["Type", "psk"]]],
        ]
    )
    service = NetworkAdminService(
        ConnectionManagerAdapter(manager, memory=memory), AcceptingGate()
    )

    result = service.execute(
        {
            "operation": "connect",
            "service_id": "wifi_lab",
            "ssid": "Laboratorio",
            "passphrase": "example-only",
        }
    )

    assert result["status"] == "completed"
    assert manager.calls == [
        ("connect", "wifi_lab"),
        (
            "setServiceInput",
            [["ServiceId", "wifi_lab"], ["Passphrase", "example-only"]],
        ),
        ("service", "wifi_lab"),
    ]
    assert "example-only" not in json.dumps(result)


def test_service_rejects_unknown_fields_before_manager_call() -> None:
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), AcceptingGate())

    try:
        service.execute({"operation": "status", "command": "id"})
    except ValueError as error:
        assert str(error) == "unknown fields"
    else:
        raise AssertionError("unknown fields were accepted")
    assert manager.calls == []


def test_process_stream_rejects_oversized_json_without_echoing_it() -> None:
    source = StringIO("x" * 8193)
    target = StringIO()
    service = NetworkAdminService(ConnectionManagerAdapter(FakeConnectionManager()), RejectingGate())

    exit_code = process_stream(source, target, service)

    assert exit_code == 2
    assert json.loads(target.getvalue()) == {
        "status": "rejected",
        "operation": "unknown",
        "data": {},
        "reason": "request_too_large",
    }


def test_process_stream_rejects_unknown_operation_without_manager_calls() -> None:
    manager = FakeConnectionManager()
    source = StringIO('{"operation":"shell","command":"id"}')
    target = StringIO()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), RejectingGate())

    exit_code = process_stream(source, target, service)

    assert exit_code == 2
    assert json.loads(target.getvalue())["reason"] == "invalid_request"
    assert manager.calls == []


def test_invalid_stream_response_does_not_echo_passphrase() -> None:
    source = StringIO(
        '{"operation":"shell","passphrase":"example-only","command":"id"}'
    )
    target = StringIO()
    service = NetworkAdminService(ConnectionManagerAdapter(FakeConnectionManager()), RejectingGate())

    process_stream(source, target, service)

    assert "example-only" not in target.getvalue()


def test_backend_failure_is_redacted_audited_and_returned_as_failed() -> None:
    notifier = RecordingNotifier()
    audit = RecordingAudit()
    service = NetworkAdminService(
        ConnectionManagerAdapter(FailingDisconnectManager()),
        AcceptingGate(),
        notifier=notifier,
        audit_log=audit,
    )
    source = StringIO(
        '{"operation":"disconnect","service_id":"wifi_lab",'
        '"passphrase":"example-only"}'
    )
    target = StringIO()

    exit_code = process_stream(source, target, service)

    assert exit_code == 1
    assert json.loads(target.getvalue()) == {
        "status": "failed",
        "operation": "disconnect",
        "data": {},
        "reason": "operation_failed",
    }
    assert notifier.calls[-1] == ("rejected", "disconnect")
    assert audit.events[-1] == {"operation": "disconnect", "status": "failed"}
    assert "example-only" not in target.getvalue()


def test_build_robot_service_resolves_only_required_naoqi_services() -> None:
    manager = FakeConnectionManager()
    memory = FakeMemory()
    session = FakeSession(
        {
            "ALConnectionManager": manager,
            "ALMemory": memory,
            "ALTextToSpeech": object(),
            "ALLeds": object(),
        }
    )

    service = build_robot_service(session, audit_log=RecordingAudit())

    assert isinstance(service, NetworkAdminService)
    assert session.requests == [
        "ALConnectionManager",
        "ALMemory",
        "ALTextToSpeech",
        "ALLeds",
    ]


def test_nao_notifier_uses_spanish_voice_and_native_integer_led_colors() -> None:
    tts = FakePostTts()
    leds = FakeLeds()
    notifier = NaoNotifier(tts, leds)

    notifier.pending("connect")
    notifier.completed("connect")
    notifier.rejected("forget")

    assert tts.calls == [
        "Mantén presionado el sensor trasero de mi cabeza durante tres segundos.",
        "Operación de red confirmada.",
        "Operación de red cancelada.",
    ]
    assert leds.calls == [
        ("ChestLeds", 0xFFFF00, 0.2),
        ("ChestLeds", 0x00FF00, 0.2),
        ("ChestLeds", 0xFF0000, 0.2),
    ]
    assert all(type(call[1]) is int for call in leds.calls)


def test_json_audit_log_redacts_secrets_before_writing(tmp_path) -> None:
    log_path = tmp_path / "nested" / "network_admin.log"
    audit = JsonAuditLog(str(log_path))

    audit.write(
        {
            "operation": "connect",
            "status": "failed",
            "passphrase": "example-only",
        }
    )

    entry = json.loads(log_path.read_text(encoding="utf-8"))
    assert entry["operation"] == "connect"
    assert entry["status"] == "failed"
    assert entry["passphrase"] == "[REDACTED]"
    assert isinstance(entry["timestamp"], float)
    assert "example-only" not in log_path.read_text(encoding="utf-8")


def test_main_connects_to_local_naoqi_and_processes_one_stdin_request() -> None:
    manager = FakeConnectionManager()
    memory = FakeMemory()
    session = FakeSession(
        {
            "ALConnectionManager": manager,
            "ALMemory": memory,
            "ALTextToSpeech": FakePostTts(),
            "ALLeds": FakeLeds(),
        }
    )
    source = StringIO('{"operation":"status"}')
    target = StringIO()

    exit_code = main(
        argv=["--stdin"],
        source=source,
        target=target,
        session_factory=lambda: session,
        audit_log=RecordingAudit(),
    )

    assert exit_code == 0
    assert session.connections == ["tcp://127.0.0.1:9559"]
    assert json.loads(target.getvalue())["operation"] == "status"


def test_gateway_target_can_be_read_and_saved_after_physical_confirmation(tmp_path) -> None:
    store = GatewayTargetStore(str(tmp_path / "target.json"))
    service = NetworkAdminService(
        ConnectionManagerAdapter(FakeConnectionManager()),
        AcceptingGate(),
        gateway_target_store=store,
    )

    saved = service.execute({
        "operation": "set_gateway_target",
        "pc_ip": "192.168.10.25",
    })
    current = service.execute({"operation": "gateway_target"})

    assert saved["status"] == "completed"
    assert current["data"] == {"pc_ip": "192.168.10.25"}


def test_gateway_target_rejects_command_injection_before_persisting(tmp_path) -> None:
    store = GatewayTargetStore(str(tmp_path / "target.json"))
    service = NetworkAdminService(
        ConnectionManagerAdapter(FakeConnectionManager()),
        AcceptingGate(),
        gateway_target_store=store,
    )

    with pytest.raises(ValueError):
        service.execute({
            "operation": "set_gateway_target",
            "pc_ip": "192.168.10.25 && calc.exe",
        })
    assert store.load() == {"pc_ip": ""}

from __future__ import annotations

import json
import sys
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[2]
CONTROL = RUNTIME / "control_server"
COMMANDS = CONTROL / "commands"
for path in (str(RUNTIME), str(CONTROL), str(COMMANDS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from message_security import safe_message_summary
from network_commands import NetworkAdminCommand


class RecordingSocket:
    def __init__(self) -> None:
        self.messages = []

    def sendMessage(self, message):
        self.messages.append(message)


class RecordingLogger:
    def __init__(self) -> None:
        self.messages = []

    def _record(self, message) -> None:
        self.messages.append(str(message))

    debug = _record
    info = _record
    warning = _record
    error = _record


class RecordingService:
    def __init__(self, result=None, error=None) -> None:
        self.requests = []
        self.result = result or {
            "status": "completed",
            "operation": "status",
            "data": {"state": "ready"},
        }
        self.error = error

    def execute(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def _execute(service, message):
    socket = RecordingSocket()
    logger = RecordingLogger()
    command = NetworkAdminCommand(object(), logger, service)
    success = command.execute(message, socket)
    return success, json.loads(socket.messages[-1])["networkAdmin"], logger


def test_network_command_forwards_only_allowlisted_service_fields() -> None:
    service = RecordingService(
        {
            "status": "completed",
            "operation": "connect",
            "data": {"service": {"ServiceId": "wifi_lab"}},
        }
    )
    success, payload, logger = _execute(
        service,
        {
            "action": "networkAdmin",
            "request_id": "req-1",
            "operation": "connect",
            "service_id": "wifi_lab",
            "ssid": "Laboratorio",
            "passphrase": "example-only",
        },
    )

    assert success is True
    assert service.requests == [
        {
            "operation": "connect",
            "service_id": "wifi_lab",
            "ssid": "Laboratorio",
            "passphrase": "example-only",
        }
    ]
    assert payload == {
        "request_id": "req-1",
        "status": "completed",
        "operation": "connect",
        "data": {"service": {"ServiceId": "wifi_lab"}},
    }
    assert "example-only" not in json.dumps(payload)
    assert "example-only" not in " ".join(logger.messages)


def test_network_command_rejects_unknown_outer_fields_before_service_call() -> None:
    service = RecordingService()
    success, payload, _logger = _execute(
        service,
        {
            "action": "networkAdmin",
            "request_id": "req-2",
            "operation": "status",
            "command": "id",
        },
    )

    assert success is False
    assert service.requests == []
    assert payload == {
        "request_id": "req-2",
        "status": "rejected",
        "operation": "unknown",
        "data": {},
        "reason": "invalid_request",
    }


def test_network_command_reports_unavailable_without_crashing_control() -> None:
    success, payload, _logger = _execute(
        None,
        {"action": "networkAdmin", "request_id": "req-3", "operation": "status"},
    )

    assert success is False
    assert payload["status"] == "failed"
    assert payload["reason"] == "unavailable"


def test_network_command_returns_stable_failure_without_exception_text() -> None:
    service = RecordingService(error=RuntimeError("backend example-only"))
    success, payload, logger = _execute(
        service,
        {"action": "networkAdmin", "request_id": "req-4", "operation": "scan"},
    )

    assert success is False
    assert payload == {
        "request_id": "req-4",
        "status": "failed",
        "operation": "scan",
        "data": {},
        "reason": "operation_failed",
    }
    assert "example-only" not in json.dumps(payload)
    assert "example-only" not in " ".join(logger.messages)


def test_network_command_redacts_sensitive_fields_from_service_result() -> None:
    service = RecordingService(
        {
            "status": "completed",
            "operation": "status",
            "data": {"profile": {"Name": "Lab", "Passphrase": "example-only"}},
        }
    )
    _success, payload, _logger = _execute(
        service,
        {"action": "networkAdmin", "request_id": "req-redact", "operation": "status"},
    )

    assert payload["data"]["profile"]["Passphrase"] == "[REDACTED]"
    assert "example-only" not in json.dumps(payload)


def test_network_command_rejects_invalid_request_identifier() -> None:
    service = RecordingService()
    success, payload, _logger = _execute(
        service,
        {
            "action": "networkAdmin",
            "request_id": "invalid identifier with spaces",
            "operation": "status",
        },
    )

    assert success is False
    assert service.requests == []
    assert payload["request_id"] == "invalid"
    assert payload["reason"] == "invalid_request"


def test_safe_message_summary_never_serializes_sensitive_or_unknown_fields() -> None:
    summary = safe_message_summary(
        {
            "action": "networkAdmin",
            "request_id": "req-5",
            "operation": "connect",
            "passphrase": "example-only",
            "debug": "must-not-appear",
        }
    )

    assert summary == "action=networkAdmin operation=connect request_id=req-5"
    assert "example-only" not in summary
    assert "must-not-appear" not in summary


def test_safe_message_summary_bounds_untrusted_metadata() -> None:
    summary = safe_message_summary(
        {
            "action": "networkAdmin\nforged",
            "request_id": "x" * 65,
            "operation": "shell command",
        }
    )

    assert summary == "action=invalid operation=invalid request_id=invalid"

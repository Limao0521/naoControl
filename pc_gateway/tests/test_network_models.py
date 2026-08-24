from __future__ import annotations

import pytest

from nao_gateway.network_models import (
    NetworkRequest,
    NetworkRequestError,
    parse_network_request,
    redact_sensitive,
)


def test_parse_rejects_unknown_operation() -> None:
    with pytest.raises(NetworkRequestError, match="Unsupported network operation"):
        parse_network_request({"operation": "shell", "command": "id"})


def test_parse_rejects_unknown_fields() -> None:
    with pytest.raises(NetworkRequestError, match="Unknown network request fields"):
        parse_network_request({"operation": "status", "debug": True})


def test_parse_requires_service_for_mutation() -> None:
    with pytest.raises(NetworkRequestError, match="service_id is required"):
        parse_network_request({"operation": "disconnect"})


def test_parse_rejects_invalid_connect_passphrase_length() -> None:
    with pytest.raises(NetworkRequestError, match="between 8 and 63"):
        parse_network_request(
            {"operation": "connect", "service_id": "wifi_lab", "passphrase": "short"}
        )


def test_parse_rejects_nul_in_operator_values() -> None:
    with pytest.raises(NetworkRequestError, match="must not contain NUL"):
        parse_network_request({"operation": "forget", "service_id": "wifi\x00lab"})


def test_parse_normalizes_supported_request() -> None:
    request = parse_network_request(
        {
            "operation": "connect",
            "service_id": "wifi_lab",
            "ssid": "Laboratorio",
            "passphrase": "example-only",
        }
    )

    assert request == NetworkRequest(
        operation="connect",
        service_id="wifi_lab",
        ssid="Laboratorio",
        passphrase="example-only",
    )


def test_redaction_removes_nested_secret_values() -> None:
    payload = {
        "ssid": "Lab",
        "passphrase": "example-only",
        "nested": {"password": "example-only", "state": "ready"},
        "items": [{"psk": "example-only"}, "visible"],
    }

    assert redact_sensitive(payload) == {
        "ssid": "Lab",
        "passphrase": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "state": "ready"},
        "items": [{"psk": "[REDACTED]"}, "visible"],
    }


def test_redaction_does_not_mutate_original_value() -> None:
    payload = {"passphrase": "example-only"}

    assert redact_sensitive(payload) == {"passphrase": "[REDACTED]"}
    assert payload == {"passphrase": "example-only"}

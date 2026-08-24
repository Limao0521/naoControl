from __future__ import annotations

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from nao_gateway.network_broker import (
    ProcessResult,
    SshNetworkTransport,
    create_network_app,
)
from nao_gateway.network_models import NetworkRequest


APPROVED_ORIGIN = "http://169.254.1.2:3000"


class FakeTransport:
    def __init__(self) -> None:
        self.requests = []

    async def execute(self, request: NetworkRequest) -> dict:
        self.requests.append(request)
        return {"status": "completed", "operation": request.operation, "data": {}}


class RecordingProcessRunner:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.argv = []
        self.stdin = b""
        self.timeout = None

    async def __call__(self, argv, stdin, timeout):
        self.argv = list(argv)
        self.stdin = stdin
        self.timeout = timeout
        return self.result


async def make_client(transport) -> TestClient:
    client = TestClient(TestServer(create_network_app(transport, {APPROVED_ORIGIN})))
    await client.start_server()
    return client


@pytest.mark.asyncio
async def test_unapproved_origin_is_rejected_before_transport() -> None:
    transport = FakeTransport()
    client = await make_client(transport)
    try:
        response = await client.get(
            "/network/status", headers={"Origin": "https://attacker.example"}
        )
        assert response.status == 403
        assert transport.requests == []
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_approved_status_request_has_nostore_cors_response() -> None:
    transport = FakeTransport()
    client = await make_client(transport)
    try:
        response = await client.get(
            "/network/status", headers={"Origin": APPROVED_ORIGIN}
        )
        assert response.status == 200
        assert response.headers["Access-Control-Allow-Origin"] == APPROVED_ORIGIN
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Vary"] == "Origin"
        assert transport.requests == [NetworkRequest(operation="status")]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_operation_endpoint_rejects_read_only_operation() -> None:
    transport = FakeTransport()
    client = await make_client(transport)
    try:
        response = await client.post(
            "/network/operation",
            headers={"Origin": APPROVED_ORIGIN},
            json={"operation": "status"},
        )
        assert response.status == 400
        assert transport.requests == []
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_query_endpoint_accepts_scan_and_profiles_only() -> None:
    transport = FakeTransport()
    client = await make_client(transport)
    try:
        response = await client.post(
            "/network/query",
            headers={"Origin": APPROVED_ORIGIN},
            json={"operation": "scan"},
        )
        assert response.status == 200
        assert transport.requests == [NetworkRequest(operation="scan")]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ssh_transport_keeps_ssid_and_passphrase_out_of_argv() -> None:
    result = ProcessResult(
        0,
        b'{"status":"completed","operation":"connect","data":{}}\n',
        b"",
    )
    runner = RecordingProcessRunner(result)
    transport = SshNetworkTransport(
        "nao", "169.254.1.2", "C:/keys/nao", runner=runner
    )

    response = await transport.execute(
        NetworkRequest("connect", "wifi_lab", "Laboratorio", "example-only")
    )

    argv_text = " ".join(runner.argv)
    assert "Laboratorio" not in argv_text
    assert "example-only" not in argv_text
    assert json.loads(runner.stdin)["service_id"] == "wifi_lab"
    assert json.loads(runner.stdin)["passphrase"] == "example-only"
    assert runner.timeout == 45.0
    assert response["status"] == "completed"


@pytest.mark.asyncio
async def test_ssh_failure_after_mutation_is_not_reported_as_success() -> None:
    runner = RecordingProcessRunner(
        ProcessResult(255, b"", b"connection closed with example-only")
    )
    transport = SshNetworkTransport(
        "nao", "169.254.1.2", "C:/keys/nao", runner=runner
    )

    response = await transport.execute(NetworkRequest("forget", "wifi_lab"))

    assert response == {
        "status": "transport_lost_after_apply",
        "operation": "forget",
        "data": {},
        "reason": "ssh_connection_lost",
    }
    assert "example-only" not in json.dumps(response)


@pytest.mark.asyncio
async def test_malformed_helper_output_fails_closed() -> None:
    runner = RecordingProcessRunner(ProcessResult(0, b"not-json", b""))
    transport = SshNetworkTransport(
        "nao", "169.254.1.2", "C:/keys/nao", runner=runner
    )

    response = await transport.execute(NetworkRequest("status"))

    assert response == {
        "status": "failed",
        "operation": "status",
        "data": {},
        "reason": "invalid_helper_response",
    }

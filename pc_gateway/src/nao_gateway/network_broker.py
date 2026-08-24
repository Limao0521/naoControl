"""Loopback-only HTTP broker for SSH-protected NAO network administration."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable, Iterable

from aiohttp import web

from .network_models import (
    NetworkRequest,
    NetworkRequestError,
    parse_network_request,
    redact_sensitive,
)


READ_OPERATIONS = frozenset({"status", "scan", "profiles"})
MUTATING_OPERATIONS = frozenset({"connect", "disconnect", "forget"})
REMOTE_HELPER_COMMAND = (
    "python2 /home/nao/naoControl/nao/scripts/runtime/network_admin.py --stdin"
)
MAX_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


ProcessRunner = Callable[[list[str], bytes, float], Awaitable[ProcessResult]]


async def _run_process(argv: list[str], stdin: bytes, timeout: float) -> ProcessResult:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(stdin), timeout=timeout
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return ProcessResult(124, b"", b"")
    return ProcessResult(process.returncode, stdout, stderr)


class SshNetworkTransport:
    """Run one fixed robot helper command; untrusted values use stdin only."""

    def __init__(
        self,
        user: str,
        host: str,
        key_path: str,
        *,
        runner: ProcessRunner = _run_process,
        timeout: float = 45.0,
    ) -> None:
        self.user = user
        self.host = host
        self.key_path = key_path
        self.runner = runner
        self.timeout = timeout

    def _argv(self) -> list[str]:
        return [
            "ssh",
            "-i",
            self.key_path,
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=8",
            f"{self.user}@{self.host}",
            REMOTE_HELPER_COMMAND,
        ]

    async def execute(self, request: NetworkRequest) -> dict:
        stdin = json.dumps(asdict(request), separators=(",", ":")).encode("utf-8")
        try:
            result = await self.runner(self._argv(), stdin, self.timeout)
        except Exception:
            return self._failure(request.operation, "ssh_transport_failed")

        if len(result.stdout) > MAX_RESPONSE_BYTES or len(result.stderr) > MAX_RESPONSE_BYTES:
            return self._failure(request.operation, "response_too_large")
        if result.returncode != 0:
            if result.returncode == 255 and request.operation in MUTATING_OPERATIONS:
                return {
                    "status": "transport_lost_after_apply",
                    "operation": request.operation,
                    "data": {},
                    "reason": "ssh_connection_lost",
                }
            reason = "ssh_timeout" if result.returncode == 124 else "ssh_transport_failed"
            return self._failure(request.operation, reason)

        try:
            payload = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._failure(request.operation, "invalid_helper_response")
        if not isinstance(payload, dict):
            return self._failure(request.operation, "invalid_helper_response")
        if payload.get("operation") != request.operation or payload.get("status") not in {
            "completed",
            "rejected",
            "confirmation_timeout",
            "failed",
        }:
            return self._failure(request.operation, "invalid_helper_response")
        return redact_sensitive(payload)

    @staticmethod
    def _failure(operation: str, reason: str) -> dict:
        return {
            "status": "failed",
            "operation": operation,
            "data": {},
            "reason": reason,
        }


def _json_error(reason: str, status: int = 400) -> web.Response:
    return web.json_response(
        {"status": "rejected", "operation": "unknown", "data": {}, "reason": reason},
        status=status,
    )


async def _read_json(request: web.Request) -> dict:
    try:
        payload = await request.json(loads=json.loads)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise NetworkRequestError("invalid_json")
    if not isinstance(payload, dict):
        raise NetworkRequestError("invalid_json")
    return payload


def create_network_app(
    transport: SshNetworkTransport,
    allowed_origins: Iterable[str],
) -> web.Application:
    origins = frozenset(allowed_origins)

    @web.middleware
    async def security_headers(request: web.Request, handler):
        origin = request.headers.get("Origin", "")
        if request.path != "/health" and origin not in origins:
            return _json_error("origin_not_allowed", status=403)
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def status(_request: web.Request) -> web.Response:
        return web.json_response(await transport.execute(NetworkRequest("status")))

    async def query(request: web.Request) -> web.Response:
        try:
            parsed = parse_network_request(await _read_json(request))
        except NetworkRequestError:
            return _json_error("invalid_request")
        if parsed.operation not in READ_OPERATIONS - {"status"}:
            return _json_error("operation_not_allowed")
        return web.json_response(await transport.execute(parsed))

    async def operation(request: web.Request) -> web.Response:
        try:
            parsed = parse_network_request(await _read_json(request))
        except NetworkRequestError:
            return _json_error("invalid_request")
        if parsed.operation not in MUTATING_OPERATIONS:
            return _json_error("operation_not_allowed")
        return web.json_response(await transport.execute(parsed))

    async def options(_request: web.Request) -> web.Response:
        return web.Response(status=204)

    app = web.Application(middlewares=[security_headers], client_max_size=8192)
    app.router.add_get("/health", health)
    app.router.add_get("/network/status", status)
    app.router.add_post("/network/query", query)
    app.router.add_post("/network/operation", operation)
    app.router.add_route("OPTIONS", "/{tail:.*}", options)
    return app

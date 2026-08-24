"""Small authenticated PC bootstrap that starts code downloaded from the NAO."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from dotenv import load_dotenv

from .protocol import ReplayGuard, sign_envelope, verify_envelope


logger = logging.getLogger(__name__)


class BundleError(ValueError):
    pass


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _canonical_ipv4(value: str) -> str:
    try:
        packed = socket.inet_aton(value)
        canonical = socket.inet_ntoa(packed)
    except OSError as error:
        raise BundleError("invalid robot address") from error
    if canonical != value:
        raise BundleError("invalid robot address")
    return canonical


def _download(url: str, maximum: int) -> bytes:
    with urlopen(url, timeout=15) as response:
        content = response.read(maximum + 1)
    if len(content) > maximum:
        raise BundleError("gateway bundle is too large")
    return content


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise BundleError("unsafe bundle member") from error
        if member.issym() or member.islnk() or member.isdev():
            raise BundleError("unsafe bundle member")
    for member in archive.getmembers():
        target = root / member.name
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not member.isfile():
            raise BundleError("unsafe bundle member")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise BundleError("gateway bundle is invalid")
        with source, open(target, "wb") as output:
            shutil.copyfileobj(source, output)


class GatewayRuntime:
    MAX_BUNDLE_BYTES = 8 * 1024 * 1024

    def __init__(
        self,
        root: Path,
        bundle_fetcher=_download,
        process_factory=subprocess.Popen,
        python_executable: str | None = None,
        startup_sleep=time.sleep,
    ) -> None:
        self.root = Path(root)
        self.bundle_fetcher = bundle_fetcher
        self.process_factory = process_factory
        self.python_executable = python_executable or sys.executable
        self.startup_sleep = startup_sleep
        self._process = None
        self._log_handles = []

    def _running(self) -> bool:
        if self._process is not None and getattr(self._process, "poll", lambda: None)() is None:
            return True
        pid_path = self.root / "gateway.pid"
        try:
            pid = int(pid_path.read_text(encoding="ascii").strip())
            return _pid_is_running(pid)
        except (OSError, ValueError):
            return False

    def _release(self, content: bytes, digest: str) -> Path:
        releases = self.root / "releases"
        release = releases / digest
        if release.is_dir():
            return release
        releases.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="incoming-", dir=str(releases)))
        archive_path = temporary / "bundle.tar.gz"
        archive_path.write_bytes(content)
        extracted = temporary / "source"
        extracted.mkdir()
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                _safe_extract(archive, extracted)
            required = (
                extracted / "pc_gateway" / "src" / "nao_gateway" / "__init__.py",
                extracted / "config" / "action_registry.json",
                extracted / "config" / "behavior_registry.json",
            )
            if not all(path.is_file() for path in required):
                raise BundleError("gateway bundle is incomplete")
            extracted.rename(release)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return release

    def install_and_start(self, nao_ip: str, bundle_name: str, expected_sha256: str) -> dict:
        nao_ip = _canonical_ipv4(nao_ip)
        if bundle_name != "pc_gateway_bundle.tar.gz":
            raise BundleError("invalid bundle name")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise BundleError("invalid bundle digest")
        if self._running():
            pid = int((self.root / "gateway.pid").read_text(encoding="ascii"))
            return {"status": "already_running", "pid": pid}

        url = f"http://{nao_ip}:6677/{bundle_name}"
        content = self.bundle_fetcher(url, self.MAX_BUNDLE_BYTES)
        if not isinstance(content, bytes):
            raise BundleError("gateway bundle is invalid")
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_sha256:
            raise BundleError("gateway bundle digest mismatch")
        release = self._release(content, digest)

        env_file = self.root / ".env"
        if not env_file.is_file():
            raise BundleError("PC gateway .env is not configured")
        logs = self.root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        stdout = open(logs / "gateway.log", "ab", buffering=0)
        stderr = open(logs / "gateway-error.log", "ab", buffering=0)
        self._log_handles = [stdout, stderr]

        environment = os.environ.copy()
        environment["NAO_GATEWAY_URL"] = f"ws://{nao_ip}:6674"
        environment["PYTHONPATH"] = str(release / "pc_gateway" / "src")
        args = [
            self.python_executable,
            "-u",
            "-m",
            "nao_gateway.main",
            "--env-file",
            str(env_file),
            "--registry",
            str(release / "config" / "action_registry.json"),
        ]
        options = {
            "cwd": str(release),
            "env": environment,
            "stdin": subprocess.DEVNULL,
            "stdout": stdout,
            "stderr": stderr,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._process = self.process_factory(args, **options)
        self.startup_sleep(0.5)
        if getattr(self._process, "poll", lambda: None)() is not None:
            for handle in self._log_handles:
                handle.close()
            self._log_handles = []
            raise BundleError("gateway process exited during startup")
        (self.root / "gateway.pid").write_text(str(self._process.pid), encoding="ascii")
        return {"status": "ready", "pid": self._process.pid}


class LauncherCoordinator:
    def __init__(self, secret: bytes, runtime: GatewayRuntime, now_ms=None) -> None:
        if len(secret) < 32:
            raise ValueError("launcher secret must contain at least 32 bytes")
        self.secret = secret
        self.runtime = runtime
        self.now_ms = now_ms or (lambda: int(__import__("time").time() * 1000))
        self.replay_guard = ReplayGuard(1000)

    def handle(self, envelope: dict, client_ip: str) -> dict:
        client_ip = _canonical_ipv4(client_ip)
        if not isinstance(envelope, dict) or envelope.get("message_type") != "gateway_start":
            raise BundleError("invalid launcher request")
        payload = verify_envelope(
            envelope, self.secret, self.now_ms(), self.replay_guard
        )
        if not isinstance(payload, dict) or set(payload) != {"bundle_name", "bundle_sha256"}:
            raise BundleError("invalid launcher payload")
        return self.runtime.install_and_start(
            client_ip, payload["bundle_name"], payload["bundle_sha256"]
        )

    def response(self, request_id: str, result: dict) -> dict:
        now = self.now_ms()
        payload = {
            "request_id": request_id,
            "status": result["status"],
            "pid": int(result["pid"]),
        }
        return sign_envelope({
            "protocol_version": 1,
            "message_type": "gateway_start_result",
            "message_id": __import__("uuid").uuid4().hex,
            "issued_at_ms": now,
            "expires_at_ms": now + 30000,
            "payload": payload,
        }, self.secret)


def create_handler(coordinator: LauncherCoordinator):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NaoGatewayLauncher/1"

        def do_POST(self):
            if self.path != "/start":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 8192:
                    raise BundleError("invalid request size")
                envelope = json.loads(self.rfile.read(length).decode("utf-8"))
                result = coordinator.handle(envelope, self.client_address[0])
                result = coordinator.response(envelope["message_id"], result)
                logger.info("Gateway start accepted from %s", self.client_address[0])
                status = 200
            except Exception:
                logger.warning("Gateway start rejected from %s", self.client_address[0])
                result = {"status": "rejected", "reason": "invalid_request"}
                status = 400
            encoded = json.dumps(result, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=6676)
    args = parser.parse_args()
    load_dotenv(args.env_file)
    log_dir = Path(args.runtime_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "launcher.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    secret = os.environ.get("NAO_GATEWAY_SECRET", "").strip().encode("utf-8")
    coordinator = LauncherCoordinator(secret, GatewayRuntime(Path(args.runtime_root)))
    server = ThreadingHTTPServer((args.host, args.port), create_handler(coordinator))
    logger.info("NAO PC launcher listening on %s:%s", args.host, args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()

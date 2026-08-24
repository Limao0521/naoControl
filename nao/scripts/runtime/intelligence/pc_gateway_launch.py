#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Persist the PC target and request a signed remote gateway start."""
from __future__ import absolute_import, print_function

import hashlib
import json
import os
import socket
import time
import uuid

try:
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 on the robot
    from urllib2 import Request, urlopen

try:
    from .protocol import sign_envelope
except (ImportError, ValueError):  # pragma: no cover - direct robot execution
    from protocol import sign_envelope


MAX_RESPONSE_BYTES = 4096
DEFAULT_TARGET_PATH = "/home/nao/naoControl/config/pc_gateway_target.json"
DEFAULT_BUNDLE_PATH = "/home/nao/naoControl/pc_bundle/pc_gateway_bundle.tar.gz"


class GatewayLaunchError(ValueError):
    pass


def _valid_ipv4(value):
    if not isinstance(value, str):
        try:
            value = value.encode("ascii")
        except Exception:
            return False
    try:
        text = value.decode("ascii") if not isinstance(value, str) else value
        packed = socket.inet_aton(text)
        return socket.inet_ntoa(packed) == text
    except (socket.error, UnicodeError):
        return False


class GatewayTargetStore(object):
    def __init__(self, path=DEFAULT_TARGET_PATH):
        self.path = path

    def load(self):
        try:
            with open(self.path, "rb") as source:
                data = json.loads(source.read().decode("utf-8"))
            pc_ip = data.get("pc_ip", "") if isinstance(data, dict) else ""
            if pc_ip and _valid_ipv4(pc_ip):
                return {"pc_ip": pc_ip}
        except (IOError, OSError, TypeError, ValueError):
            pass
        return {"pc_ip": ""}

    def save(self, pc_ip):
        if not _valid_ipv4(pc_ip):
            raise GatewayLaunchError("pc_ip is invalid")
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        temporary = self.path + ".tmp"
        with open(temporary, "wb") as target:
            target.write(json.dumps({"pc_ip": pc_ip}, separators=(",", ":")).encode("utf-8"))
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.rename(temporary, self.path)
        return {"pc_ip": pc_ip}


def _http_transport(url, body, timeout):
    request = Request(
        url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    response = urlopen(request, timeout=timeout)
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise GatewayLaunchError("launcher response is too large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (TypeError, ValueError):
        raise GatewayLaunchError("launcher response is invalid")
    if not isinstance(result, dict):
        raise GatewayLaunchError("launcher response is invalid")
    return result


class RemoteGatewayLauncher(object):
    def __init__(self, target_store, secret, bundle_path=DEFAULT_BUNDLE_PATH,
                 transport=None, now_ms=None):
        self.target_store = target_store
        self.secret = secret
        self.bundle_path = bundle_path
        self.transport = transport or _http_transport
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

    def _bundle_sha256(self):
        digest = hashlib.sha256()
        try:
            with open(self.bundle_path, "rb") as source:
                while True:
                    block = source.read(65536)
                    if not block:
                        break
                    digest.update(block)
        except (IOError, OSError):
            raise GatewayLaunchError("gateway bundle is unavailable")
        return digest.hexdigest()

    def start(self):
        pc_ip = self.target_store.load().get("pc_ip", "")
        if not pc_ip:
            raise GatewayLaunchError("pc target is not configured")
        now = self.now_ms()
        envelope = sign_envelope({
            "protocol_version": 1,
            "message_type": "gateway_start",
            "message_id": str(uuid.uuid4()),
            "issued_at_ms": now,
            "expires_at_ms": now + 30000,
            "payload": {
                "bundle_name": "pc_gateway_bundle.tar.gz",
                "bundle_sha256": self._bundle_sha256(),
            },
        }, self.secret)
        result = self.transport(
            "http://{}:6676/start".format(pc_ip),
            json.dumps(envelope, separators=(",", ":")),
            20,
        )
        if result.get("status") not in ("ready", "already_running"):
            raise GatewayLaunchError("pc launcher rejected the request")
        return result


class GatewayEntryGate(object):
    """Combine robot safety and PC launch into the mode-entry decision."""

    def __init__(self, safety, launcher):
        self.safety = safety
        self.launcher = launcher
        self.last_reason = "not_checked"

    def __call__(self):
        allowed, reasons = self.safety.check_intelligent_entry()
        if not allowed:
            self.last_reason = reasons[0] if reasons else "robot_not_ready"
            return False
        try:
            self.launcher.start()
        except Exception as error:
            if str(error) == "pc target is not configured":
                self.last_reason = "pc_target_not_configured"
            else:
                self.last_reason = "pc_gateway_unavailable"
            return False
        self.last_reason = "ready"
        return True

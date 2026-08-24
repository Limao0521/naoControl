#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""SSH-invoked, physically confirmed network administration for NAO."""

from __future__ import print_function

import json
import os
import sys
import time

try:
    basestring
except NameError:  # pragma: no cover - Python 3 test runtime
    basestring = str


MAX_REQUEST_BYTES = 8192
ALLOWED_OPERATIONS = frozenset((
    "status", "scan", "profiles", "connect", "disconnect", "forget",
))
ALLOWED_REQUEST_FIELDS = frozenset((
    "operation", "service_id", "ssid", "passphrase",
))
MUTATING_OPERATIONS = frozenset(("connect", "disconnect", "forget"))
VISIBLE_SERVICE_FIELDS = (
    "ServiceId", "Name", "Type", "State", "Security", "Strength",
    "Favorite", "AutoConnect", "IPv4", "IPv6", "Nameservers", "Domains",
)


class NetworkAdminError(ValueError):
    pass


class NullNotifier(object):
    def pending(self, operation):
        pass

    def completed(self, operation):
        pass

    def rejected(self, operation):
        pass


class NullAuditLog(object):
    def write(self, event):
        pass


class NaoNotifier(object):
    """Use Spanish voice and chest LEDs for the physical approval flow."""

    def __init__(self, tts, leds):
        self.tts = tts
        self.leds = leds

    def _say(self, text):
        speaker = getattr(self.tts, "post", self.tts)
        speaker.say(text)

    def _led(self, color):
        self.leds.fadeRGB("ChestLeds", int(color), 0.2)

    def pending(self, operation):
        self._led(0xFFFF00)
        self._say("Mantén presionado el sensor trasero de mi cabeza durante tres segundos.")

    def completed(self, operation):
        self._led(0x00FF00)
        self._say("Operación de red confirmada.")

    def rejected(self, operation):
        self._led(0xFF0000)
        self._say("Operación de red cancelada.")


def _redact(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in ("passphrase", "password", "secret", "psk"):
                result[key] = "[REDACTED]"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class JsonAuditLog(object):
    def __init__(self, path):
        self.path = path

    def write(self, event):
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        entry = dict(_redact(event), timestamp=time.time())
        with open(self.path, "ab") as stream:
            stream.write((json.dumps(entry, separators=(",", ":")) + "\n").encode("utf-8"))


class RearTactileGate(object):
    """Require one uninterrupted rear-head touch before allowing mutation."""

    def __init__(self, read_sensor, clock=None, sleep=None,
                 hold_seconds=3.0, poll_seconds=0.05):
        self.read_sensor = read_sensor
        self.clock = clock or time.time
        self.sleep = sleep or time.sleep
        self.hold_seconds = float(hold_seconds)
        self.poll_seconds = float(poll_seconds)

    def wait_for_hold(self, timeout_seconds):
        deadline = self.clock() + float(timeout_seconds)
        hold_started = None
        while self.clock() < deadline:
            touched = float(self.read_sensor() or 0.0) >= 0.5
            now = self.clock()
            if touched:
                if hold_started is None:
                    hold_started = now
                if now - hold_started >= self.hold_seconds:
                    return True
            else:
                hold_started = None
            self.sleep(self.poll_seconds)
        return False


def _normalize_service(service):
    source = dict(service)
    return dict(
        (field, source[field])
        for field in VISIBLE_SERVICE_FIELDS
        if field in source
    )


class ConnectionManagerAdapter(object):
    """Small allowlisted boundary around NAOqi ALConnectionManager."""

    def __init__(self, manager, memory=None):
        self.manager = manager
        self.memory = memory

    def status(self):
        return {
            "state": self.manager.state(),
            "interfaces": [dict(item) for item in self.manager.interfaces()],
            "services": [_normalize_service(item) for item in self.manager.services()],
        }

    def scan(self):
        self.manager.scan()
        return {"services": [_normalize_service(item) for item in self.manager.services()]}

    def profiles(self):
        return {
            "profiles": [
                _normalize_service(item)
                for item in self.manager.provisionedServices()
            ]
        }

    def connect(self, service_id, passphrase="", ssid=""):
        signal = None
        connection_id = None
        if self.memory is not None:
            signal = self.memory.subscriber("NetworkServiceInputRequired").signal

            def on_input_required(input_request):
                requested = dict(input_request)
                reply = [["ServiceId", service_id]]
                if "Passphrase" in requested:
                    if not passphrase:
                        raise NetworkAdminError("passphrase required")
                    reply.append(["Passphrase", passphrase])
                if "Name" in requested:
                    if not ssid:
                        raise NetworkAdminError("ssid required")
                    reply.append(["Name", ssid])
                self.manager.setServiceInput(reply)

            connection_id = signal.connect(on_input_required)

        try:
            self.manager.connect(service_id)
            return {"service": _normalize_service(self.manager.service(service_id))}
        finally:
            if signal is not None and connection_id is not None:
                signal.disconnect(connection_id)

    def disconnect(self, service_id):
        self.manager.disconnect(service_id)
        return {"service_id": service_id}

    def forget(self, service_id):
        self.manager.forget(service_id)
        return {"service_id": service_id}


class NetworkAdminService(object):
    def __init__(self, adapter, tactile_gate, confirmation_timeout=20.0,
                 notifier=None, audit_log=None):
        self.adapter = adapter
        self.tactile_gate = tactile_gate
        self.confirmation_timeout = float(confirmation_timeout)
        self.notifier = notifier or NullNotifier()
        self.audit_log = audit_log or NullAuditLog()

    def execute(self, request):
        if not isinstance(request, dict):
            raise NetworkAdminError("request must be an object")
        if set(request) - ALLOWED_REQUEST_FIELDS:
            raise NetworkAdminError("unknown fields")

        operation = request.get("operation")
        if operation not in ALLOWED_OPERATIONS:
            raise NetworkAdminError("unsupported operation")

        service_id = request.get("service_id", "")
        ssid = request.get("ssid", "")
        passphrase = request.get("passphrase", "")
        for name, value, maximum in (
            ("service_id", service_id, 512),
            ("ssid", ssid, 32),
            ("passphrase", passphrase, 63),
        ):
            if not isinstance(value, basestring):
                raise NetworkAdminError(name + " must be a string")
            if "\x00" in value or len(value) > maximum:
                raise NetworkAdminError(name + " is invalid")
        if passphrase and len(passphrase) < 8:
            raise NetworkAdminError("passphrase is invalid")
        if operation in MUTATING_OPERATIONS and not service_id:
            raise NetworkAdminError("service_id is required")

        if operation in MUTATING_OPERATIONS:
            self.audit_log.write({
                "operation": operation,
                "status": "pending_confirmation",
            })
            self.notifier.pending(operation)
            if not self.tactile_gate.wait_for_hold(self.confirmation_timeout):
                self.notifier.rejected(operation)
                self.audit_log.write({
                    "operation": operation,
                    "status": "confirmation_timeout",
                })
                return {
                    "status": "confirmation_timeout",
                    "operation": operation,
                    "data": {},
                }

        try:
            if operation == "connect":
                data = self.adapter.connect(service_id, passphrase, ssid)
            elif operation in ("disconnect", "forget"):
                data = getattr(self.adapter, operation)(service_id)
            else:
                data = getattr(self.adapter, operation)()
        except Exception:
            if operation in MUTATING_OPERATIONS:
                self.audit_log.write({"operation": operation, "status": "failed"})
                self.notifier.rejected(operation)
            raise
        if operation in MUTATING_OPERATIONS:
            self.audit_log.write({"operation": operation, "status": "completed"})
            self.notifier.completed(operation)
        return {"status": "completed", "operation": operation, "data": data}


def build_robot_service(session, audit_log=None):
    manager = session.service("ALConnectionManager")
    memory = session.service("ALMemory")
    tts = session.service("ALTextToSpeech")
    leds = session.service("ALLeds")
    gate = RearTactileGate(lambda: memory.getData("RearTactilTouched"))
    return NetworkAdminService(
        ConnectionManagerAdapter(manager, memory=memory),
        gate,
        notifier=NaoNotifier(tts, leds),
        audit_log=audit_log or JsonAuditLog(
            "/home/nao/logs/naoControl/network_admin.log"
        ),
    )


def _write_result(stream, result):
    stream.write(json.dumps(result, separators=(",", ":")))
    stream.write("\n")


def process_stream(source, target, service):
    raw = source.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        _write_result(target, {
            "status": "rejected",
            "operation": "unknown",
            "data": {},
            "reason": "request_too_large",
        })
        return 2

    try:
        request = json.loads(raw)
    except (TypeError, ValueError):
        _write_result(target, {
            "status": "rejected",
            "operation": "unknown",
            "data": {},
            "reason": "invalid_request",
        })
        return 2

    try:
        result = service.execute(request)
    except NetworkAdminError:
        _write_result(target, {
            "status": "rejected",
            "operation": "unknown",
            "data": {},
            "reason": "invalid_request",
        })
        return 2
    except Exception:
        operation = request.get("operation", "unknown") if isinstance(request, dict) else "unknown"
        _write_result(target, {
            "status": "failed",
            "operation": operation if operation in ALLOWED_OPERATIONS else "unknown",
            "data": {},
            "reason": "operation_failed",
        })
        return 1

    _write_result(target, result)
    return 0


def main(argv=None, source=None, target=None, session_factory=None, audit_log=None):
    argv = sys.argv[1:] if argv is None else argv
    source = sys.stdin if source is None else source
    target = sys.stdout if target is None else target
    if "--stdin" not in argv:
        print("network_admin requires --stdin", file=sys.stderr)
        return 2
    if session_factory is None:
        import qi
        session_factory = qi.Session
    session = session_factory()
    session.connect("tcp://127.0.0.1:9559")
    return process_stream(
        source,
        target,
        build_robot_service(session, audit_log=audit_log),
    )


if __name__ == "__main__":
    sys.exit(main())

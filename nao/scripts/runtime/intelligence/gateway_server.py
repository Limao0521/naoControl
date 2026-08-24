#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Authenticated NAO-side gateway and physical bumper controller."""
from __future__ import absolute_import, print_function

import json
import os
import sys
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.dirname(HERE)
CONTROL = os.path.join(RUNTIME, "control_server")
for path in (HERE, RUNTIME, CONTROL, os.path.join(CONTROL, "facades"),
             "/home/nao/SimpleWebSocketServer-0.1.2"):
    if path not in sys.path:
        sys.path.insert(0, path)

from protocol import ProtocolError, ReplayGuard, sign_envelope, verify_envelope
from pc_gateway_launch import (
    DEFAULT_BUNDLE_PATH,
    DEFAULT_TARGET_PATH,
    GatewayEntryGate,
    GatewayTargetStore,
    RemoteGatewayLauncher,
)


def create_entry_gate(safety, secret, target_path=DEFAULT_TARGET_PATH,
                      bundle_path=DEFAULT_BUNDLE_PATH, transport=None,
                      now_ms=None):
    launcher = RemoteGatewayLauncher(
        GatewayTargetStore(target_path),
        secret,
        bundle_path=bundle_path,
        transport=transport,
        now_ms=now_ms,
    )
    return GatewayEntryGate(safety, launcher)


class GatewayCore(object):
    def __init__(self, secret, executor, now_ms=None, system_handler=None,
                 interaction_handler=None):
        self.secret = secret
        self.executor = executor
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.system_handler = system_handler or (lambda name: None)
        self.interaction_handler = interaction_handler or (lambda payload: None)
        self.replay_guard = ReplayGuard(1000)

    def envelope(self, message_type, payload):
        now = self.now_ms()
        return sign_envelope({
            "protocol_version": 1,
            "message_type": message_type,
            "message_id": str(uuid.uuid4()),
            "issued_at_ms": now,
            "expires_at_ms": now + 10000,
            "payload": payload,
        }, self.secret)

    def handle_message(self, envelope):
        response_type = "command_result"
        message_type = envelope.get("message_type", "invalid") if isinstance(envelope, dict) else "invalid"
        try:
            payload = verify_envelope(
                envelope, self.secret, self.now_ms(), self.replay_guard
            )
            if message_type == "heartbeat":
                result = {"status": "ok"}
                response_type = "heartbeat_result"
            elif message_type == "turn_finished":
                self.system_handler("TURN_FINISHED")
                result = {"status": "ok"}
                response_type = "event_result"
            elif message_type == "interaction_update":
                self.interaction_handler(payload)
                result = {"status": "ok"}
                response_type = "event_result"
            elif message_type == "command":
                result = self.executor.execute(payload)
            else:
                result = {"status": "rejected", "reason": "unknown_message_type"}
        except Exception as error:
            result = {"status": "rejected", "reason": str(error)}
        if message_type != "heartbeat":
            print(
                "GATEWAY message={} status={} reason={}".format(
                    message_type, result.get("status"), result.get("reason")
                )
            )
        return self.envelope(response_type, result)


class CaptureController(object):
    """Run recorder side effects without leaving the bumper state machine stuck."""
    def __init__(self, manager, capture, interaction_store, facade, send_all,
                 interaction_id_factory=None):
        self.manager = manager
        self.capture = capture
        self.interaction_store = interaction_store
        self.facade = facade
        self.send_all = send_all
        self.interaction_id_factory = interaction_id_factory or uuid.uuid4
        self.interaction_id = None

    def _best_effort(self, operation, label):
        try:
            operation()
        except Exception as error:
            print("GATEWAY recovery_failed operation={} error={}: {}".format(
                label, type(error).__name__, error
            ))

    def recover(self, reason, now_ms, error=None):
        if error is not None:
            print("GATEWAY capture_failed reason={} error={}: {}".format(
                reason, type(error).__name__, error
            ))
        self._best_effort(self.capture.cancel, "capture_cancel")
        self._best_effort(
            lambda: self.manager.handle_system("INTERACTION_CANCELLED", now_ms),
            "mode_recovery",
        )
        self._best_effort(lambda: self.interaction_store.save({
            "interaction_id": self.interaction_id or "",
            "phase": "error", "transcript": "", "response": "", "actions": [],
        }), "interaction_state")
        self._best_effort(
            lambda: self.facade.set_led_rgb("FaceLeds", 0.0, 0.0, 1.0),
            "ready_led",
        )
        self._best_effort(
            lambda: self.send_all("interaction_cancelled", {"reason": reason}),
            "cancel_event",
        )

    def start(self, now_ms):
        self.interaction_id = str(self.interaction_id_factory())
        try:
            self.interaction_store.save({
                "interaction_id": self.interaction_id,
                "phase": "listening",
                "transcript": "", "response": "", "actions": [],
            })
            self.capture.start(self.interaction_id, now_ms)
            self.facade.set_led_rgb("FaceLeds", 0.0, 1.0, 0.0)
            return True
        except Exception as error:
            self.recover("capture_start_failed", now_ms, error)
            return False

    def finish(self, now_ms):
        try:
            result = self.capture.stop(now_ms)
            self.interaction_store.save({
                "interaction_id": self.interaction_id or "",
                "phase": "processing",
                "transcript": "", "response": "", "actions": [],
            })
            print("GATEWAY audio_ready duration_ms={}".format(result["duration_ms"]))
            print("GATEWAY audio_diagnostics={}".format(result["audio_diagnostics"]))
            self.facade.set_led_rgb("FaceLeds", 1.0, 0.5, 0.0)
            self.send_all("audio_result", result)
            return True
        except Exception as error:
            self.recover("capture_finish_failed", now_ms, error)
            return False


def _load_runtime():
    from naoqi import ALProxy
    from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer
    from nao_facade import NAOFacade
    from action_executor import ActionExecutor
    from audio_capture import AudioCapture
    from interaction_state import InteractionStateStore
    from mode_manager import ModeManager
    from safety_supervisor import SafetySupervisor

    base = os.environ.get("NAO_CONTROL_HOME", "/home/nao/naoControl")
    with open(os.path.join(base, "config", "action_registry.json"), "r") as source:
        registry = json.load(source)
    with open(os.path.join(base, "config", "behavior_registry.json"), "r") as source:
        registry["behaviors"] = json.load(source)["behaviors"]
    secret_path = os.environ.get(
        "NAO_GATEWAY_SECRET_FILE", os.path.join(base, "config", "robot_gateway.secret")
    )
    with open(secret_path, "rb") as source:
        secret = source.read().strip()
    if len(secret) < 32:
        raise RuntimeError("gateway secret must contain at least 32 bytes")

    facade = NAOFacade("127.0.0.1", 9559)
    executor = ActionExecutor(facade, registry)
    safety = SafetySupervisor(facade)
    allowed, reasons = safety.check_intelligent_entry()
    entry_gate = create_entry_gate(safety, secret)
    manager = ModeManager(
        initial_mode="WEB_CONTROL",
        entry_check=entry_gate,
    )
    memory = ALProxy("ALMemory", "127.0.0.1", 9559)
    capture = AudioCapture(ALProxy("ALAudioRecorder", "127.0.0.1", 9559))
    clients = set()
    interaction_store = InteractionStateStore()

    def system_handler(name):
        events = manager.handle_system(name, int(time.time() * 1000))
        write_mode()
        if name == "TURN_FINISHED":
            facade.set_led_rgb("FaceLeds", 0.0, 0.0, 1.0)
        for event in events:
            send_all("mode_event", event.as_dict())

    core = GatewayCore(
        secret, executor, system_handler=system_handler,
        interaction_handler=interaction_store.save,
    )

    def send_all(message_type, payload):
        encoded = json.dumps(core.envelope(message_type, payload))
        for client in list(clients):
            try:
                client.sendMessage(encoded)
            except Exception:
                clients.discard(client)

    class GatewaySocket(WebSocket):
        def handleConnected(self):
            clients.add(self)
            print("GATEWAY pc_connected clients={}".format(len(clients)))
            self.sendMessage(json.dumps(core.envelope("hello_result", {
                "status": "ready", "mode": manager.mode, "entry_reasons": reasons
            })))

        def handleMessage(self):
            try:
                incoming = json.loads(self.data)
            except Exception:
                incoming = {}
            self.sendMessage(json.dumps(core.handle_message(incoming)))

        def handleClose(self):
            clients.discard(self)
            print("GATEWAY pc_disconnected clients={}".format(len(clients)))

    def write_mode():
        path = os.environ.get("NAO_CONTROL_MODE_FILE", "/tmp/nao_control_mode.json")
        temporary = path + ".tmp"
        with open(temporary, "w") as output:
            json.dump({"mode": manager.mode, "updated_at_ms": core.now_ms()}, output)
        os.rename(temporary, path)

    capture_controller = CaptureController(
        manager, capture, interaction_store, facade, send_all
    )

    def poll_bumpers_once():
        now = core.now_ms()
        left = memory.getData("LeftBumperPressed") == 1.0
        right = memory.getData("RightBumperPressed") == 1.0
        events = manager.handle_bumper(left, right, now)
        for event in events:
            print("GATEWAY event={} mode={}".format(event.name, event.mode))
            if event.name == "MODE_ENTER_REQUESTED":
                facade.set_led_rgb("FaceLeds", 0.0, 0.0, 1.0)
                facade.say("Modo inteligente listo")
            elif event.name == "MODE_ENTRY_REJECTED":
                facade.set_led_rgb("FaceLeds", 1.0, 0.0, 0.0)
                if entry_gate.last_reason == "pc_target_not_configured":
                    facade.say("Configura la dirección del computador en el menú de red")
                elif entry_gate.last_reason == "pc_gateway_unavailable":
                    facade.say("No pude iniciar el sistema inteligente en el computador")
                else:
                    facade.say("No es seguro iniciar el modo inteligente")
            elif event.name == "MODE_EXIT_REQUESTED":
                capture.cancel()
                facade.set_led_rgb("FaceLeds", 1.0, 1.0, 1.0)
                facade.say("Modo control web")
            elif event.name == "CAPTURE_STARTED":
                capture_controller.start(now)
            elif event.name == "CAPTURE_FINISHED":
                capture_controller.finish(now)
            elif event.name == "EMERGENCY_REQUESTED":
                capture.cancel()
                safety.emergency_stop("both_bumpers")
                facade.set_led_rgb("FaceLeds", 1.0, 0.0, 0.0)
                send_all("emergency", {"reason": "both_bumpers"})
            write_mode()
            send_all("mode_event", event.as_dict())
        if manager.mode == "CAPTURING" and capture.started_at_ms is not None:
            if now - capture.started_at_ms >= AudioCapture.MAX_DURATION_MS:
                capture_controller.recover("audio_limit", now)
                write_mode()

    def bumper_loop():
        write_mode()
        while True:
            try:
                poll_bumpers_once()
            except Exception as error:
                print("GATEWAY bumper_loop_error error={}: {}".format(
                    type(error).__name__, error
                ))
                if manager.mode in ("CAPTURING", "PROCESSING", "RESPONDING"):
                    capture_controller.recover("bumper_runtime_failed", core.now_ms(), error)
                    write_mode()
            time.sleep(0.05)

    thread = threading.Thread(target=bumper_loop)
    thread.daemon = True
    thread.start()
    return SimpleWebSocketServer("", 6674, GatewaySocket)


def main():
    server = _load_runtime()
    print("NAO Nemotron gateway listening on 0.0.0.0:6674")
    server.serveforever()


if __name__ == "__main__":
    main()

import base64
import io
import json
import wave

from nao.scripts.runtime.intelligence.audio_capture import AudioCapture, audio_diagnostics
from nao.scripts.runtime.intelligence.gateway_server import GatewayCore, create_entry_gate
from nao.scripts.runtime.intelligence.protocol import ReplayGuard, sign_envelope


class FakeRecorder(object):
    def __init__(self, files):
        self.calls = []
        self.files = files

    def startMicrophonesRecording(self, path, kind, rate, channels):
        self.calls.append(("start", path, kind, rate, channels))

    def stopMicrophonesRecording(self):
        self.calls.append(("stop",))
        self.files.data = b"RIFF-test-wav"


class FakeFiles(object):
    def __init__(self):
        self.data = None

    def read(self, path):
        return self.data

    def remove(self, path):
        self.data = None


class FakeExecutor(object):
    def __init__(self):
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return {"status": "completed", "action": command["action"]}


def unsigned(message_type, message_id, payload):
    return {
        "protocol_version": 1,
        "message_type": message_type,
        "message_id": message_id,
        "issued_at_ms": 1000,
        "expires_at_ms": 6000,
        "payload": payload,
    }


def test_audio_capture_returns_bounded_wav_bytes():
    files = FakeFiles()
    recorder = FakeRecorder(files)
    capture = AudioCapture(recorder, files=files, path="/tmp/test.wav")
    capture.start("interaction-1", now_ms=100)

    result = capture.stop(now_ms=900)

    assert result["interaction_id"] == "interaction-1"
    assert result["duration_ms"] == 800
    assert base64.b64decode(result["audio_b64"]) == b"RIFF-test-wav"
    assert files.data is None


def test_audio_diagnostics_reports_wav_metadata_without_retaining_audio():
    buffer = io.BytesIO()
    wav = wave.open(buffer, "wb")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(16000)
    wav.writeframes(b"\x01\x00" * 160)
    wav.close()

    details = audio_diagnostics(buffer.getvalue())

    assert details == {
        "bytes": len(buffer.getvalue()), "channels": 1, "sample_rate_hz": 16000,
        "sample_width_bytes": 2, "frames": 160, "rms": 1,
    }


def test_unsigned_command_is_rejected_without_execution():
    executor = FakeExecutor()
    core = GatewayCore(b"shared-secret", executor, now_ms=lambda: 1000)

    result = core.handle_message({"message_type": "command"})

    assert result["payload"]["status"] == "rejected"
    assert executor.commands == []


def test_signed_command_executes_allowlisted_action(capsys):
    executor = FakeExecutor()
    core = GatewayCore(b"shared-secret", executor, now_ms=lambda: 1000)
    envelope = sign_envelope(
        unsigned("command", "message-1", {"action": "say", "arguments": {"text": "Hola"}}),
        b"shared-secret",
    )

    result = core.handle_message(envelope)

    assert result["payload"]["status"] == "completed"
    assert executor.commands == [{"action": "say", "arguments": {"text": "Hola"}}]
    assert "GATEWAY message=command status=completed" in capsys.readouterr().out


def test_rejected_command_logs_rejection_reason(capsys):
    class RejectingExecutor(object):
        def execute(self, command):
            return {"status": "rejected", "reason": "invalid_posture"}

    core = GatewayCore(b"shared-secret", RejectingExecutor(), now_ms=lambda: 1000)
    envelope = sign_envelope(
        unsigned("command", "message-rejected", {"action": "set_posture", "arguments": {}}),
        b"shared-secret",
    )

    result = core.handle_message(envelope)

    assert result["payload"]["reason"] == "invalid_posture"
    assert "GATEWAY message=command status=rejected reason=invalid_posture" in capsys.readouterr().out


def test_heartbeat_has_a_distinct_result_type():
    executor = FakeExecutor()
    core = GatewayCore(b"shared-secret", executor, now_ms=lambda: 1000)
    envelope = sign_envelope(
        unsigned("heartbeat", "heartbeat-1", {}), b"shared-secret"
    )

    result = core.handle_message(envelope)

    assert result["message_type"] == "heartbeat_result"
    assert result["payload"]["status"] == "ok"
    assert executor.commands == []


def test_turn_finished_invokes_system_handler():
    events = []
    core = GatewayCore(
        b"shared-secret", FakeExecutor(), now_ms=lambda: 1000,
        system_handler=lambda name: events.append(name),
    )
    envelope = sign_envelope(
        unsigned("turn_finished", "turn-1", {}), b"shared-secret"
    )

    result = core.handle_message(envelope)

    assert result["message_type"] == "event_result"
    assert result["payload"]["status"] == "ok"
    assert events == ["TURN_FINISHED"]


def test_gateway_server_entry_gate_uses_persisted_target_and_remote_launcher(tmp_path):
    target = tmp_path / "target.json"
    bundle = tmp_path / "bundle.tar.gz"
    target.write_text('{"pc_ip":"192.168.10.25"}', encoding="utf-8")
    bundle.write_bytes(b"bundle")
    requests = []

    class Safety:
        def check_intelligent_entry(self):
            return True, []

    def transport(*args):
        requests.append(args)
        request = json.loads(args[1])
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

    gate = create_entry_gate(
        Safety(),
        b"x" * 32,
        target_path=str(target),
        bundle_path=str(bundle),
        transport=transport,
        now_ms=lambda: 1000,
    )

    assert gate() is True
    assert requests[0][0] == "http://192.168.10.25:6676/start"

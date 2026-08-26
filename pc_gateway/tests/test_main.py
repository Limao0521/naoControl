import pytest
import asyncio
from pathlib import Path

from nao_gateway import main as main_module
from nao_gateway.config import GatewaySettings


def test_load_registry_merges_behavior_catalog_from_sibling_config():
    registry = main_module.load_registry(
        Path("config/action_registry.json"),
    )
    assert sorted(registry["behaviors"]) == [
        "dance_gangnam", "dance_macarena", "dance_siu", "no",
        "play_saxophone", "taichi", "thinking", "wave", "yes",
    ]

    host = main_module.AgentHost(None, None, lambda: None, registry)
    run_behavior = next(tool for tool in host.tool_schemas() if tool["name"] == "run_behavior")
    assert run_behavior["constraints"]["allowed_behavior_ids"] == sorted(registry["behaviors"])


class BrokenHost(object):
    async def handle_audio(self, payload):
        raise TimeoutError("model timeout")


class FragileRobot(object):
    def __init__(self):
        self.calls = []

    async def execute(self, action, arguments):
        self.calls.append((action, arguments))
        raise ConnectionError("robot disconnected")

    async def complete_turn(self):
        self.calls.append(("complete_turn", {}))
        raise ConnectionError("robot disconnected")


@pytest.mark.asyncio
async def test_failed_interaction_does_not_crash_when_robot_disconnects(caplog):
    robot = FragileRobot()

    await main_module.handle_audio_result(robot, BrokenHost(), {"audio_b64": ""})

    assert robot.calls == [
        ("say", {"text": "No pude procesar la solicitud."}),
        ("complete_turn", {}),
    ]
    assert "Interaction failed: TimeoutError" in caplog.text
    assert "Fallback speech failed: ConnectionError" in caplog.text
    assert "Turn completion failed: ConnectionError" in caplog.text


@pytest.mark.asyncio
async def test_connection_manager_reconnects_after_robot_session_is_lost():
    class StopAfterReconnect(BaseException):
        pass

    class ReconnectingRobot(object):
        def __init__(self):
            self.events = asyncio.Queue()
            self.connect_count = 0
            self.close_count = 0

        async def connect(self):
            self.connect_count += 1
            if self.connect_count == 2:
                raise StopAfterReconnect()

        async def receive_forever(self):
            await self.events.put(("connection_lost", {"reason": "test disconnect"}))

        async def heartbeat_forever(self):
            await asyncio.Future()

        async def close(self):
            self.close_count += 1

    robot = ReconnectingRobot()

    with pytest.raises(StopAfterReconnect):
        await main_module.maintain_robot_connection(
            robot, object(), retry_delay=0, sleep=lambda delay: asyncio.sleep(0)
        )

    assert robot.connect_count == 2
    assert robot.close_count == 2


@pytest.mark.asyncio
async def test_run_gateway_does_not_start_network_administration(monkeypatch, tmp_path):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text("{}", encoding="utf-8")
    (tmp_path / "behavior_registry.json").write_text(
        '{"behaviors": {}}', encoding="utf-8"
    )
    settings = GatewaySettings.from_env(
        {
            "NVIDIA_API_KEY": "test-nvidia-key",
            "NAO_GATEWAY_SECRET": "test-shared-secret-with-enough-entropy",
            "NAO_GATEWAY_URL": "ws://169.254.1.2:6674",
        }
    )
    calls = []

    class FakeRobot:
        def __init__(self, *args):
            calls.append("robot_created")

        async def publish_interaction_state(self, payload):
            calls.append("state_published")

    class FakeNemotron:
        def __init__(self, *args):
            calls.append("nemotron_created")

        async def close(self):
            calls.append("nemotron_closed")

    monkeypatch.setattr(main_module, "RobotClient", FakeRobot)
    monkeypatch.setattr(main_module, "NemotronClient", FakeNemotron)
    monkeypatch.setattr(main_module, "AgentHost", lambda *args, **kwargs: object())

    async def fake_robot_connection(robot, host):
        calls.append("robot_service")

    monkeypatch.setattr(main_module, "maintain_robot_connection", fake_robot_connection)

    await main_module.run_gateway(settings, Path(registry_path))

    assert calls == ["robot_created", "nemotron_created", "robot_service", "nemotron_closed"]


@pytest.mark.asyncio
async def test_provider_config_event_activates_router_and_reports_status_to_robot():
    handler = getattr(main_module, "handle_provider_config", None)
    assert handler is not None, "provider config handler is missing"
    published = []

    class Robot:
        async def publish_provider_status(self, payload):
            published.append(payload)

    class Router:
        async def activate(self, name):
            assert name == "gemma_local"
            return {"active": name, "healthy": True, "error": ""}

    await handler(Robot(), Router(), {"selected": "gemma_local"})

    assert published == [{"active": "gemma_local", "healthy": True, "error": ""}]

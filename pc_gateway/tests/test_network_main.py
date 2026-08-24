from __future__ import annotations

import asyncio

import pytest

from nao_gateway import network_main
from nao_gateway.config import NetworkBrokerSettings


def test_network_process_loads_only_its_own_environment_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NVIDIA_API_KEY=must-not-be-loaded\n"
        "NAO_NETWORK_HOST=169.254.197.40\n"
        "NAO_SSH_KEY=C:/keys/nao\n",
        encoding="utf-8",
    )

    environment = network_main.load_network_environment(
        env_file, {"NVIDIA_API_KEY": "also-not-loaded", "NAO_SSH_USER": "nao"}
    )

    assert environment == {
        "NAO_NETWORK_HOST": "169.254.197.40",
        "NAO_SSH_KEY": "C:/keys/nao",
        "NAO_SSH_USER": "nao",
    }


@pytest.mark.asyncio
async def test_standalone_network_broker_binds_loopback_and_cleans_up(tmp_path):
    key_path = tmp_path / "nao_key"
    key_path.write_text("test-key-placeholder", encoding="utf-8")
    settings = NetworkBrokerSettings.from_env(
        {"NAO_NETWORK_HOST": "169.254.197.40", "NAO_SSH_KEY": str(key_path)}
    )
    calls = []

    class FakeRunner:
        def __init__(self, app):
            calls.append(("runner", app))

        async def setup(self):
            calls.append(("setup",))

        async def cleanup(self):
            calls.append(("cleanup",))

    class FakeSite:
        def __init__(self, runner, host, port):
            calls.append(("site", host, port))

        async def start(self):
            calls.append(("start",))

    stop_event = asyncio.Event()
    stop_event.set()

    await network_main.run_network_broker(
        settings,
        stop_event=stop_event,
        runner_factory=FakeRunner,
        site_factory=FakeSite,
    )

    assert ("site", "127.0.0.1", 6675) in calls
    assert calls[-1] == ("cleanup",)

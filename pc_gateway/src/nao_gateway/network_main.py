"""Standalone PC-side broker for NAO network administration."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Mapping

from aiohttp import web
from dotenv import dotenv_values

from .config import NetworkBrokerSettings
from .network_broker import SshNetworkTransport, create_network_app


logger = logging.getLogger(__name__)
NETWORK_ENVIRONMENT_KEYS = frozenset(
    {
        "NAO_NETWORK_HOST",
        "NAO_GATEWAY_URL",
        "NAO_NETWORK_BROKER_PORT",
        "NAO_SSH_USER",
        "NAO_SSH_KEY",
        "NAO_NETWORK_ALLOWED_ORIGINS",
    }
)


def load_network_environment(
    env_file: str | Path, environ: Mapping[str, str]
) -> dict[str, str]:
    """Load only network settings; never inject cloud secrets into this process."""
    loaded = dotenv_values(env_file)
    environment = {
        key: value
        for key, value in loaded.items()
        if key in NETWORK_ENVIRONMENT_KEYS and value is not None
    }
    environment.update(
        {key: value for key, value in environ.items() if key in NETWORK_ENVIRONMENT_KEYS}
    )
    return environment


async def run_network_broker(
    settings: NetworkBrokerSettings,
    *,
    stop_event: asyncio.Event | None = None,
    runner_factory=web.AppRunner,
    site_factory=web.TCPSite,
) -> None:
    """Serve the loopback-only administrative API until cancelled."""
    transport = SshNetworkTransport(
        settings.nao_ssh_user,
        settings.nao_ssh_host,
        settings.nao_ssh_key,
    )
    runner = runner_factory(
        create_network_app(transport, settings.network_allowed_origins)
    )
    await runner.setup()
    try:
        site = site_factory(runner, settings.network_broker_host, settings.network_broker_port)
        await site.start()
        logger.info(
            "NAO network broker listening on http://%s:%s",
            settings.network_broker_host,
            settings.network_broker_port,
        )
        if stop_event is None:
            await asyncio.Future()
        else:
            await stop_event.wait()
    finally:
        await runner.cleanup()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    environment = load_network_environment(args.env_file, os.environ)
    asyncio.run(run_network_broker(NetworkBrokerSettings.from_env(environment)))


if __name__ == "__main__":
    main()

"""Authenticated WebSocket client for the robot-local gateway."""
from __future__ import annotations

import asyncio
import json
import time
import uuid

import websockets

from .protocol import ReplayGuard, sign_envelope, verify_envelope


class RobotClient:
    def __init__(self, url: str, secret: bytes, now_ms=None) -> None:
        self.url = url
        self.secret = secret
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.replay_guard = ReplayGuard(1000)
        self.socket = None
        self.events: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
        self.results: asyncio.Queue[dict] = asyncio.Queue()
        self.command_lock = asyncio.Lock()

    def _envelope(self, message_type: str, payload: dict) -> dict:
        now = self.now_ms()
        return sign_envelope({
            "protocol_version": 1,
            "message_type": message_type,
            "message_id": str(uuid.uuid4()),
            "issued_at_ms": now,
            "expires_at_ms": now + 10000,
            "payload": payload,
        }, self.secret)

    def command_envelope(self, action: str, arguments: dict) -> dict:
        return self._envelope("command", {"action": action, "arguments": arguments})

    def turn_finished_envelope(self) -> dict:
        return self._envelope("turn_finished", {})

    def interaction_update_envelope(self, payload: dict) -> dict:
        return self._envelope("interaction_update", payload)

    def ingest(self, raw: str) -> tuple[str, dict]:
        envelope = json.loads(raw)
        payload = verify_envelope(envelope, self.secret, self.now_ms(), self.replay_guard)
        return envelope["message_type"], payload

    async def connect(self) -> None:
        self.events = asyncio.Queue()
        self.results = asyncio.Queue()
        self.socket = await websockets.connect(self.url, max_size=12 * 1024 * 1024)

    async def receive_forever(self) -> None:
        if self.socket is None:
            raise RuntimeError("robot client is not connected")
        try:
            async for raw in self.socket:
                message_type, payload = self.ingest(raw)
                if message_type == "command_result":
                    await self.results.put(payload)
                else:
                    await self.events.put((message_type, payload))
        except Exception as error:
            await self.events.put(("connection_lost", {
                "error_type": type(error).__name__, "reason": str(error),
            }))
        else:
            await self.events.put(("connection_lost", {
                "error_type": "ConnectionClosed", "reason": "robot closed the connection",
            }))

    async def execute(self, action: str, arguments: dict) -> dict:
        if self.socket is None:
            raise RuntimeError("robot client is not connected")
        async with self.command_lock:
            await self.socket.send(json.dumps(self.command_envelope(action, arguments)))
            return await asyncio.wait_for(self.results.get(), timeout=20)

    async def heartbeat_forever(self) -> None:
        while self.socket is not None:
            await self.socket.send(json.dumps(self._envelope("heartbeat", {})))
            await asyncio.sleep(1)

    async def complete_turn(self) -> None:
        if self.socket is None:
            raise RuntimeError("robot client is not connected")
        await self.socket.send(json.dumps(self.turn_finished_envelope()))

    async def publish_interaction_state(self, payload: dict) -> None:
        if self.socket is None:
            raise RuntimeError("robot client is not connected")
        await self.socket.send(json.dumps(self.interaction_update_envelope(payload)))

    async def close(self) -> None:
        if self.socket is not None:
            await self.socket.close()
            self.socket = None

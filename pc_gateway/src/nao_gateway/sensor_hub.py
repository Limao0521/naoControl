"""Acquire a bounded current frame from the NAO MJPEG stream."""
from __future__ import annotations

import httpx


def extract_first_jpeg(data: bytes) -> bytes | None:
    start = data.find(b"\xff\xd8")
    if start < 0:
        return None
    end = data.find(b"\xff\xd9", start + 2)
    if end < 0:
        return None
    return data[start:end + 2]


async def fetch_latest_jpeg(url: str, limit: int = 2 * 1024 * 1024) -> bytes:
    buffer = bytearray()
    async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3)) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                buffer.extend(chunk)
                frame = extract_first_jpeg(bytes(buffer))
                if frame is not None:
                    return frame
                if len(buffer) > limit:
                    raise ValueError("MJPEG frame exceeded size limit")
    raise ValueError("MJPEG stream ended before a complete frame")

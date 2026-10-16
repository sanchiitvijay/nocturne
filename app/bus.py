"""In-process publish/subscribe used for the live stream (Server-Sent Events).

Publishers may run in worker threads; delivery is marshalled onto the event loop.
For multi-process deployments swap this module for Redis pub/sub — the interface stays the same.
"""
from __future__ import annotations

import asyncio
import json


class Bus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def _deliver(self, message: str) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                continue  # slow client: drop rather than block everyone
            queue.put_nowait(message)

    def publish(self, topic: str, payload: dict) -> None:
        if not self._loop:
            return
        message = f"event: {topic}\ndata: {json.dumps(payload, default=str)}\n\n"
        self._loop.call_soon_threadsafe(self._deliver, message)

    @property
    def listeners(self) -> int:
        return len(self._subscribers)


bus = Bus()

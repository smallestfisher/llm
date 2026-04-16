from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ThreadSubscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]]


class ThreadEventService:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[ThreadSubscriber]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, thread_public_id: str) -> ThreadSubscriber:
        subscriber = ThreadSubscriber(loop=asyncio.get_running_loop(), queue=asyncio.Queue())
        with self._lock:
            self._subscribers[thread_public_id].append(subscriber)
        return subscriber

    def unsubscribe(self, thread_public_id: str, subscriber: ThreadSubscriber) -> None:
        with self._lock:
            subscribers = self._subscribers.get(thread_public_id, [])
            if subscriber in subscribers:
                subscribers.remove(subscriber)
            if not subscribers and thread_public_id in self._subscribers:
                del self._subscribers[thread_public_id]

    def publish(self, thread_public_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(thread_public_id, []))
        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, payload)


thread_event_service = ThreadEventService()

from __future__ import annotations

import fnmatch
import logging
import threading
import uuid
from collections.abc import Callable  # noqa: TC003  -- usado solo en type hints, con annotations future
from dataclasses import dataclass
from typing import Any

from motor.events.event import Event, EventPayload

log = logging.getLogger("ura.eventbus")


@dataclass
class _Subscriber:
    id: str
    topic: str
    callback: Callable[[Event], Any]
    pattern: bool = False
    priority: int = 0


class EventBus:
    def __init__(self) -> None:
        self._exact: dict[str, list[_Subscriber]] = {}
        self._patterns: list[_Subscriber] = []
        self._lock = threading.RLock()

    def publish(
        self,
        topic: str,
        payload: EventPayload,
        *,
        source: str = "system",
    ) -> None:
        event = Event(topic=topic, payload=payload, source=source)
        subs = self._get_subscribers(topic)
        for sub in subs:
            try:
                sub.callback(event)
            except Exception:
                log.exception("[eventbus] Error en subscriber %s para tópico %s", sub.id, topic)

    def publish_async(
        self,
        topic: str,
        payload: EventPayload,
        *,
        source: str = "system",
    ) -> None:
        t = threading.Thread(
            target=self.publish,
            args=(topic, payload),
            kwargs={"source": source},
            daemon=True,
        )
        t.start()

    def subscribe(
        self,
        topic: str,
        callback: Callable[[Event], Any],
        *,
        pattern: bool = False,
        priority: int = 0,
    ) -> str:
        sub_id = uuid.uuid4().hex[:12]
        sub = _Subscriber(id=sub_id, topic=topic, callback=callback, pattern=pattern, priority=priority)
        with self._lock:
            if pattern:
                self._patterns.append(sub)
            else:
                self._exact.setdefault(topic, []).append(sub)
                self._exact[topic].sort(key=lambda s: s.priority, reverse=True)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        with self._lock:
            for topic, subs in list(self._exact.items()):
                for i, s in enumerate(subs):
                    if s.id == sub_id:
                        subs.pop(i)
                        if not subs:
                            del self._exact[topic]
                        return True
            for i, s in enumerate(self._patterns):
                if s.id == sub_id:
                    self._patterns.pop(i)
                    return True
        return False

    def emit_sync(
        self,
        topic: str,
        payload: EventPayload,
        *,
        source: str = "system",
    ) -> list[Any]:
        event = Event(topic=topic, payload=payload, source=source)
        subs = self._get_subscribers(topic)
        responses: list[Any] = []
        for sub in subs:
            try:
                result = sub.callback(event)
                responses.append(result)
            except Exception:
                log.exception("[eventbus] Error en emit_sync subscriber %s para %s", sub.id, topic)
                responses.append(None)
        return responses

    def count(self, topic: str | None = None) -> int:
        with self._lock:
            if topic:
                exact = len(self._exact.get(topic, []))
                pattern = sum(1 for s in self._patterns if fnmatch.fnmatch(topic, s.topic))
                return exact + pattern
            exact = sum(len(subs) for subs in self._exact.values())
            return exact + len(self._patterns)

    def reset(self) -> None:
        with self._lock:
            self._exact.clear()
            self._patterns.clear()

    def _get_subscribers(self, topic: str) -> list[_Subscriber]:
        with self._lock:
            exact = list(self._exact.get(topic, []))
            pattern = [s for s in self._patterns if fnmatch.fnmatch(topic, s.topic)]
            combined = exact + pattern
            combined.sort(key=lambda s: s.priority, reverse=True)
        return combined

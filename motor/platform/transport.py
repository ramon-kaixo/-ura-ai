"""Transport abstraction + LocalTransport reference implementation.

Concurrency contract for LocalTransport:
- send() and request() are thread-safe (lock-protected).
- receive() is thread-safe.
- register() should be called before concurrent access.
- The transport is NOT designed for multi-producer/multi-consumer
  at scale. It is a reference implementation for testing.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from motor.platform.errors import ProtocolException

log = logging.getLogger("ura.platform.transport")
from motor.platform.models import ProtocolEnvelope

if TYPE_CHECKING:
    from motor.platform.metrics import PlatformMetrics


class Transport(ABC):
    @abstractmethod
    async def send(self, envelope: ProtocolEnvelope) -> None:
        ...

    @abstractmethod
    async def receive(self) -> ProtocolEnvelope:
        ...

    @abstractmethod
    async def request(self, envelope: ProtocolEnvelope) -> ProtocolEnvelope:
        ...


class LocalTransport(Transport):
    """In-process transport. Reference implementation. Thread-safe.

    Optionally accepts a PlatformMetrics instance for ADR-028-10
    metrics instrumentation.
    """

    def __init__(self, metrics: PlatformMetrics | None = None) -> None:
        self._handlers: dict[str, Callable[[ProtocolEnvelope], ProtocolEnvelope]] = {}
        self._received: list[ProtocolEnvelope] = []
        self._lock = threading.Lock()
        self._metrics = metrics

    def register(self, message_type: str, handler: Callable[[ProtocolEnvelope], ProtocolEnvelope]) -> None:
        self._handlers[message_type] = handler

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
            self._received.clear()

    async def send(self, envelope: ProtocolEnvelope) -> None:
        if not isinstance(envelope, ProtocolEnvelope):
            raise ProtocolException("send() requires a ProtocolEnvelope")
        with self._lock:
            self._received.append(envelope)
        if self._metrics is not None:
            try:
                size = len(envelope.payload) if envelope.payload else 0
                self._metrics.record_sent(
                    source=envelope.routing.source,
                    destination=envelope.routing.destination,
                    message_kind=envelope.routing.message_kind.value,
                    size_bytes=size,
                    duration_ms=0.0,
                )
            except Exception:
                log.debug("Metrics record_sent failed", exc_info=True)

    async def receive(self) -> ProtocolEnvelope:
        with self._lock:
            if not self._received:
                raise RuntimeError("No messages available")
            env = self._received.pop(0)
        if self._metrics is not None:
            try:
                size = len(env.payload) if env.payload else 0
                self._metrics.record_received(
                    source=env.routing.source,
                    destination=env.routing.destination,
                    message_kind=env.routing.message_kind.value,
                    size_bytes=size,
                )
            except Exception:
                log.debug("Metrics record_received failed", exc_info=True)
        return env

    async def request(self, envelope: ProtocolEnvelope) -> ProtocolEnvelope:
        with self._lock:
            self._received.append(envelope)
            handler = self._handlers.get(envelope.routing.message_type)
            if handler is None:
                if self._metrics is not None:
                    try:
                        self._metrics.record_error(
                            source=envelope.routing.source,
                            destination=envelope.routing.destination,
                            error_code="no_handler",
                        )
                    except Exception:
                        log.debug("Metrics record_error failed", exc_info=True)
                raise RuntimeError(f"No handler for {envelope.routing.message_type}")
            return handler(envelope)

"""Transport abstraction + LocalTransport reference implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from motor.platform.models import ProtocolEnvelope


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
    """In-process transport. No serialization. Reference implementation."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[ProtocolEnvelope], ProtocolEnvelope]] = {}
        self._received: list[ProtocolEnvelope] = []

    def register(self, message_type: str, handler: Callable[[ProtocolEnvelope], ProtocolEnvelope]) -> None:
        self._handlers[message_type] = handler

    def clear(self) -> None:
        self._handlers.clear()
        self._received.clear()

    async def send(self, envelope: ProtocolEnvelope) -> None:
        self._received.append(envelope)

    async def receive(self) -> ProtocolEnvelope:
        if not self._received:
            raise RuntimeError("No messages available")
        return self._received.pop(0)

    async def request(self, envelope: ProtocolEnvelope) -> ProtocolEnvelope:
        self._received.append(envelope)
        handler = self._handlers.get(envelope.routing.message_type)
        if handler is None:
            raise RuntimeError(f"No handler for {envelope.routing.message_type}")
        return handler(envelope)

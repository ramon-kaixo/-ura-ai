"""Tests de event_bus y notifier."""

from core.event_bus import AsyncEventBus, replay_events


def test_event_bus_imports() -> None:
    assert callable(replay_events)


def test_async_event_bus_creates() -> None:
    bus = AsyncEventBus()
    assert bus is not None
    assert bus._suscriptores == {}


def test_async_event_bus_suscribir() -> None:
    import asyncio

    bus = AsyncEventBus()

    async def _run() -> None:
        called = []

        async def callback(data) -> None:
            called.append(data)

        await bus.suscribir("test_event", callback)
        assert "test_event" in bus._suscriptores
        assert len(bus._suscriptores["test_event"]) == 1

    asyncio.run(_run())

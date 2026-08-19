"""Tests de cobertura para knowledge/engine/eventbus.py."""

from __future__ import annotations

from knowledge.engine.eventbus import (
    ArchiveCompleted,
    CompileCompleted,
    Event,
    EventBus,
    MemoryCreated,
    MetadataExtracted,
    SearchPerformed,
    get_bus,
    set_bus,
)

EVENT = CompileCompleted(reason="test", documents_changed=1, documents_total=2, errors=0, correlation_id="c1")


def test_subscribe_y_publish() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(CompileCompleted, lambda e: seen.append(e))
    bus.publish(EVENT)
    assert seen == [EVENT]


def test_no_duplicados() -> None:
    bus = EventBus()
    seen: list[Event] = []

    def _h(e: Event) -> None:
        seen.append(e)

    bus.subscribe(CompileCompleted, _h)
    bus.subscribe(CompileCompleted, _h)
    bus.publish(EVENT)
    assert len(seen) == 1


def test_unsubscribe() -> None:
    bus = EventBus()
    seen: list[Event] = []

    def _h(e: Event) -> None:
        seen.append(e)

    bus.subscribe(CompileCompleted, _h)
    bus.unsubscribe(CompileCompleted, _h)
    bus.publish(EVENT)
    assert seen == []
    bus.unsubscribe(CompileCompleted, _h)  # no-op


def test_tipo_distinto_no_recibe() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(MemoryCreated, lambda e: seen.append(e))
    bus.publish(EVENT)
    assert seen == []


def test_handler_fallo_no_afecta_otros() -> None:
    bus = EventBus()
    seen: list[Event] = []

    def _boom(_: Event) -> None:
        raise RuntimeError("handler roto")

    bus.subscribe(CompileCompleted, _boom)
    bus.subscribe(CompileCompleted, lambda e: seen.append(e))
    bus.publish(EVENT)
    assert len(seen) == 1


def test_clear() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(CompileCompleted, lambda e: seen.append(e))
    bus.clear()
    bus.publish(EVENT)
    assert seen == []


def test_multiples_suscriptores() -> None:
    bus = EventBus()
    a: list[Event] = []
    b: list[Event] = []
    bus.subscribe(CompileCompleted, lambda e: a.append(e))
    bus.subscribe(CompileCompleted, lambda e: b.append(e))
    bus.publish(EVENT)
    assert a == [EVENT]
    assert b == [EVENT]


def test_get_bus_singleton() -> None:
    b1 = get_bus()
    b2 = get_bus()
    assert b1 is b2


def test_set_bus() -> None:
    nuevo = EventBus()
    previo = get_bus()
    try:
        set_bus(nuevo)
        assert get_bus() is nuevo
    finally:
        set_bus(previo)


def test_eventos_restantes() -> None:
    e1 = ArchiveCompleted(kind="source", commit="c", file_count=1)
    e2 = SearchPerformed(query="q", docs_returned=3)
    e3 = MetadataExtracted(asset_id="a", asset_type="markdown", extractor="md", success=True, duration_ms=1.0)
    assert e1.kind == "source"
    assert e2.docs_returned == 3
    assert e3.extractor == "md"
    assert issubclass(CompileCompleted, Event)
    assert issubclass(MemoryCreated, Event)
    assert issubclass(MetadataExtracted, Event)

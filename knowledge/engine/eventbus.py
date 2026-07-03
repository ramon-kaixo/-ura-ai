"""Event Bus — desacoplamiento publish/subscribe interno.

Elimina llamadas directas entre compile → archive → audit → metrics.
Cada suscriptor maneja su evento independientemente.

Uso:
    bus = EventBus()
    bus.subscribe(CompileCompleted, archive_handler)
    bus.subscribe(CompileCompleted, audit_handler)
    bus.publish(CompileCompleted(result))  # → ambos handlers
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.engine.ontology.internal import AssetType

log = logging.getLogger("ura.knowledge.eventbus")


# ── Event types ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Event:
    """Base class for all events."""
    pass


@dataclass(frozen=True)
class CompileCompleted(Event):
    """Publicado cuando un compile termina exitosamente."""
    reason: str
    documents_changed: int
    documents_total: int
    errors: int
    correlation_id: str = ""


@dataclass(frozen=True)
class MemoryCreated(Event):
    """Publicado cuando se crea un registro de memoria."""
    memory_id: str
    kind: str
    title: str
    related_assets: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryUpdated(Event):
    """Publicado cuando se actualiza un registro de memoria."""
    memory_id: str
    kind: str


@dataclass(frozen=True)
class MemoryLinked(Event):
    """Publicado cuando se vincula un asset a un registro de memoria."""
    memory_id: str
    asset_id: str


@dataclass(frozen=True)
class ArchiveCompleted(Event):
    """Publicado cuando un archive termina."""
    kind: str
    commit: str
    file_count: int
    correlation_id: str = ""


@dataclass(frozen=True)
class SearchPerformed(Event):
    """Publicado cuando se realiza una búsqueda."""
    query: str
    docs_returned: int
    correlation_id: str = ""


@dataclass(frozen=True)
class MetadataExtracted(Event):
    """Publicado cuando un extractor completa la extracción de metadatos.

    Fase 6 — Backend Vectorial: el suscriptor vectorial se engancha aquí.
    """
    asset_id: str
    asset_type: AssetType
    extractor: str
    success: bool
    duration_ms: float


# ── Event Bus ──────────────────────────────────────────────────────────────


Handler = Callable[[Event], None]


class EventBus:
    """Publish/subscribe desacoplado.

    Thread-safe. Los handlers se ejecutan en el hilo del publicador
    (síncrono) por ahora. En futura versión podrían ir a un thread pool.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[type[Event], list[Handler]] = {}

    def subscribe(self, event_type: type[Event], handler: Handler) -> None:
        """Registra un handler para un tipo de evento. No permite duplicados."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                log.debug("Subscribed %s to %s", handler.__name__, event_type.__name__)

    def unsubscribe(self, event_type: type[Event], handler: Handler) -> None:
        """Elimina un handler."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h is not handler
                ]

    def publish(self, event: Event) -> None:
        """Publica un evento a todos los suscriptores.

        Cada handler se ejecuta en el hilo actual.
        Si un handler falla, se registra el error pero no afecta a los demás.
        """
        event_type = type(event)
        handlers = list(self._subscribers.get(event_type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                log.error(
                    "Event handler %s failed for %s: %s",
                    handler.__name__, event_type.__name__, exc,
                )

    def clear(self) -> None:
        """Elimina todos los suscriptores (útil en tests)."""
        with self._lock:
            self._subscribers.clear()


# ── Singleton global ──────────────────────────────────────────────────────

_BUS: EventBus | None = None
_BUS_LOCK = threading.Lock()


def get_bus() -> EventBus:
    """Retorna la instancia global del Event Bus."""
    global _BUS
    if _BUS is not None:
        return _BUS
    with _BUS_LOCK:
        if _BUS is not None:
            return _BUS
        _BUS = EventBus()
        return _BUS


def set_bus(bus: EventBus) -> None:
    """Establece la instancia global (útil en tests)."""
    global _BUS
    _BUS = bus

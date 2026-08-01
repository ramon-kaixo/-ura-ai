# ADR-011-02: EventBus con Contratos Tipados

> **Fecha:** 2026-07-05
> **Fase:** 11 (Plataforma)
> **Propósito:** Definir el contrato del bus de eventos interno: tópicos,
> payloads tipados, modos síncrono/asíncrono, filtros y garantías de entrega.
> **Estado:** ✅ Aprobado

## Contexto

Actualmente existen **dos buses de eventos** en el sistema:

1. `core/event_bus.py` — ZeroMQ, usará el agente de consciencia (sin test)
2. `knowledge/engine/eventbus.py` — in-process, usado por Knowledge Engine

Ambos son independientes, con APIs diferentes y sin interoperabilidad. F11
necesita un bus único que:

- Permita a plugins suscribirse a eventos del sistema
- Permita al sistema reaccionar a eventos de plugins
- Soporte tópicos jerárquicos (ej. `plugin.*`, `pipeline.*`)
- Sea tipado (cada tópico tiene un payload predecible)
- No dependa de ZeroMQ (es intraproceso)

Esta ADR define el **contrato** del bus. La implementación se hará tras
la aprobación del contrato.

## Decisión

### 1. Arquitectura

Bus **único in-process** en `motor/events/bus.py`. ZeroMQ (`core/event_bus.py`)
se mantiene como bus externo para comunicación cross-proceso (consciencia). El
bus in-process es el bus **interno del motor**.

```
Plugin → motor/events/bus.py → Subscriptores
         ↑                          |
         |  (re-publish opcional)    |
         +-- core/event_bus.py ------+
             (ZeroMQ, cross-proceso)
```

### 2. API

```python
class EventBus:
    """Bus de eventos interno con tópicos jerárquicos y payloads tipados."""

    def publish(self, topic: str, payload: EventPayload, /) -> None:
        """Publica un evento. Todos los subscriptores reciben el payload."""

    def publish_async(self, topic: str, payload: EventPayload, /) -> None:
        """Publica asíncronamente (no bloquea al emisor)."""

    def subscribe(
        self,
        topic: str,
        callback: Callable[[Event], None],
        *,
        pattern: bool = False,
    ) -> str:
        """Suscribe un callback a un tópico.
        Si pattern=True, topic se interpreta como patrón glob (ej. 'pipeline.*').
        Retorna un subscription_id para desuscripción.
        """

    def unsubscribe(self, subscription_id: str) -> bool:
        """Desuscribe un callback por su id."""

    def emit_sync(self, topic: str, payload: EventPayload) -> list[Any]:
        """Publica síncronamente y espera respuestas de los subscriptores.
        Útil para hooks que pueden modificar el flujo (ej. pre_ingest).
        Retorna lista de respuestas de subscriptores.
        """

    def count(self, topic: str | None = None) -> int:
        """Número de subscriptores. Si topic=None, total del bus."""

    def reset(self) -> None:
        """Elimina todos los subscriptores (para tests/test isolation)."""
```

### 3. Event y EventPayload

```python
@dataclass(frozen=True)
class Event:
    """Envoltorio inmutable de un evento."""
    topic: str
    payload: EventPayload
    timestamp: str  # ISO 8601
    source: str     # nombre del plugin o subsistema que emitió
    id: str         # UUID único para trazabilidad

@dataclass
class EventPayload:
    """Payload base. Subtipos por tópico heredan de esta clase."""
    pass
```

### 4. Tópicos Predefinidos y sus Payloads

| Tópico | Payload | Tipo | Descripción |
|--------|---------|------|-------------|
| `system.started` | `SystemStarted(python_version, ura_version)` | async | Motor iniciado |
| `system.shutdown` | `SystemShutdown(reason)` | sync | Motor apagándose |
| `system.degraded` | `SystemDegraded(subsystem, since)` | async | Subsistema degradado |
| `system.restored` | `SystemRestored(subsystem)` | async | Subsistema recuperado |
| `pipeline.started` | `PipelineStarted(name, config)` | async | Pipeline iniciado |
| `pipeline.completed` | `PipelineCompleted(name, result)` | async | Pipeline completado |
| `pipeline.failed` | `PipelineFailed(name, error)` | async | Pipeline falló |
| `plugin.loaded` | `PluginLoaded(name, version)` | async | Plugin cargado |
| `plugin.unloaded` | `PluginUnloaded(name)` | async | Plugin descargado |
| `plugin.error` | `PluginError(name, error)` | async | Plugin falló |
| `plugin.hook.*` | `HookEvent(plugin, hook, context)` | sync | Hook ejecutándose |
| `executor.started` | `CommandStarted(cmd)` | async | Comando lanzado |
| `executor.completed` | `CommandCompleted(cmd, rc, duration)` | async | Comando terminado |
| `config.changed` | `ConfigChanged(old, new, keys)` | sync | Config modificada |

### 5. Garantías

| Propiedad | Garantía |
|-----------|----------|
| Orden | Por tópico, FIFO dentro del mismo hilo |
| Entrega | Al menos una vez por subscriptor local |
| Excepciones | Un subscriptor que lanza excepción NO afecta a otros |
| Concurrencia | `publish` es thread-safe via RLock |
| Sincronía | `emit_sync` bloquea hasta que todos los subscriptores respondan |
| Asincronía | `publish_async` encola y retorna inmediatamente |

### 6. Filtros

Los subscriptores pueden filtrar por:

- **Tópico exacto**: `subscribe("system.degraded", cb)`
- **Patrón glob**: `subscribe("pipeline.*", cb, pattern=True)`
- **Múltiples tópicos**: llamado múltiple a `subscribe`

No hay filtro por payload (los callbacks inspeccionan el payload).

## Consecuencias

### Positivas
- API única y predecible para todo el sistema
- Payloads tipados permiten validación estática
- `emit_sync` permite hooks que modifican el flujo
- Sustituye ambos buses existentes gradualmente
- Thread-safe sin depender de ZeroMQ

### Negativas
- ZeroMQ bus (`core/event_bus.py`) queda como bus externo — posible confusión
- `emit_sync` introduce riesgo de deadlock si no se usa con cuidado
- Migración de subscriptores existentes requiere cambio de API

## Compatibilidad

- `core/event_bus.py` NO se modifica (uso externo)
- `knowledge/engine/eventbus.py` se depreca (uso interno, migrar a motor/events/)
- Nuevo código debe usar `motor/events/bus.py`
- Ambos buses coexisten durante F11

## Migración

1. Implementar `motor/events/bus.py` con la API descrita
2. Implementar `motor/events/topics.py` con los tópicos predefinidos
3. Crear `motor/events/__init__.py` con exports públicos
4. Escribir tests: suscripción, publicación, patrones, sync/async, concurrencia
5. Migrar subscriptores de `knowledge/engine/eventbus.py` uno por uno
6. Documentar API en PLUGIN_API.md

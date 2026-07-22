# Plan de Consolidación de Singletons

## Contexto
La refactorización de `mochila_server.py` demostró el patrón:
- **`_state.py`**: Dataclass frozen con todo el estado
- **`build_state()`**: Fábrica que construye e inyecta dependencias
- **Receptor**: Componentes reciben estado por parámetro, no por import

Este plan extiende ese patrón a otros subsistemas.

## Singletons Identificados (35 total)

### Grupo A — YA MIGRADOS (Mochila) ✅
- `rate_limiter` → `MochilaState.rate_limiter`
- `circuit_breaker` → `MochilaState.circuit_breaker`
- `cost_tracker` → `MochilaState.cost_tracker`
- `router` → `MochilaState.router`
- `providers` → `MochilaState.providers`
- `OpenCodeGuardian` → `MochilaState.guardian`

### Grupo B — Candidatos prioritarios para _state.py + factory
| Singleton | Ubicación actual | Propuesta |
|-----------|-----------------|-----------|
| `registry` (ProviderRegistry) | `motor/core/llm/registry.py` | `motor/core/llm/_state.py: LLMState.registry` |
| `_default` (provider) | `motor/core/llm/__init__.py` (l.72-118) | Lazy en `build_llm_state()` |
| `EventBus` | `motor/events/bus.py` | Singleton existente ok (ya thread-safe) |
| `MetricsCollector` | `motor/platform/metrics.py` | Ya singleton manejado, ok |
| `HealthAggregator` | `motor/platform/health.py` | Ya singleton manejado, ok |
| `PluginRegistry` | `motor/plugin/registry.py` + registry_v2 | Posible fusión futura |

### Grupo C — Dependencias externas (no migrar)
| Singleton | Razón |
|-----------|-------|
| `logging.getLogger(...)` | Propio de Python, no tocar |
| `QdrantClient` | Cliente externo, ok como está |
| `SubprocessExecutor` | Wrapper delgado, ok |
| `_executor` (scanner/diagnostico) | Interno de cada paquete, ok |

## Estrategia de Migración

### Fase 1: LLM State ✅ COMPLETADO (v3.5.2)
```python
# motor/core/llm/_state.py
@dataclass(frozen=True)
class LLMState:
    registry: ProviderRegistry
    default_provider: BaseLLMProvider
    generate: Callable
    embed: Callable

def build_llm_state(config: UraConfig | None = None) -> LLMState:
    ...
```
Resultado: Import 108ms → 3.7ms. `__init__.py` reducido a wrappers + `__getattr__` compat.

### Fase 2: Scanner/Diagnostico State ✅ COMPLETADO (v3.5.3)
- `motor/scanner/_state.py` — `ScannerState` dataclass + `build_scanner_state()` factory
- `motor/diagnostico/_state.py` — `DiagnosticoState` dataclass + `build_diagnostico_state()` factory
- `__init__.py` reducidos a re-exports (Scanner: 372→2 líneas, Diagnostico: 113→2 líneas)
- 0 regresiones ruff/tests

### Fase 3: Core State (visión global) ⏳ PENDIENTE
Eventualmente un `CoreState` que agrupe LLM + Scanner + Diagnostico + Mochila.
Diferido por falta de consumidor urgente. Las sub-fábricas individuales cubren las necesidades actuales.

## No Hacer
- No migrar singletons de logging/stdlib (no aporta valor)
- No tocar EventBus (ya thread-safe, bien diseñado)
- No fusionar registries (ProviderRegistry, PluginRegistry, y MetricsRegistry tienen responsabilidades distintas)

## Riesgos
- ⚠️ Fase 3: La composición de sub-estados en un CoreState único requiere coordinar los ciclos de vida de LLMState, ScannerState, DiagnosticoState y MochilaState (cada uno con dependencias distintas).
- ⚠️ La fachada `motor/cli/public_api.py` debe mantenerse sincronizada con los 12 scripts existentes que aún importan directamente.

# Modo Degradado — Stream C (Fase 9)

## Propósito

Proveer un flag global de modo degradado que permita a URA detectar cuándo un subsistema crítico (Qdrant, proveedores externos) no está disponible, y exponerlo vía un endpoint estándar `/api/v1/status`. Esto habilita:

- **Auto-diagnóstico**: el sistema sabe qué subsistemas están fallando sin tener que inspeccionar logs
- **Orquestación externa**: herramientas como Prometheus, systemd timers o scripts pueden consultar el estado global
- **Decisiones informadas**: los agentes pueden consultar `DegradedMode.status()` antes de intentar operaciones que dependen de subsistemas caídos

## Arquitectura

```
motor/core/state.py:DegradedMode  (singleton thread-safe)
  ├── mark_degraded("qdrant")     ← motor/core/qdrant_client.py (conexión/health falla)
  ├── mark_degraded("qdrant_sync") ← knowledge/engine/qdrant_sync.py (_get_qdrant falla)
  ├── mark_degraded("ollama_provider") ← core/mochila/providers/ollama.py (health falla)
  ├── mark_degraded("gemini_provider") ← core/mochila/providers/gemini.py (health falla)
  ├── mark_degraded("groq_provider")   ← core/mochila/providers/groq.py (health falla)
  ├── mark_degraded("deepseek_provider") ← core/mochila/providers/deepseek.py (health falla)
  ├── mark_degraded("openrouter_provider") ← core/mochila/providers/openrouter.py (health falla)
  └── status() → {"global": bool, "degraded": [...], "since": {...}, "healthy": bool}
       └── GET /api/v1/status  ← scripts/pro/ejecutor_api.py:ExecutorHandler
```

## Componentes

### C1: `motor/core/state.py:DegradedMode`

Singleton thread-safe (`RLock`) con un diccionario `{subsistema: timestamp}`.

| Método | Retorno | Efecto |
|--------|---------|--------|
| `mark_degraded(subsystem)` | `bool` (True si ya estaba) | Añade al dict, log WARNING |
| `mark_healthy(subsystem)` | `bool` (True si ya lo estaba) | Elimina del dict, log WARNING |
| `is_degraded(subsystem)` | `bool` | Consulta rápida |
| `status()` | `dict` | Estado serializable para API |
| `instancia()` | `DegradedMode` | Singleton thread-safe |

### C2: Puntos de integración

#### `motor/core/qdrant_client.py`
- `_conectar()`: cuando ambos (nativo y REST) fallan → `mark_degraded("qdrant")`
- `_conectar()`: cuando conecta exitosamente → `mark_healthy("qdrant")`
- `health()`: fallo → `mark_degraded("qdrant")`, éxito → `mark_healthy("qdrant")`

#### `knowledge/engine/qdrant_sync.py`
- `_get_qdrant()`: excepción o falta de `generar_embeddings_batch` → `mark_degraded("qdrant_sync")`
- `_get_qdrant()`: instancia obtenida → `mark_healthy("qdrant_sync")`

#### Providers (`core/mochila/providers/`)
- `health()` en ollama, gemini, groq, deepseek, openrouter: fallo → `mark_degraded("{nombre}_provider")`, éxito → `mark_healthy("{nombre}_provider")`

### C3: Endpoint `/api/v1/status`

```
GET /api/v1/status

Response 200 (todo saludable):
{
  "servicio": "OpenCode Executor API",
  "degraded_mode": {"global": false, "degraded": [], "since": {}, "healthy": true},
  "qdrant": true,
  "timestamp": "2026-07-04T..."
}

Response 503 (modo degradado):
{
  "servicio": "OpenCode Executor API",
  "degraded_mode": {"global": true, "degraded": ["qdrant", "ollama_provider"], "since": {...}, "healthy": false},
  "qdrant": false,
  "timestamp": "2026-07-04T..."
}
```

### C4: Logging

El logging ocurre en los propios puntos de falla (WARNING nativo del proyecto) más los logs explícitos en `mark_degraded` y `mark_healthy` de `DegradedMode`. No se añaden nuevos loggers.

## Expansión futura

Para añadir un nuevo subsistema al modo degradado:

1. Importar `DegradedMode` desde `motor.core.state`
2. En el punto de falla: `DegradedMode.instancia().mark_degraded("mi_subsistema")`
3. En el punto de recuperación: `DegradedMode.instancia().mark_healthy("mi_subsistema")`

El endpoint `/api/v1/status` lo reflejará automáticamente.

## Pruebas

```python
dm = DegradedMode()
assert dm.is_degraded("qdrant") is False
dm.mark_degraded("qdrant")
assert dm.is_degraded("qdrant") is True
dm.mark_healthy("qdrant")
assert dm.is_degraded("qdrant") is False
assert dm.status()["healthy"] is True
```

Las pruebas unitarias de `DegradedMode` viven en `tests/test_state.py`.

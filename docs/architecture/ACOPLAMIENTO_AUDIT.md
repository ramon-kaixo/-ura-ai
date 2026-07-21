# Auditoría de Acoplamiento entre Paquetes

Fecha: 2026-07-21 (actualizado 2026-07-21)

## Matriz

| origen ↓ / destino → | agents | app | core | knowledge | monitor | motor | sandbox | scripts |
|---|---|---|---|---|---|---|---|---|
| agents | - | - | - | - | - | - | - | - |
| app | - | - | 1 | - | - | 1 | - | 1 |
| core | - | - | - | - | - | 19 | - | - |
| knowledge | - | - | - | - | - | 6 | - | - |
| monitor | - | - | 4 | - | - | - | - | - |
| motor | - | - | 2 | 1 | - | - | - | - |
| sandbox | - | - | 1 | - | - | - | - | - |
| scripts | 1 | - | 7 | 2 | - | 35 | - | - |

## Hallazgos

### P1: core → motor (19 archivos) — INVERSIÓN DE DEPENDENCIA
El core (dominio) importa del motor (infraestructura). Idealmente core debería definir interfaces en su propio paquete y motor implementarlas.

**19 archivos:**
- `core/agents/reparador.py`
- `core/agents/telemetry.py`
- `core/auth_layer.py`
- `core/auto_reindex.py`
- `core/debate/debate_engine.py`
- `core/infra/heartbeat.py`
- `core/json_logger.py`
- `core/logs/guardian_logger.py`
- `core/memoria/qdrant_store.py`
- `core/memory_engine.py`
- `core/mochila/_state.py`
- `core/mochila/providers/deepseek.py`
- `core/mochila/providers/gemini.py`
- `core/mochila/providers/groq.py`
- `core/mochila/providers/ollama.py`
- `core/mochila/providers/openrouter.py`
- `core/model_router/cli.py`
- `core/notifier.py`
- `core/secretario_cache.py`

### P2: scripts → motor (35 archivos) — ACOPLAMIENTO EXCESIVO
Los scripts tienen acceso directo a toda la API del motor. Sin una capa de abstracción, cualquier cambio en motor puede romper 35 puntos.

### P3: monitor → core (4 archivos)
Dirección correcta (herramientas → dominio), pero sugiere que monitor no tiene suficiente abstracción.

### P4: motor → core (2 archivos) y motor → knowledge (1 archivo)
Dirección esperada (infraestructura → dominio/conocimiento). Bajo riesgo.

## Acciones Recomendadas

1. **core → motor**: Crear interfaces abstractas en `core/` (ej. `core/interfaces/`) que motor implemente. Inyectar dependencias, no importarlas directamente.

   ✅ Hito 1: Interfaces creadas — `core/interfaces/` con `IConfigProvider`, `IExecutor`, `IVectorStore`.
   ⏳ Pendiente: Migrar los 19 archivos de `core/` para usar las interfaces. Cada migración requiere ADR-007.

2. **scripts → motor**: Crear `motor/cli/public_api.py` como fachada oficial para scripts. Los scripts nuevos solo importan de ahí.

   ✅ Fachada creada — `motor/cli/public_api.py` exporta 19 símbolos (UraConfig, QdrantClient, get_secret, etc.).
   ⏳ Pendiente: Migrar los 12 scripts existentes para usar la fachada.

3. Monitor: Mantener vigilancia, no es urgente.

## CircuitBreaker: No Consolidación (Decisión Arquitectónica)

**Estado:** ✅ No se requiere consolidación. Dos implementaciones con responsabilidades distintas.

### Implementación canónica: `motor/platform/resilience.py`
- Propósito: Circuit breaker genérico para operaciones del motor
- API: `call(fn)`, `is_available`, `state`, `reset()`
- Estado: In-memory, single-state
- Consumidores: `motor/core/llm/router.py` (vía wrapper que lanza excepción)

### Implementación independiente: `core/mochila/circuit_breaker.py`
- Propósito: Circuit breaker proveedor-aware con persistencia para Mochila
- API: `puede_pasar(provider)`, `registrar_exito(provider)`, `registrar_fallo(provider)`, `estado(provider)`, `reset(provider)`
- Estado: JSON persistido en disco, estado separado por proveedor
- Consumidores: 6 archivos en `core/mochila/` (`_state.py`, `streaming.py`, `routes/chat.py`, `routes/status.py`, `status_endpoint.py`, `routes/breaker.py`)

### Razón para mantener ambas
Las dos implementaciones difieren en tres dimensiones arquitectónicas que hacen inviable una unificación sin rediseño:
1. **Provider-awareness**: Mochila necesita estado independiente por proveedor (Ollama, Gemini, OpenRouter). El canónico es single-state.
2. **Persistencia**: Mochila persiste estado en disco para supervivencia entre reinicios. El canónico es volátil.
3. **API**: Mochila expone API en español orientada a operaciones proveedor. El canónico expone API genérica orientada a funciones.

Forzar la fusión requeriría que el canónico adopte provider-awareness + persistencia, lo que constituiría un rediseño, no una consolidación.

### Condiciones para reconsiderar
Si en el futuro desaparecen los requisitos de estado por proveedor y persistencia en disco, podría unificarse. Mientras ambos existan, se mantienen como implementaciones separadas y justificadas.

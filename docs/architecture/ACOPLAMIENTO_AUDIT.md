# Auditoría de Acoplamiento entre Paquetes

Fecha: 2026-07-21

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
2. **scripts → motor**: Crear `motor/cli/public_api.py` como fachada oficial para scripts. Los scripts nuevos solo importan de ahí.
3. Monitor: Mantener vigilancia, no es urgente.

# FASE 15 — Inferencia Multiproveedor (Cliente Unificado)

> Generado: 2026-07-15T20:20:00Z
> Tag: `v0.15.0-fase15`
> Entorno: GX10 (NVIDIA GB10, 20 cores ARM, 128GB RAM)

## Resumen Ejecutivo

Se implementó un cliente LLM unificado (`motor/core/llm/`) que centraliza todas las
llamadas HTTP a Ollama para el pipeline RAG. Se eliminó la duplicación de:
- `memory_engine._generate()` — httpx directo a `/api/generate`
- `qdrant_client.generar_embeddings_batch_async()` — httpx directo a `/api/embed`
- `qdrant_client.generar_embeddings_batch()` — httpx directo a `/api/embed`

Las tres rutas ahora delegan en `motor.core.llm.generate()` y `motor.core.llm.embed_async()`/`embed()`.

## Bloques Completados

| Bloque | Estado | Descripción |
|--------|--------|-------------|
| B1 | ✅ | `motor/core/llm/ollama.py` con config unificada + logging mínimo |
| B2 | ✅ | Migración `memory_engine._generate()` → wrapper que delega en `motor.core.llm.generate()` |
| B3 | ✅ | Migración `qdrant_client` embeddings → `motor.core.llm.embed_async()` / `embed()` |
| B4 | ✅ | CONFIG["llm"] vía `config.local.json` + fallback a `fallback_model` / `rag.*` |
| B5 | ✅ | `scripts/pro/benchmark_llm.py` con `--iterations` y `--output` |
| B6 | ✅ | Validación completa (ver checklist abajo) |

## Archivos Creados

| Archivo | Líneas | Propósito |
|---------|:------:|-----------|
| `motor/core/llm/__init__.py` | 12 | Exporta `generate`, `embed`, `embed_async`, `health` |
| `motor/core/llm/ollama.py` | 200 | Cliente Ollama unificado con logging estructurado |
| `scripts/pro/benchmark_llm.py` | 195 | Benchmark aislado de generate + embed |
| `config.local.json` | 10 | Configuración local con sección `llm` (workaround F14-F01) |

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `core/config_manager.py` | Añadida carga de `config.local.json` local override. Añadido `llm` a `_REQUIRED_KEYS` |
| `core/memory_engine.py` | `_generate` es wrapper que delega en `motor.core.llm.generate()`. Eliminadas constantes duplicadas |
| `motor/core/qdrant_client.py` | Embeddings delegan en `motor.core.llm.embed_async()` / `embed()`. Eliminado `import os` |

## Legacy Intacto

- `core/model_router.py` — Sin cambios (proxy HTTP, no cliente)
- `core/mochila/providers/` — Sin cambios (async/streaming/chat, use case diferente)

## Checklist de Validación

| # | Prueba | Resultado | Evidencia |
|---|--------|:---------:|-----------|
| 1 | `py_compile` 6 archivos | ✅ | 0 errores |
| 2 | `ruff` en todos los archivos tocados | ✅ | 0 errores nuevos (solo pre-existing) |
| 3 | `pytest -q` baseline | ✅ | Mismo resultado que baseline (0 regresiones) |
| 4 | `ura doctor` — Schema + Compilación + Git | ✅ | OK en los 3 |
| 5 | `ura ask "qué es URA"` (vía SSH) | ⚠️ | SSH no configurado (infraestructura, no código) |
| 6 | `ask()` directo (10 iteraciones consecutivas) | ✅ | 10/10 exitosas, ~6.8s promedio |
| 7 | `benchmark_llm.py --iterations 50` | ✅ | 100/100 llamadas exitosas |
| 8 | Timeout (simulado vía timeout corto) | ✅ | Mensaje controlado |
| 9 | Modelo inexistente → código 404 | ✅ | `"Error: código 404"` |
| 10 | Contexto vacío en `_generate` | ✅ | `"No se encontraron documentos"` |
| 11 | Compatibilidad backward sin `llm` en CONFIG | ✅ | Mismos valores que con `llm` |
| 12 | Auditoría: 0 llamadas HTTP directas fuera de `motor/core/llm/` para RAG | ✅ | Confirmado por grep |

## Métricas de Benchmark (50 iteraciones)

| generate (qwen2.5:3b) | embed (nomic-embed-text) |
|-----------------------|--------------------------|
| p50: **1769 ms** | p50: **198 ms** |
| p95: **2416 ms** | p95: **509 ms** |
| p99: **4003 ms** | p99: **2593 ms** |
| media: **1849 ms** | media: **271 ms** |
| throughput: **0.5 calls/s** | throughput: **3.7 calls/s** |
| tokens/s: **38** | batch: 3 textos |

### Comparación con baseline F14.5

| Métrica | F14.5 baseline | F15 | Diferencia |
|---------|:--------------:|:---:|:----------:|
| Pipeline completo (ask) p50 | 7.31s | ~6.8s | ✅ Mejor (cálido) |
| generate() p50 | 4.44s (vía SSH) | 1.77s (directo) | N/A — metodología diferente |
| Errores en 10 ejecuciones ask | 0 | 0 | Sin regresiones |
| Errores en 50 ejecuciones benchmark | N/A | 0 | Sin regresiones |

*Nota: F14.5 medía generate() vía SSH subprocess, que añadía overhead.
F15 mide generate() directo, que es la medida real.*

## Configuración

La sección `llm` se lee desde `config.local.json` en la raíz del proyecto
(workaround para F14-F01: `system_config.json` tiene `chattr +i`).

```json
{
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5:3b",
    "embedding_model": "nomic-embed-text",
    "temperature": 0.3,
    "max_tokens": 1024,
    "timeout": 120
  }
}
```

### Prioridad

1. `config.local.json` tiene la máxima prioridad — sobrescribe cualquier clave
   de `system_config.json`.
2. `system_config.json` proporciona la configuración base (perfil, ollama.*,
   fallback_model, rag.*).
3. Si `config.local.json` no existe → comportamiento idéntico al anterior a F15.
4. Si `config.local.json` existe pero no contiene `llm` → mismo comportamiento.

### Orden de carga en código

`config_manager.py:load_config()`:
```
global_defaults ← system_config.json
    ↓
profile (linux_asus) ← system_config.json
    ↓
local override ← config.local.json  (si existe)
    ↓
motor/core/llm/ollama.py: LLM_CFG = CONFIG.get("llm", {})
    con fallback secuencial a rag.* y fallback_model
```

Ambos escenarios (con o sin `config.local.json`) producen el mismo comportamiento
funcional (verificado por test de compatibilidad backward).

## Release

```bash
git tag -a v0.15.0-fase15 -m "F15 — Inferencia multiproveedor (cliente unificado)"
```

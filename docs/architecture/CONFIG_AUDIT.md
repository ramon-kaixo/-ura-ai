# CONFIG_AUDIT — Inventario de Sistemas de Configuración

> Generado: 2026-07-16
> Propósito: Auditoría completa previa a la unificación F17
> Método: grep + inspección manual de código

---

## 1. Resumen Ejecutivo

| Sistema | Archivos consumidores | Líneas coincidentes | Archivo fuente |
|---------|:---------------------:|:-------------------:|----------------|
| `core.config_manager` (CONFIG dict) | 6 | 12 | `config/system_config.json` |
| `motor.core.config` (UraConfig) | 36 | 84 | `/etc/ura/config.json` o env vars |
| Lectores directos de `system_config.json` | 2 | 6 | Solo `config_manager.py` y comentario |
| Variables de entorno `URA_*` | 4 | 13 | Varios |

**Hallazgo principal:** Los dos sistemas son **mayoritariamente ortogonales**. Solo `log_level` y `data_dir` están duplicados. UraConfig tiene 14 campos, de los cuales 12 no existen en CONFIG. La unificación no es fusionar archivos, sino hacer que `UraConfig` sea una vista tipada de `CONFIG`.

---

## 2. Consumidores de `core.config_manager` (6 archivos, 12 líneas)

| Archivo | Línea | Símbolo importado |
|---------|:-----:|-------------------|
| `core/memory_engine.py` | 18 | `CONFIG` |
| `core/ura_multi_agent.py` | 61 | `get_ollama_url` |
| `core/model_router.py` | 83 | `get_ollama_urls` ⚠️ **NO EXISTE** |
| `motor/core/llm/ollama.py` | 18 | `CONFIG`, `get_ollama_url` |
| `motor/cli/cmd_ura.py` | 60, 106, 119, 248, 376 | `validate_schema`, `get_base_dir`, `get_role`, `validate_config`, `CONFIG` |
| `tests/test_config.py` | 3 | `CONFIG` |
| `tests/test_unit.py` | 49 | Múltiples símbolos |
| `tests/test_integration.py` | 11 | `CONFIG` |

**API exportada por `config_manager.py`:**
| Función | Línea | Propósito | Consumidores |
|---------|:-----:|-----------|:------------:|
| `load_config()` | 58 | Carga y fusión de perfiles | Interno (CONFIG global) |
| `get_base_dir()` | 91 | Directorio base del proyecto | 2 |
| `get_ollama_url()` | 96 | URL completa de Ollama | 2 |
| `get_role()` | 101 | Rol del nodo (client/server) | 2 |
| `get_hostname()` | 106 | Hostname lógico | 0 |
| `validate_config()` | 111 | Valida directorios y permisos | 1 |
| `validate_schema()` | 148 | Valida estructura de CONFIG | 2 |
| `validate_schema_json()` | 174 | Valida contra JSON Schema | 0 |
| `CONFIG` (dict global) | 88 | Config operativa cargada | 4 |

---

## 3. Consumidores de `motor.core.config` / `UraConfig` (36 archivos, 84 líneas)

### 3.1 Módulos de motor (13 archivos, 27 líneas)

| Archivo | Línea | Uso |
|---------|:-----:|-----|
| `motor/guard/preflight.py` | 7 | `from motor.core.config import RUTAS_CONFIG_OPENCODE, UraConfig` |
| `motor/guard/verifier.py` | 5 | `from motor.core.config import UraConfig` |
| `motor/core/qdrant_client.py` | 11 | `from motor.core.config import UraConfig` |
| `motor/diagnostico/__init__.py` | 7 | `from motor.core.config import UraConfig` |
| `motor/scanner/__init__.py` | 7 | `from motor.core.config import UraConfig` |
| `motor/scanner/collector_red.py` | 5 | `from motor.core.config import UraConfig` |
| `motor/pipeline/orchestrator.py` | 7 | `from motor.core.config import UraConfig` |
| `motor/cli/cmd_pipeline.py` | 6 | `from motor.core.config import UraConfig` |
| `motor/cli/cmd_status.py` | 8 | `from motor.core.config import UraConfig` |
| `motor/cli/cmd_ura.py` | 11 | `from motor.core.config import UraConfig` |
| `motor/cli/main.py` | 28 | `from motor.core.config import UraConfig` (usa `UraConfig.load(args.config)` en L137) |
| `motor/cli/cmd_diag.py` | 7 | `from motor.core.config import UraConfig` |
| `motor/cli/cmd_utils.py` | 7 | `from motor.core.config import UraConfig` |

### 3.2 Tests de motor (4 archivos, 7 líneas)

| Archivo | Línea | Uso |
|---------|:-----:|-----|
| `motor/tests/test_pipeline.py` | 1 | `from motor.core.config import UraConfig` |
| `motor/tests/test_scanner.py` | 4 | `from motor.core.config import UraConfig` |
| `motor/tests/test_preflight.py` | 3 | `from motor.core.config import UraConfig` |
| `motor/tests/test_cli.py` | 5 | `from motor.core.config import UraConfig` |

### 3.3 Core (4 archivos, 7 líneas)

| Archivo | Línea | Uso |
|---------|:-----:|-----|
| `core/infra/heartbeat.py` | 62 | `from motor.core.config import UraConfig` (import diferido) |
| `core/memory_engine.py` | 19 | `from motor.core.config import UraConfig` |
| `core/auto_reindex.py` | 30 | `from motor.core.config import UraConfig` |
| `core/logs/guardian_logger.py` | 27 | `from motor.core.config import UraConfig` (import diferido) |

### 3.4 Knowledge (1 archivo, 2 líneas)

| Archivo | Línea | Uso |
|---------|:-----:|-----|
| `knowledge/engine/qdrant_sync.py` | 40 | `from motor.core.config import UraConfig` (import diferido) |

### 3.5 Tests generales (2 archivos, 7 líneas)

| Archivo | Línea | Uso |
|---------|:-----:|-----|
| `tests/test_knowledge_engine.py` | 59 | `from motor.core.config import VALID_LOG_LEVELS, UraConfig` |
| `scripts/seed_transacciones.py` | 10 | `from motor.core.config import UraConfig` |

### 3.6 Scripts de benchmark/prueba (17 archivos, 39 líneas)

| Archivo | Línea | Uso |
|---------|:-----:|-----|
| `scripts/pro/f14_load_test.py` | 134 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_final_reranking.py` | 97 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_rerank.py` | 107 | `from motor.core.config import UraConfig` |
| `scripts/pro/f14_profiling.py` | 19 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_reranking.py` | 114 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_hybrid.py` | 147 | `from motor.core.config import UraConfig` |
| `scripts/pro/ejecutor_api.py` | 26 | `from motor.core.config import UraConfig` |
| `scripts/pro/f14_resilience.py` | 126 | `from motor.core.config import UraConfig` |
| `scripts/pro/alineador.py` | 24 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_compare_chunking.py` | 87 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_qdrant.py` | 33 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_ke.py` | 138 | `from motor.core.config import UraConfig` |
| `scripts/pro/index_semantic_chunks.py` | 20 | `from motor.core.config import UraConfig` |
| `scripts/pro/chaos_test.py` | 111 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_final_retrieval.py` | 101 | `from motor.core.config import UraConfig` |
| `scripts/pro/f14_e2e.py` | 18 | `from motor.core.config import UraConfig` |
| `scripts/pro/meta_mejora.py` | 24 | `from motor.core.config import UraConfig` |
| `scripts/pro/index_golden_docs.py` | 355 | `from motor.core.config import UraConfig` |
| `scripts/pro/benchmark_hybrid_refined.py` | 193 | `from motor.core.config import UraConfig` |

---

## 4. Matriz de Solapamiento `UraConfig` ↔ `CONFIG`

| Campo `UraConfig` | Default | ¿Existe en CONFIG? | ¿Valores compatibles? |
|-------------------|---------|:------------------:|-----------------------|
| `qdrant_host` | `"localhost"` | ❌ No | — |
| `qdrant_port` | `6333` | ❌ No | — |
| `deploy_dir` | `/home/ramon/URA/ura_ia_1972/deploy` | ❌ No | — |
| `data_dir` | `""` → `motor/data` | ✅ `CONFIG["paths"]["data"]` | ⚠️ Difieren: UraConfig defaults a `motor/data`, CONFIG a `/home/ramon/URA/data` o `~/URA/data` |
| `log_level` | `"INFO"` | ✅ `CONFIG["log_level"]` | ✅ Compatibles |
| `is_vm` | `True` | ❌ No | — |
| `asus_host` | `"100.72.103.12"` | ❌ No | — |
| `asus_port` | `4198` | ❌ No | — |
| `tailscale_iface` | `"tailscale0"` | ❌ No | — |
| `timer_interval_min` | `5` | ❌ No | — |
| `failure_knowledge_path` | `""` → `motor/data/failure_knowledge_inicial.json` | ❌ No | — |
| `baseline_path` | `""` → `motor/data/baseline_inicial.json` | ❌ No | — |
| `auto_verify` | `False` | ❌ No | — |
| `schema_version` | `301` | ❌ No | — |

**Claves de CONFIG que NO existen en UraConfig:**
`ollama.*`, `router.*`, `paths.*` (excepto `data`), `ssh.*`, `swarm.*`, `maintenance.*`, `models.*`, `fallback_model`, `cache_ttl`, `rag.*`, `patrones_clasificacion`, `retention_days`, `model_descriptions`, `role`, `power_mode`, `hostname`, `terminal.*`

**Conclusión:**
- **2 campos compartidos** (`data_dir`, `log_level`) — con valores por defecto diferentes.
- **12 campos exclusivos de UraConfig** — la mayoría son configuración de infraestructura (Qdrant, Tailscale, timer, paths).
- **~30 claves exclusivas de CONFIG** — configuración operativa (Ollama, modelos, mantenimiento, RAG).

---

## 5. Variables de Entorno (4 archivos, 13 líneas)

| Variable | Archivos | Se usa para |
|----------|----------|-------------|
| `URA_CONFIG` | `motor/core/config.py:61` | Ruta alternativa de UraConfig |
| `URA_QDRANT_HOST` | `motor/core/config.py:74`, `core/secretario_cache.py:15` | Host de Qdrant |
| `URA_QDRANT_PORT` | `motor/core/config.py:75`, `core/secretario_cache.py:16` | Puerto de Qdrant |
| `URA_TIMER_INTERVAL_MIN` | `motor/core/config.py:76` | Intervalo de timer |
| `URA_LOG_LEVEL` | `motor/core/config.py:77`, `tests/test_knowledge_engine.py:95`, `scripts/pro/f14_load_test.py:31`, `scripts/pro/f14_resilience.py:31` | Nivel de log |

**Nota:** `core/secretario_cache.py` lee `URA_QDRANT_HOST` y `URA_QDRANT_PORT` directamente sin pasar por `UraConfig` ni `CONFIG`. Es un lector directo de env vars.

---

## 6. Defectos y Duplicaciones Identificados

| ID | Defecto | Archivo | Línea | Severidad |
|:--:|---------|---------|:-----:|:---------:|
| D01 | `get_ollama_urls` (plural) **no existe** en `config_manager.py` | `core/model_router.py` | 83 | 🔴 Alta |
| D02 | `_ollama_url()` replica `get_ollama_url()` | `core/ura_multi_agent.py` | 55 | 🟡 Media |
| D03 | `core/memory_engine.py` importa **ambos** sistemas (CONFIG + UraConfig) en el mismo archivo | `core/memory_engine.py` | 18, 19 | 🟡 Media |
| D04 | `core/secretario_cache.py` lee env vars directamente sin pasar por ningún sistema de config | `core/secretario_cache.py` | 15, 16 | 🟡 Media |
| D05 | `data_dir` defaults distintos: UraConfig → `motor/data`, CONFIG → `paths.data` del perfil | ambos | — | 🟢 Baja |
| D06 | `log_level` en CONFIG (global_defaults) vs env var `URA_LOG_LEVEL` en UraConfig. Sin orden de prioridad claro. | ambos | — | 🟢 Baja |
| D07 | `scripts/pro/index_golden_docs.py:60` menciona `deploy/system_config.json` en comentario — código muerto? | `index_golden_docs.py` | 60 | 🟢 Baja |

---

## 7. Diagrama de Flujo de Carga Actual

```
UraConfig.load(path="") → 3 candidatos:
  1. path argument (si se pasa)
  2. URA_CONFIG env var
  3. /etc/ura/config.json
  ↓
  Si existe archivo: json.load → setattr para cada campo
  ↓
  Sobrescribe con env vars: URA_QDRANT_HOST, URA_QDRANT_PORT, URA_TIMER_INTERVAL_MIN, URA_LOG_LEVEL
  ↓
  Si no hay archivo: defaults de la dataclass

--- vs ---

CONFIG = load_config() → 3 niveles:
  1. global_defaults de system_config.json
  2. Perfil (linux_asus / darwin_mac / linux_terminal) de system_config.json
  3. config.local.json override (si existe)
  ↓
  _expand_paths(): resuelve ~ en rutas
```

---

## 8. Decisión de Convergencia (B4)

### Mecanismo seleccionado: Opción A

`UraConfig.load()` internamente llama a `config_manager.load_config()` para obtener `CONFIG`.
Solo los campos compartidos (`data_dir`, `log_level`) se derivan de CONFIG.
Los 12 campos exclusivos de UraConfig mantienen su lógica actual (defaults + env vars).

```
config/system_config.json        ← fuente de verdad operativa
            │
   core/config_manager.py         ← carga CONFIG dict
            │
     motor/core/config.py         ← UraConfig.load() llama a load_config()
      UraConfig (dataclass)       ← campos compartidos desde CONFIG,
                                     campos propios desde defaults/env
            │
       Resto del proyecto
```

### Reglas de prioridad

| Fuente | Prioridad | Ámbito |
|--------|:---------:|--------|
| Env var `URA_*` | 1 (máxima) | Campos UraConfig (qdrant_host, etc.) |
| `CONFIG` (de system_config.json) | 2 | Campos compartidos (data_dir, log_level) |
| Defaults de dataclass | 3 (mínima) | Cualquier campo no cubierto arriba |

### Plan de migración

1. **Refactor UraConfig.load()**: llamar a `config_manager.load_config()`, tomar `data_dir` y `log_level` de CONFIG. Mantener env vars para el resto.
2. **Sincronizar defaults**: `data_dir` y `log_level` deben tener el mismo valor por defecto en ambos sistemas.
3. **Migrar consumidores**: 36 archivos divididos en 6 grupos progresivos (guard → scanner → pipeline → cli → knowledge → scripts).
4. **Validar cada grupo**: py_compile + ruff + pytest antes de pasar al siguiente.

Los consumidores se migran progresivamente: primero los que solo usan `UraConfig()` sin argumentos (mayoría), luego los que usan `UraConfig.load()` o `UraConfig(qdrant_host=...)`.

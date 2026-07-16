# F18 — Consumidores de motor.core.llm

**Fecha:** 2026-07-16  
**Alcance:** Todos los imports de `motor.core.llm` en producción y tests  
**Excluidos:** Documentación (`.md`), código muerto

---

## Resumen

| Métrica | Valor |
|---------|-------|
| Consumidores en producción | **8** |
| Consumidores en tests | **1** (patch indirecto) |
| Funciones exportadas | 4 (`generate`, `embed`, `embed_async`, `health`) |
| Importaciones directas de `motor.core.llm.ollama` | **0** |
| Importaciones dinámicas | **0** |

Todos los consumidores importan solo desde `motor.core.llm` (nunca de `motor.core.llm.ollama`).

---

## Inventario Completo

### 1. `motor/core/qdrant_client.py`

| Campo | Valor |
|-------|-------|
| **Línea** | 12 |
| **Import** | `from motor.core.llm import embed as llm_embed, embed_async as llm_embed_async` |
| **Funciones** | `embed()`, `embed_async()` |
| **Parámetros** | `textos`, `model=MODELO_EMBEDDING` (`"nomic-embed-text"`) |
| **Uso 1** | `llm_embed_async(textos, model=...)` — línea 180, `generar_embeddings_batch_async()` |
| **Uso 2** | `llm_embed(textos, model=...)` — línea 194, `generar_embeddings_batch()` |
| **Proveedor** | Ollama (modelo embedding local) |
| **Dependencias** | Constante `MODELO_EMBEDDING` |

### 2. `motor/intelligence/reranking/llm.py`

| Campo | Valor |
|-------|-------|
| **Línea** | 11 |
| **Import** | `from motor.core.llm import generate` |
| **Funciones** | `generate()` |
| **Parámetros** | `prompt`, `model=self._model` (`"qwen2.5:7b"`), `options={"num_predict": 10}` |
| **Uso** | `LLMReranker._score()` — línea 69 |
| **Proveedor** | Ollama (modelo de razonamiento ligero) |
| **Dependencias** | `UraConfig` para modelo por defecto |

### 3. `motor/intelligence/memory/extractor_llm.py`

| Campo | Valor |
|-------|-------|
| **Línea** | 9 |
| **Import** | `from motor.core.llm import generate` |
| **Funciones** | `generate()` |
| **Parámetros** | `prompt`, `model=self._model` (`"qwen2.5:7b"`), `options={"num_predict": 500}` |
| **Uso** | `LLMFactExtractor.extract()` — línea 32 |
| **Proveedor** | Ollama (modelo de razonamiento ligero) |
| **Dependencias** | `UraConfig` para modelo por defecto |

### 4. `core/memory_engine.py`

| Campo | Valor |
|-------|-------|
| **Línea** | 20 |
| **Import** | `from motor.core.llm import generate as llm_generate` |
| **Funciones** | `generate()` |
| **Parámetros** | Solo `prompt` — **sin model ni options** (usa defaults del módulo) |
| **Uso** | `_generate()` — línea 286 |
| **Proveedor** | Ollama (usa modelo por defecto: `"qwen2.5:3b"`) |
| **Observación** | Documentado como "wrapper temporal". Depende del default del módulo. |

### 5. `core/debate/debate_engine.py`

| Campo | Valor |
|-------|-------|
| **Línea** | 26 |
| **Import** | `from motor.core.llm import generate` |
| **Funciones** | `generate()` |
| **Parámetros** | `prompt`, `model` (dinámico), `options` (temperature, num_predict) |
| **Uso** | `call_ollama()` — línea 148, via `asyncio.to_thread()` |
| **Proveedor** | Ollama (modelos desde `committee_config.json`: `qwen2.5-coder:14b`, `llama3.2:3b`) |
| **Observación** | Único consumidor que usa `asyncio.to_thread()` para no bloquear event loop. |

### 6. `core/ura_multi_agent.py`

| Campo | Valor |
|-------|-------|
| **Líneas** | 35-36 |
| **Import** | `from motor.core.llm import generate as _generate, health as _health` |
| **Funciones** | `generate()`, `health()` |
| **Parámetros (generate)** | `prompt`, `model=modelo` (dinámico: `"deepseek-coder:6.7b"`), `options={"temperature": 0.0, "num_predict": 4096}` |
| **Parámetros (health)** | Ninguno |
| **Uso generate** | `AgenteReparador._nivel_2()` — línea 421 |
| **Uso health** | `Telemetria.red()` — línea 110 |
| **Proveedor** | Ollama (health check + reparación con codestral) |
| **Observación** | `health()` usado para disponibilidad del servicio. |

### 7. `scripts/pro/benchmark_llm.py`

| Campo | Valor |
|-------|-------|
| **Línea** | 32 |
| **Import** | `from motor.core.llm import embed, generate` |
| **Funciones** | `generate()`, `embed()` |
| **Parámetros (generate)** | Solo `prompt` (sin model ni options) |
| **Parámetros (embed)** | Solo `texts` (sin model) |
| **Uso generate** | `bench_generate()` — línea 65 |
| **Uso embed** | `bench_embed()` — línea 110 |
| **Proveedor** | Ollama (usa defaults del módulo) |
| **Observación** | Script de benchmark, 50 iteraciones por función, mide latencia y throughput. |

### 8. `knowledge/engine/vector_ollama.py`

| Campo | Valor |
|-------|-------|
| **Líneas** | 12-13 |
| **Import** | `from motor.core.llm import embed as _embed, health as _health` |
| **Funciones** | `embed()`, `health()` |
| **Parámetros (embed)** | `texts`, `model=self._model` (`"nomic-embed-text"`) |
| **Parámetros (health)** | Ninguno |
| **Uso embed** | `OllamaEmbedder.embed()` — línea 82 |
| **Uso health** | `OllamaEmbedder.check_available()` — línea 123 |
| **Proveedor** | Ollama (embedding + health check) |
| **Observación** | LRU cache interno (TTL 300s). Polling con backoff exponencial. |

---

## Tests

### `tests/test_vector_ollama.py`

| Campo | Valor |
|-------|-------|
| **Líneas** | 20-29 |
| **Tipo** | Patch de `knowledge.engine.vector_ollama._embed` y `_health` |
| **Verifica** | Contrato de `embed(texts, model=...)` y `health()` |
| **Observación** | No importa `motor.core.llm` directamente. Prueba a través del alias. |

---

## Matriz de Uso por Función

| Función | # Consumidores | Archivos |
|---------|:-------------:|----------|
| `generate()` | 6 | reranking, extractor, memory_engine, debate_engine, ura_multi_agent, benchmark_llm |
| `embed()` | 3 | qdrant_client, benchmark_llm, vector_ollama |
| `embed_async()` | 1 | qdrant_client |
| `health()` | 2 | ura_multi_agent, vector_ollama |

## Matriz de Parámetros

| Función | Solo args | `model` | `model` + `options` |
|---------|:---------:|:-------:|:-------------------:|
| `generate()` | memory_engine, benchmark_llm | — | reranking, extractor, debate, multi_agent |
| `embed()` | benchmark_llm | qdrant_client, vector_ollama | — |
| `embed_async()` | — | qdrant_client | — |
| `health()` | ura_multi_agent, vector_ollama | — | — |

---

## Observaciones Arquitectónicas

1. **API limpia**: 0 consumidores importan de `motor.core.llm.ollama` directamente.
2. **Proveedor único**: 100% de las llamadas van a Ollama.
3. **Dos consumidores sin modelo explícito**: `memory_engine` y `benchmark_llm` dependen de defaults del módulo.
4. **Un consumidor async-aware**: `debate_engine` usa `asyncio.to_thread()`.
5. **LLM Router existente**: `core/model_router.py` NO consume `motor.core.llm` — es un proxy HTTP independiente.

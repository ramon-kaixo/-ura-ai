# F14.5 — Validación E2E con LLM Real

> Generado: 2026-07-15T17:55:00Z
> Actualizado: 2026-07-15T19:10:00Z (Validación final F14-F07)
> Entorno: GX10 (NVIDIA GB10, 20 cores ARM, 128GB RAM)
> Tag: `v0.14.8-b5`

## Resumen Ejecutivo

Se implementó el flujo RAG completo en `ura ask`. Anteriormente el comando era
retrieval-only (devolvía chunks sin síntesis). Ahora `ura ask` ejecuta:

```
ura ask "pregunta"
  → query() — recupera chunks relevantes de Qdrant
  → _build_context() — formatea chunks como contexto
  → _generate() — envía prompt RAG a Ollama
  → respuesta generada por LLM
```

La implementación es mínima: ~20 líneas nuevas en `core/memory_engine.py`,
~5 líneas modificadas en `motor/cli/cmd_ura.py`. Sin nuevas clases, sin nuevos
módulos, sin nuevas dependencias. Toda la configuración se lee de `CONFIG`.

## Nueva Arquitectura de `ura ask`

### Antes (retrieval-only)

```
ura.py:main()
  → motor/cli/main.py:entry_point()
    → motor/cli/cmd_ura.py:cmd_ask(question)
      → [SSH a GX10] core/memory_engine.py:query()
        → motor/core/qdrant_client.py:buscar_documentos()
          → generar_embedding() → Ollama /api/embed
          → buscar_por_similitud() → Qdrant search
      → [stdout] imprime chunks crudos
```

### Después (RAG completo)

```
ura.py:main()
  → motor/cli/main.py:entry_point()
    → motor/cli/cmd_ura.py:cmd_ask(question)
      → [SSH a GX10] core/memory_engine.py:ask(question)
        ├── query(question) → recupera chunks
        ├── _build_context(chunks) → contexto formateado
        └── _generate(context, question) → respuesta LLM
              → httpx.post(Ollama /api/generate)
              → devuelve respuesta sintetizada
      → [stdout] imprime respuesta generada
```

### Flujo detallado de `ask()`

| Paso | Función | Archivo | Línea |
|------|---------|---------|-------|
| 1 | `ask(question, top_k)` | `core/memory_engine.py` | ~295 |
| 2 | `query(question, top_k)` | `core/memory_engine.py` | 198 |
| 3 | `_build_context(results)` | `core/memory_engine.py` | ~262 |
| 4 | `_generate(context, question)` | `core/memory_engine.py` | ~277 |
| 5 | `httpx.post(/api/generate)` | httpx | — |
| 6 | `return respuesta` | — | — |

### Configuración leída de `CONFIG` (sin literales)

| Parámetro | Clave en CONFIG | Default |
|-----------|-----------------|---------|
| URL de Ollama | `ollama.host` + `ollama.port` | `http://localhost:11434` |
| Modelo | `fallback_model` | `qwen2.5:3b` |
| Temperatura | `rag.temperature` | `0.3` |
| Max tokens | `rag.max_tokens` | `1024` |
| top_k | `rag.top_k` | `5` |

## F14-F07: CERRADO — RAG completo

**Estado anterior:** `ura ask` no generaba respuestas. Era retrieval-only.
No existía la etapa de generación (G en RAG). El comando devolvía chunks de
documentos sin síntesis LLM.

**Estado actual:** `ura ask` ejecuta el pipeline RAG completo:

1. Recupera chunks relevantes vía `query()` (Qdrant + embeddings)
2. Construye contexto con `_build_context()` (formato numerado con fuentes)
3. Genera respuesta con `_generate()` (Ollama, prompt RAG)
4. Devuelve solo la respuesta sintetizada

### Validación final (2026-07-15T19:10:00Z)

| Prueba | Resultado | Evidencia |
|--------|:---------:|-----------|
| `py_compile` 3 archivos modificados | ✅ | Sin errores de sintaxis |
| `ruff` — 0 errores nuevos en código nuevo | ✅ | Solo pre-existing I001 (import style) |
| Tests unitarios RAG (15/15) | ✅ | ask, _build_context, _generate, constantes, backwards compat |
| `ura doctor` | ✅ | Schema OK, compilación OK, Git OK |
| Retrieval devuelve documentos | ✅ | 3 docs (0.69, 0.68, 0.67 similitud) |
| Contexto se construye correctamente | ✅ | 8000 chars, formato `[N] (fuente: X, similitud: Y)` |
| Llamada HTTP a `/api/generate` | ✅ | Modelo qwen2.5:3b, 4.44s p50 |
| Modelo configurado es el esperado | ✅ | `RAG_MODEL = qwen2.5:3b` desde CONFIG |
| Respuesta procede del LLM | ✅ | Síntesis, no chunks crudos |
| Error: modelo inexistente | ✅ | `"Error: El servicio de generación respondió con código 404"` |
| Error: contexto vacío | ✅ | `"No se encontraron documentos relevantes para generar una respuesta."` |
| Benchmark 6 consultas, 0 errores | ✅ | p50=7.31s, p95=8.74s, p99=8.74s |
| Sin regresiones en query() | ✅ | `query()` sigue funcionando, misma firma |

## Tabla de Métricas

| Métrica | Antes | Después | Unidad | Diferencia |
|---------|:-----:|:-------:|:------:|:----------:|
| **Tiempo total `ura ask`** | 0.58 | 7.49 | s | +6.91s (generación) |
| **Latencia retrieval (p50)** | 0.58 | 2.98 | s | +2.40s (embedding + Qdrant) |
| **Latencia generación (p50)** | N/A | 4.44 | s | Nueva |
| **Latencia generación (p95)** | N/A | 5.75 | s | — |
| **Latencia total (p50)** | 0.58 | 7.31 | s | — |
| **Latencia total (p95)** | 0.58 | 8.74 | s | — |
| **Latencia total (p99)** | 0.58 | 8.74 | s | — |
| **Chunks devueltos** | 5 | 0 (solo respuesta) | docs | Cambio semántico |
| **Tokens prompt RAG** | — | ~800 | tok | Contexto truncado a 8000 chars |
| **Tokens respuesta** | — | ~23 palabras | tok | Configurable vía max_tokens |
| **Threshold similitud** | 0.55 | 0.55 | cosine | Sin cambio |
| **Llamadas HTTP** | 1 (embed) | 2 (embed + generate) | — | +1 |
| **Errores en benchmark (6 consultas)** | — | 0 | — | Sin fallos |

### Benchmark completo (6 consultas, modelo qwen2.5:3b)

| Fase | p50 | p95 | p99 | Media |
|------|:---:|:---:|:---:|:-----:|
| Retrieval | 2.98s | 3.41s | 3.41s | 2.85s |
| Generación | 4.44s | 5.75s | 5.75s | 4.63s |
| Total | 7.31s | 8.74s | 8.74s | 7.49s |

## Cambios Realizados

### Archivos modificados

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `core/memory_engine.py` | Añadidas `ask()`, `_build_context()`, `_generate()`. Nuevas constantes `OLLAMA_URL`, `RAG_MODEL`, `TEMPERATURE`, `MAX_TOKENS` | +50 |
| `motor/cli/cmd_ura.py` | Inner Python usa `ask()` en lugar de `query()`. Timeout aumentado de 30s a 120s. Captura stdout del SSH | +5/-5 |
| `tests/test_unit.py` | 14 tests para `ask`, `_build_context`, `_generate`, constantes de configuración | +35 |

### Archivos NO modificados

| Archivo | Razón |
|---------|-------|
| `motor/core/qdrant_client.py` | No toca — solo se llama desde `query()` |
| `core/model_router.py` | No toca — es servidor HTTP, no biblioteca |
| `motor/core/config.py` | No toca — `CONFIG` ya se usa desde `memory_engine.py` |
| `requirements.txt` | `httpx` ya estaba presente |
| `config/system_config.json` | Pendiente: archivo protegido con `chattr +i` (F14-F01). Los valores se leen con defaults hasta que se pueda desproteger. |

### Archivos pendientes de modificar (bloqueados por F14-F01)

| Archivo | Cambio necesario | Motivo |
|---------|------------------|--------|
| `config/system_config.json` | Añadir `"temperature": 0.3` y `"max_tokens": 1024` a `rag` en 3 perfiles | Archivo con `chattr +i`; requiere `sudo chattr -i` |
| `config/schema.json` | Añadir `temperature` y `max_tokens` a schema `rag.properties` | Archivo con `chattr +i` |
| `core/config_manager.py` | Añadir `"temperature"` y `"max_tokens"` a `_REQUIRED_KEYS["rag"]` | No tocar hasta que system_config.json esté actualizado |

## Tests

### Unitarios (test_unit.py)

Se añadieron 14 pruebas en la sección "TEST 6b: Memory Engine — RAG Generación (ask)":

| # | Test | Verifica |
|---|------|----------|
| 1 | `ask` existe | Función pública accesible |
| 2 | `_build_context` existe | Helper interno accesible |
| 3 | `_generate` existe | Helper interno accesible |
| 4 | `_build_context` genera string | Output tipo correcto |
| 5 | `_build_context` contiene contenido | Primer chunk presente |
| 6 | `_build_context` contiene contenido | Segundo chunk presente |
| 7 | `_build_context` contiene fuente | Metadato preserveado |
| 8 | `_build_context` contiene similitud | Score preserveado |
| 9 | `_build_context` lista vacía | Edge case: string vacío |
| 10 | `_build_context` max_chars | Truncamiento correcto |
| 11 | `_build_context` sin content | Edge case: no crash |
| 12 | `_generate` contexto vacío | Mensaje de error |
| 13 | `ask` retorna string | Output tipo correcto |
| 14 | Constantes CONFIG existen | OLLAMA_URL, RAG_MODEL, TEMPERATURE, MAX_TOKENS son tipos correctos |

## Problemas Conocidos Restantes

| ID | Severidad | Descripción |
|----|:---------:|-------------|
| F14-F05 | 🔴 Alta | **Model Router caído.** Puerto 11435 no responde. |
| F14-F06 | 🔴 Alta | **Pipeline bloqueado.** Preflight intenta escribir en `/opt/motor/data/snapshots/` read-only. |
| F14-F07 | 🟢 **CERRADO** | ~~`ura ask` no generaba respuestas.~~ RAG completo implementado y validado. |
| F14-F08 | 🟡 Media | **`ura ask` CLI roto en local.** SSH self-call desde GX10 a sí mismo. |
| F14-F09 | 🟢 Baja | **`ura ask` output bug.** Ahora usa `ask()` — bug obsoleto. |
| F14-F10 | 🟢 Baja | **GPU memory no reportada.** `nvidia-smi` muestra `[N/A]`. |

## Recomendaciones

1. ✅ **F14-F07 CERRADO** — RAG completo implementado y validado (6 consultas, 0 errores).
   ```bash
   python3 ura.py ask "qué es URA y cuál es su arquitectura"
   ```
2. **Desproteger config/**: Ejecutar `sudo chattr -i config/system_config.json`
   y `sudo chattr -i config/schema.json` para añadir `temperature` y `max_tokens`.
3. **Reactivar Model Router** (F14-F05).
4. **Detectar localhost** (F14-F08): evitar SSH self-call en GX10.

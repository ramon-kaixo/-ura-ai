# F14.5 — Análisis Forense de `ura ask` (F14-F07)

> **Propósito:** Determinar por qué `ura ask` no genera respuesta LLM
> **Regla:** No modificar código. Solo analizar.
> **Fecha:** 2026-07-15

## 1. Punto de Entrada

| Capa | Archivo | Línea | Función |
|------|---------|:-----:|---------|
| CLI wrapper | `ura.py` | 49 | `_motor_main()` |
| Dispatcher | `motor/cli/main.py` | 143 | `URA_COMMANDS["ask"](config, raw_args)` |
| Handler | `motor/cli/cmd_ura.py` | 420 | `cmd_ask(config, args)` |

## 2. Call Graph Completo

```
ura.py:49  main()
  → motor/cli/main.py:143  URA_COMMANDS["ask"](config, raw_args)
    → motor/cli/cmd_ura.py:420  cmd_ask(config, args)
      │
      ├── [línea 422] Extrae pregunta de sys.argv
      ├── [línea 430] shlex.quote(question)
      ├── [línea 431-436] Construye string Python:
      │     "from core.memory_engine import query; r=query('...'); "
      │     "for x in r: print(f\"[{x.get('')}] "
      │     "({x.get('',0):.2f}) {x.get('', '')[:200]}\")"
      │     ★ chr(39)+chr(39) = '' (empty string) como key de dict
      │
      ├── [línea 437] Construye comando SSH:
      │     f'cd ~/URA/ura_ia_1972/ && python3 -c "{inner_py}"'
      │     TARGET = "10.164.1.99"  (hardcoded)
      │
      └── [línea 438] Ejecuta vía SubprocessExecutor:
            _executor.run(["ssh", "10.164.1.99", cmd], ...)
            ↑ EL FLUJO TERMINA AQUÍ  ↑
            (retorna exit code del SSH)
```

**En GX10 (remoto) se ejecuta:**

```
python3 -c "from core.memory_engine import query; r=query('...'); for x in r: print(...)"
  → core/memory_engine.py:198  query(question, top_k=5)
    │
    ├── [línea 202] _get_qdrant() → QdrantClient.instancia()
    ├── [línea 207] qdrant.buscar_documentos(question, limit=5)
    │     └── motor/core/qdrant_client.py:348  buscar_documentos()
    │           ├── [línea 350] self.generar_embedding(query_texto)
    │           │     └── [línea 209] generar_embedding()
    │           │           └── [línea 169] generar_embedding_async()
    │           │                 └── httpx POST http://localhost:11434/api/embed
    │           │                     {"model": "nomic-embed-text", "input": texto}
    │           │                     ★ LLAMA A OLLAMA (solo embeddings)
    │           │
    │           └── [línea 351] buscar_por_similitud(vector, collection, limit)
    │                 └── [línea 326] qdrant_client.query_points(...)
    │                       ★ LLAMA A QDRANT (solo búsqueda vectorial)
    │
    ├── [línea 217] Filtra por SIMILARITY_THRESHOLD = 0.7
    └── [línea 220-227] Construye list[dict] con:
          {content, source, chunk_index, similarity}
          ★ NO HAY MÁS PROCESAMIENTO  ★
          ★ NO HAY LLAMADA A LLM DE GENERACIÓN  ★
          ★ NO HAY MODEL ROUTER  ★
          ★ NO HAY MEMORY  ★
          ★ NO HAY CONSENSUS  ★
```

## 3. Archivos Implicados y Responsabilidades

| Archivo | Rol en el flujo | ¿Generación? |
|---------|-----------------|:------------:|
| `ura.py:49` | Punto de entrada. Delega a `motor/cli/main.py` | ❌ |
| `motor/cli/main.py:143` | Dispatcher. Asocia "ask" → `cmd_ask` | ❌ |
| `motor/cli/cmd_ura.py:420` | **Handler.** Construye SSH command, lo ejecuta, retorna | ❌ |
| `core/memory_engine.py:198` | `query()`. Busca chunks en Qdrant, retorna lista | ❌ |
| `motor/core/qdrant_client.py:209` | `generar_embedding()`. Embeddings vía Ollama (nomic-embed-text) | ❌ |
| `motor/core/qdrant_client.py:317` | `buscar_por_similitud()`. Query Qdrant | ❌ |
| `motor/core/qdrant_client.py:348` | `buscar_documentos()`. Orquesta embed + search | ❌ |

## 4. Punto Exacto donde se Interrumpe el Flujo

**`core/memory_engine.py:229` — `return output`**

La función `query()` retorna una lista de chunks. Ese es el final del
procesamiento. Nadie consume esa lista para pasársela a un LLM.

En `cmd_ask` (líneas 432-436), el código Python que se ejecuta vía SSH
solo imprime los resultados con un `for x in r: print(...)`. No hay
ninguna línea que invoque:
- `/api/generate` de Ollama
- `/api/chat` de Ollama
- `core/inferencia/engine.py`
- `core/mochila/providers/ollama.py`
- `core/model_router.py`
- `motor/intelligence/agents/runtime.py`

## 5. Llamadas al Model Router

**No existe ninguna llamada al Model Router en el flujo de `ura ask`.**

Ni directa ni indirectamente. `cmd_ask` no importa ni referencia
`core/model_router.py`. La cadena "model_router" no aparece en
`cmd_ura.py`, `memory_engine.py`, ni `qdrant_client.py`.

El Model Router está implementado en `core/model_router.py` como
un proxy HTTP independiente (puerto 11435) y es usado por:
- `core/inferencia/engine.py:19` — recibe `model_router` como
  dependencia inyectada
- `core/ura_multi_agent.py:100` — health check del router
- `core/mochila/mochila_server.py` — FastAPI que usa providers

Ninguno de estos módulos es invocado por `ura ask`.

## 6. Llamadas a Ollama

**Sí, una llamada: solo para embeddings.**

| Archivo | Línea | Llamada | Propósito |
|---------|:-----:|---------|-----------|
| `motor/core/qdrant_client.py` | 227-228 | `httpx POST /api/embed` | Generar embedding de la consulta |

Modelo usado: **`nomic-embed-text`** (constante en línea 22).

No existe ninguna llamada a:
- `POST /api/generate` (generación de texto)
- `POST /api/chat` (chat conversacional)

## 7. Código Muerto Destinado a Generación

**Sí, existe infraestructura completa de generación que no está conectada a `ura ask`:**

| Componente | Archivo | Estado |
|------------|---------|--------|
| `OllamaProvider.chat()` | `core/mochila/providers/ollama.py:26` | ✅ Funcional. Llama a `POST /api/chat` |
| `InferenciaStreamEngine` | `core/inferencia/engine.py:16` | ✅ Funcional. Streaming con gestión VRAM |
| `Model Router` | `core/model_router.py` | ⚠️ Servicio caído (puerto 11435) |
| `Mochila Server` | `core/mochila/mochila_server.py` | ✅ Servidor FastAPI con endpoints `/v1/chat/completions` |
| `Debate Engine` | `core/debate/debate_engine.py:161` | ✅ Usa `/api/chat` de Ollama |
| `Consensus Engine` | `motor/intelligence/agents/consensus.py` | ✅ Votación multi-agente |
| `MultiAgent Runtime` | `motor/intelligence/agents/runtime.py` | ✅ Orquestador de agentes |
| `core/ura_multi_agent.py:428` | Llamada directa a `POST /api/generate` | ✅ Usado para reparación de código (otro flujo) |

**Ninguno de estos componentes es invocado por `ura ask`.**

## 8. ¿Comportamiento Intencionado o Incompleto?

**Parece una implementación incompleta (RAG sin Generation).**

Evidencia:
1. **Nombre del comando:** `ask "pregunta"` implica que el sistema
   responderá una pregunta. Si solo buscara documentos se llamaría
   `search` o `find`.
2. **Descripción en help:** `"Consulta RAG: busca en documentos y
   responde con contexto."` La palabra "responde" implica generación.
3. **Descripción en código:** `"""Consulta RAG: busca en documentos
   y responde con contexto."""` (idem).
4. **Nombre de la función:** `query()` en `memory_engine.py` — sugiere
   que es la parte de retrieval de un pipeline mayor.
5. **Infraestructura existente:** El proyecto tiene `OllamaProvider`,
   `InferenciaStreamEngine`, `Model Router`, etc. Alguien construyó
   la capacidad de generación pero nunca la conectó a `ura ask`.
6. **Bug de output:** `chr(39)+chr(39)` como key sugiere que el código
   fue escrito rápido, posiblemente como placeholder, y nunca se
   completó.

Contraevidencia (por qué **podría** ser intencionado):
1. El flujo retrieval-only tiene sentido si el caso de uso es
   "buscador documental" no "asistente conversacional".
2. El nombre `memory_engine.py` sugiere que la función es de memoria
   (recuperación), no de diálogo.
3. Hay comandos separados (`pipeline`, `finalize`) para tareas
   complejas.

**Conclusión:** La evidencia apunta a implementación incompleta.
Las 3 pistas más fuertes:
- El help dice "responde con contexto" pero no genera respuesta
- `chr(39)+chr(39)` como key no es intencionado
- Existe infraestructura de generación completa sin conectar

## 9. Cambio Mínimo para Conectar Retrieval → LLM → Respuesta

**Sin modificar la arquitectura existente.**

### Opción A — La más simple (1 archivo, ~15 líneas)

Modificar `cmd_ask` en `motor/cli/cmd_ura.py` para que, tras el SSH
de retrieval, ejecute un segundo SSH que pase los chunks a Ollama
para generar la respuesta.

```python
# Después de obtener los chunks vía SSH (línea 438),
# construir prompt con contexto + pregunta y generar vía Ollama

contexto = " ".join([chunk["content"] for chunk in resultados])
prompt = f"Contexto:\n{contexto}\n\nPregunta: {question}\n\nResponde:"

# Llamar a Ollama directamente (sin Model Router)
# POST http://localhost:11434/api/generate
# {"model": "qwen2.5:7b", "prompt": prompt, "stream": False}
```

**Archivos a modificar:** Solo `motor/cli/cmd_ura.py`.
**Archivos nuevos:** Ninguno.
**Riesgo:** Bajo. No toca arquitectura, solo añade paso al handler.

### Opción B — Usando infraestructura existente (2 archivos, ~30 líneas)

1. En `cmd_ask`, tras obtener chunks, llamar a `OllamaProvider.chat()`
   (en lugar de HTTP directo).

```python
from core.mochila.providers.ollama import OllamaProvider

provider = OllamaProvider()
mensajes = [
    {"role": "system", "content": "Responde usando el contexto dado."},
    {"role": "user", "content": f"Contexto: {contexto}\n\nPregunta: {question}"},
]
async for chunk in provider.chat(modelo="qwen2.5:7b", mensajes=mensajes):
    print(chunk["choices"][0]["delta"].get("content", ""), end="")
```

**Archivos a modificar:** `motor/cli/cmd_ura.py`.
**Depende de:** `core/mochila/providers/ollama.py` (ya existe).

### Opción C — Con Model Router (3 archivos, ~50 líneas)

1. Reactivar Model Router (servicio caído).
2. En `cmd_ask`, tras retrieval, llamar al router vía HTTP.

```python
payload = {
    "model": "razonamiento",  # ruta del router → qwen3:32b-q8_0
    "messages": [
        {"role": "system", "content": "Responde usando el contexto."},
        {"role": "user", "content": f"Contexto: {contexto}\n\n{question}"},
    ],
    "stream": False,
}
r = httpx.post("http://localhost:11435/v1/chat/completions", json=payload)
respuesta = r.json()["choices"][0]["message"]["content"]
```

**Archivos a modificar:** `motor/cli/cmd_ura.py`.
**Depende de:** Reactivar `model-router.service` (systemd).

### Recomendación

**Opción A** por ser la de menor riesgo y menor esfuerzo.
No requiere entender `OllamaProvider`, ni reactivar el Model Router.
Retrofit mínimo: añadir un paso de generación tras el retrieval.

## Resumen

| Pregunta | Respuesta |
|----------|-----------|
| 1. Punto de entrada | `ura.py:49` → `motor/cli/main.py:143` → `motor/cli/cmd_ura.py:420` |
| 2. Funciones ejecutadas | `cmd_ask` → SSH → `query()` → `buscar_documentos()` → `generar_embedding()` + `buscar_por_similitud()` |
| 3. Call graph | Ver sección 2 |
| 4. Dónde termina | `core/memory_engine.py:229` — `return output`. Solo imprime resultados. |
| 5. Model Router | ❌ No se llama en ningún punto del flujo |
| 6. Ollama | ✅ Solo para embeddings (`nomic-embed-text`, `/api/embed`) |
| 7. Código muerto | ✅ `OllamaProvider`, `InferenciaStreamEngine`, `DebateEngine`, `Mochila` — todos existentes, ninguno conectado |
| 8. ¿Intencionado o incompleto? | **Incompleto.** El help dice "responde", la infraestructura de generación existe, pero nunca se conectó. |
| 9. Cambio mínimo | **Opción A:** ~15 líneas en `cmd_ura.py` para pasar chunks → Ollama → respuesta |

# INVENTARIO DE PROVIDERS — core/mochila/providers/

**Fecha:** 2026-07-20  
**Regla:** Ningún archivo se elimina sin demostrar que no tiene consumidores.

---

## 1. base.py — Provider abstracto

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/base.py` (18 líneas) |
| Equivalente motor | `motor/core/llm/base.py` (94 líneas) — **API diferente** |
| Consumidores directos | Todos los providers en `core/mochila/providers/*.py` |
| Consumidores dinámicos | Ninguno |
| Referencias doc/config | Ninguna |
| API pública | `Provider` (abstracto), `ProviderError` |
| Clasificación | **🟡 Activo — necesario mientras existan providers mochila** |
| ¿Eliminar? | ❌ No hasta que se migren todos los providers mochila |

**Nota:** El motor `BaseLLMProvider` tiene API distinta (`generate()/embed()` vs `chat()`). No son intercambiables sin migrar `mochila_server.py`.

---

## 2. __init__.py — Exportador

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/__init__.py` (8 líneas) |
| Equivalente motor | `motor/core/llm/__init__.py` (131 líneas) |
| Consumidores directos | `core/mochila/mochila_server.py:32` (`from core.mochila.providers import GeminiProvider, OllamaProvider, OpenRouterProvider`) |
| Consumidores dinámicos | Ninguno |
| API pública | `DeepSeekProvider`, `GeminiProvider`, `GroqProvider`, `OllamaProvider`, `OpenRouterProvider`, `Provider`, `ProviderError` |
| Clasificación | **🟡 Activo** |
| ¿Eliminar? | ❌ No — necesario para mochila_server.py |

---

## 3. deepseek.py — DeepSeekProvider

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/deepseek.py` (109 líneas) |
| Equivalente motor | **NO EXISTE** |
| Consumidores directos (import) | Solo `core/mochila/providers/__init__.py:2` (`from .deepseek import DeepSeekProvider  # noqa: F401`) |
| Consumidores dinámicos | Ninguno |
| Instanciaciones | **0** — nunca instanciado en ningún archivo |
| Referencias doc/config | Solo referencias al *modelo* `deepseek-coder:6.7b` (Ollama, no el provider API) |
| API pública | `DeepSeekProvider` exportado desde `__init__` |
| Clasificación | **🔴 Muerto — sin consumidores** |
| ¿Eliminar? | ✅ **Sí — no hay riesgo** |

---

## 4. groq.py — GroqProvider

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/groq.py` (109 líneas) |
| Equivalente motor | **NO EXISTE** |
| Consumidores directos (import) | Solo `core/mochila/providers/__init__.py:4` (`from .groq import GroqProvider  # noqa: F401`) |
| Consumidores dinámicos | Ninguno |
| Instanciaciones | **0** — nunca instanciado en ningún archivo |
| Referencias doc/config | Solo mención en `motor/core/llm/openai.py:3` en un comentario |
| API pública | `GroqProvider` exportado desde `__init__` |
| Clasificación | **🔴 Muerto — sin consumidores** |
| ¿Eliminar? | ✅ **Sí — no hay riesgo** |

---

## 5. gemini.py — GeminiProvider (mochila)

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/gemini.py` (139 líneas) |
| Equivalente motor | `motor/core/llm/gemini.py` (171 líneas) — **API diferente** |
| Consumidores directos | `core/mochila/providers/__init__.py:3`, `core/mochila/mochila_server.py:32,47` |
| Instanciaciones | `mochila_server.py:47`: `"gemini": GeminiProvider()` |
| Consumidores dinámicos | Ninguno |
| API pública | `GeminiProvider` exportado desde `__init__`, usado en `mochila_server.py` |
| Clasificación | **🟡 Activo — pero DUPLICADO con motor** |
| ¿Eliminar? | ❌ **No — `mochila_server.py:47` lo usa activamente** |

**Diferencia de API:**
- Mochila: `async chat(messages, model, ...)` → streaming AsyncGenerator
- Motor: `generate(prompt, model, ...)` → str + `embed(texts)` → list[float]
- **No son intercambiables sin migrar `mochila_server.py`**

---

## 6. ollama.py — OllamaProvider (mochila)

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/ollama.py` (210 líneas) |
| Equivalente motor | `motor/core/llm/ollama.py` (210 líneas) — **API diferente** |
| Consumidores directos | `core/mochila/providers/__init__.py:5`, `core/mochila/mochila_server.py:32,45` |
| Instanciaciones | `mochila_server.py:45`: `"ollama": OllamaProvider()` |
| Consumidores dinámicos | Ninguno |
| API pública | `OllamaProvider` exportado desde `__init__`, usado en `mochila_server.py` |
| Clasificación | **🟡 Activo — pero DUPLICADO con motor** |
| ¿Eliminar? | ❌ **No — `mochila_server.py:45` lo usa activamente** |

---

## 7. openrouter.py — OpenRouterProvider (mochila)

| Campo | Valor |
|---|---|
| Archivo | `core/mochila/providers/openrouter.py` (123 líneas) |
| Equivalente motor | `motor/core/llm/openrouter.py` (167 líneas) — **API diferente** |
| Consumidores directos | `core/mochila/providers/__init__.py:6`, `core/mochila/mochila_server.py:32,46` |
| Instanciaciones | `mochila_server.py:46`: `"openrouter": OpenRouterProvider()` |
| Consumidores dinámicos | Ninguno |
| API pública | `OpenRouterProvider` exportado desde `__init__`, usado en `mochila_server.py` |
| Clasificación | **🟡 Activo — pero DUPLICADO con motor** |
| ¿Eliminar? | ❌ **No — `mochila_server.py:46` lo usa activamente** |

---

## TABLA DE MIGRACIÓN

| Provider antiguo | Provider nuevo | Archivos que cambiar | Riesgo | Funcionalidad faltante en nuevo |
|---|---|---|---|---|
| `deepseek.py` | **Ninguno** (eliminar) | `__init__.py:2` (quitar import) | ✅ Bajo — 0 instanciaciones | N/A — muerto |
| `groq.py` | **Ninguno** (eliminar) | `__init__.py:4` (quitar import) | ✅ Bajo — 0 instanciaciones | N/A — muerto |
| `gemini.py` | `motor/core/llm/gemini.py` | `mochila_server.py:32,47` + adaptar API | 🟡 Medio | Motor no tiene `chat()` async streaming |
| `ollama.py` | `motor/core/llm/ollama.py` | `mochila_server.py:32,45` + adaptar API | 🟡 Medio | Motor no tiene `chat()` async streaming |
| `openrouter.py` | `motor/core/llm/openrouter.py` | `mochila_server.py:32,46` + adaptar API | 🟡 Medio | Motor no tiene `chat()` async streaming |
| `base.py` | `motor/core/llm/base.py` | Todos los providers mochila | 🔴 Alto | BaseLLMProvider tiene API diferente |

---

## CONCLUSIÓN

**Pueden eliminarse ahora mismo (0 riesgo):**
- `core/mochila/providers/deepseek.py` — 0 instanciaciones, solo `# noqa: F401`
- `core/mochila/providers/groq.py` — 0 instanciaciones, solo `# noqa: F401`

**Requieren migración de mochila_server.py (mediano riesgo):**
- `core/mochila/providers/gemini.py` — activo en mochila_server.py:47
- `core/mochila/providers/ollama.py` — activo en mochila_server.py:45
- `core/mochila/providers/openrouter.py` — activo en mochila_server.py:46
- `core/mochila/providers/base.py` — necesario mientras existan los 3 anteriores
- `core/mochila/providers/__init__.py` — necesario mientras existan providers activos

**Para migrar los 3 activos, `mochila_server.py` necesita:**
1. Usar `chat()` de motor o adaptar a `generate()` + `embed()`
2. Manejar streaming (motor no lo soporta actualmente)
3. Esto es un refactor mayor que merece una sesión aparte

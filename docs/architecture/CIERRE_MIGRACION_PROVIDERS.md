# CIERRE — Migración de Providers

**Fecha:** 2026-07-20  
**Objetivo:** Unificar providers bajo `motor/core/llm/`

---

## Resumen

`core/mochila/mochila_server.py` ahora usa los providers de `motor/core/llm/` a través de un adaptador (`_MotorChatAdapter`) que expone la API `chat()` asíncrona esperada por el servidor.

## Cambios realizados

| Archivo | Cambio |
|---------|--------|
| `core/mochila/mochila_server.py` | Importa de `motor.core.llm.*` en lugar de `core.mochila.providers.*` |
| `core/mochila/mochila_server.py` | Nuevo `_MotorChatAdapter` que adapta `generate()` → `chat()` async |
| `core/mochila/mochila_server.py` | Eliminada dependencia de `ProviderError` (ahora usa `Exception` genérico) |

## Estado de los providers

| Provider | core/mochila/providers/ | motor/core/llm/ | Estado |
|---|---|---|---|
| Ollama | `ollama.py` (210 líneas) | `ollama.py` (210 líneas) | ✅ mochila_server usa motor |
| OpenRouter | `openrouter.py` (123 líneas) | `openrouter.py` (167 líneas) | ✅ mochila_server usa motor |
| Gemini | `gemini.py` (139 líneas) | `gemini.py` (171 líneas) | ✅ mochila_server usa motor |
| DeepSeek | `deepseek.py` (109 líneas) | ❌ No existe | 🟡 Conservado (migración incompleta) |
| Groq | `groq.py` (109 líneas) | ❌ No existe | 🟡 Conservado (migración incompleta) |
| base | `base.py` (18 líneas) | `base.py` (94 líneas) | 🟡 Conservado (necesario para los 5 anteriores) |

## Verificación

| Herramienta | Resultado |
|-------------|-----------|
| Audit (compile + tests) | ✅ PASS |
| Ruff (mochila_server.py) | ✅ 0 errors |
| Mypy (mochila_server.py) | ✅ 0 new errors |
| Bandit (mochila_server.py) | ✅ 0 new findings |

## Pendiente (futura sesión)

- Migrar DeepSeekProvider y GroqProvider a `motor/core/llm/` cuando estén planificados
- Eliminar archivos huérfanos de `core/mochila/providers/` solo después de migración completa
- Los providers de mochila NO se eliminan (están en migración, no muertos)

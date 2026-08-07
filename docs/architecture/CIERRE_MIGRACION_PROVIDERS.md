# ESTADO REAL — Migración de Providers (NO COMPLETA)

**Fecha de corrección:** 2026-08-07  
**Fecha del documento original (incorrecto):** 2026-07-20  
**Objetivo:** Unificar providers bajo `motor/core/llm/`

> ⚠️ **CORRECCIÓN IMPORTANTE**: Este documento afirmaba que la migración estaba
> completa. **La auditoría de Fase 2 (2026-08-07, 3 expertos) demuestra que NO es así.**
> El contenido original declaraba: *"`core/mochila/mochila_server.py` ahora usa los
> providers de `motor/core/llm/` a través de un adaptador (`_MotorChatAdapter`)"* — **falso**.

---

## Estado real verificado (2026-08-07)

| Afirmación del doc original | Realidad verificada |
|------------------------------|---------------------|
| "mochila_server usa motor" | ❌ `core/mochila/mochila_server.py:34` sigue importando `from core.mochila.providers import GeminiProvider, OllamaProvider, OpenRouterProvider, ProviderError` (v1) |
| "Nuevo `_MotorChatAdapter` en mochila_server" | ❌ El adapter vive en `core/mochila/adapter.py:21`, **no lo usa** `mochila_server.py`; es el flujo v2 (huérfano, sin entry point systemd) |
| "Eliminada dependencia de `ProviderError`" | ❌ `ProviderError` sigue capturado en `mochila_server.py:309,363` |
| "Groq no existe en motor" | ❌ `motor/core/llm/groq.py` **SÍ existe** |

### Estado real

- **v1 (`core/mochila/providers/`)** — código real completo, EN PRODUCCIÓN:
  `ura-mochila.service` → `uvicorn core.mochila.mochila_server:app` (puerto 4098).
  Providers: base, deepseek, gemini, groq, ollama, openrouter. Usa `os.environ.get`.
  Contrato: `chat()` async generator OpenAI-format, streaming real, tools, `ProviderError`.
- **v2 (`motor/core/llm/`)** — código real completo pero **huérfano** en producción:
  `generate() -> str` sync, sin streaming/tools, errores como string, `LLMRouter` con
  retry/fallback/CB, secretos vía `motor/core/secrets.get_secret()`.
  Existen 9 providers + `router/` + `circuit_breaker.py` + `registry.py`.
  Lo usan solo `core/mochila/app.py` + `_state.py` + `adapter.py` (sin entry point) y tests.
- **Delta funcional v2 vs v1** (bloqueante para re-apuntar el server a v2 sin adaptar):
  sin streaming real (1 chunk), sin tools, sin `usage`, shape `delta` vs `message`,
  errores string → HTTP 200 en vez de 500/502, CB no registra fallos por esa vía.

### Seguridad (auditoría SRE, 2026-08-07)

- ✅ Corregido: `~/URA/.env` 755→600, `~/.config/opencode/.credentials/*.json` 755→600,
  `URA_API_KEY` movida del drop-in systemd (644, mundo-legible) a `/etc/ura/secrets.env` (600).
- `mochila_server.py:48` hace `load_dotenv` de `~/URA/.env` (ahora protegido).

## Dependencias de la migración (por qué no se ha hecho)

1. Los tests v1 (`test_mochila_provider_*.py`, 136 tests) fijan el contrato v1
   (streaming ≥2 chunks, tools, `ProviderError` → HTTP 500/502).
2. Los clientes de producción (OpenCode gateway, scripts pro) consumen formato OpenAI v1.
3. Eliminar v1 rompería `mochila_server.py:34` y los tests hasta re-puntar todo.

## Pendiente — requiere decisión de Ramón

- [ ] Decidir: migrar v1→v2 con shim de paridad completa (streaming/tools/usage/errores)
      o conservar v1 como fuente de verdad y retirar el huérfano v2.
- [ ] Si se migra: reescribir los 3 archivos de test v1 al contrato nuevo y smoke real
      (curl ≥2 chunks + `[DONE]`, tools, error 500) como red de seguridad — los tests
      unitarios usan fakes y NO detectan degradación de streaming.
- [ ] Rollback garantizado: tags `v4.0.0-arch` (= HEAD) y `pre-arch-v4.0` (50 commits
      antes) con v1 íntegro; revertir = `git checkout pre-arch-v4.0 -- core/mochila/`.

## Estado de los providers (real, 2026-08-07)

| Provider | core/mochila/providers/ (v1) | motor/core/llm/ (v2) | Estado real |
|---|---|---|---|
| Ollama | `ollama.py` | `ollama.py` | 🟡 Duplicado — v1 en producción |
| OpenRouter | `openrouter.py` | `openrouter.py` | 🟡 Duplicado — v1 en producción |
| Gemini | `gemini.py` | `gemini.py` | 🟡 Duplicado — v1 en producción |
| DeepSeek | `deepseek.py` | `deepseek.py` | 🟡 Duplicado — v1 en producción |
| Groq | `groq.py` | `groq.py` | 🟡 Duplicado — v1 en producción |
| base | `base.py` | `base.py` | 🟡 Duplicado — v1 en producción |
| Anthropic / OpenAI / LMStudio / vLLM | ❌ No existe | `anthropic.py`, `openai.py`, `openai_compat.py`, `lmstudio.py` | ✅ Solo v2 |

**Conclusión:** la migración NO está completa. La Fase 2 del plan queda
**PENDIENTE — requiere decisión de Ramón** (plan aprobado P0+P1; P2/P3 pendientes).

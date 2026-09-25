# ESTADO REAL — Migración de Providers (P0-P2 COMPLETAS, MODO DUAL v1+v2)

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

## Decisión adoptada (Ramón, 2026-08-07): MODO DUAL — nada se elimina

- [x] ✅ **NO se elimina v1** (`core/mochila/providers/`) — sigue como fuente de verdad en
      producción (`ura-mochila.service`, puerto 4098, flag default `URA_MOCHILA_MOTOR_V2=0`).
- [x] ✅ **NO se elimina v2** (`motor/core/llm/`) — activable en caliente vía
      `URA_MOCHILA_MOTOR_V2=1` (modo dual sin pérdida de código).
- [x] P2 completado — shim de paridad: `_MotorChatAdapter` en `core/mochila/adapter.py`
      con streaming real, tools round-trip, `usage`, `ProviderError`→502, degrading a v1.
- [x] `URA_API_KEY` unificada: `~/.env` = `/etc/ura/secrets.env` = proceso vivo
      (bloque de hash `daa1764f…`), ambas `600` — no hay claves divergentes.
- [x] Red de seguridad: smoke E2E real (39 chunks + `[DONE]`, tools, 502) + suite
      mochila 154 passed + motor LLM 361 passed (2 skipped) + `make validate` OK.
- [x] Rollback garantizado: tags `v4.0.0-arch` (= HEAD) y `pre-arch-v4.0` (50 commits
      antes) con v1 íntegro; revertir = `git checkout pre-arch-v4.0 -- core/mochila/`.

## Pendiente (post-decisión, no bloqueante)

- [ ] Adopción en producción del modo v2: `URA_MOCHILA_MOTOR_V2=1` en
      `ura-mochila.service` (EnvironmentFile) + smoke 4098 + revert fácil (P2.5 opcional).

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

**Conclusión:** la migración está **P0+P2 COMPLETA** con **modo dual v1+v2** (decisión de
Ramón: conservar todo el código construido). v1 sigue en producción; v2 disponible con
shim de paridad verificada por smoke E2E. No se elimina código — sin pérdida.

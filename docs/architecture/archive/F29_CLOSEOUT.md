# Fase 29 — Conversational Assistant — Closeout

## Summary
- **Date:** 2026-07-20
- **Tag:** `v0.29.0-fase29`
- **Commit:** `a9132db`
- **Status:** Stable

## Delivered
### F29 Original (B1-B9)
- Conversation engine, context, intent, style, planner, tools, personality, learning, management
- 31 files deployed en `motor/assistant/`

### F29.5 (Interruptions, auto-mode, episodic memory, trends)
- `interruption.py`, `auto_mode.py`, `episodic_memory.py`, `trends.py`

### F29.6 (Sentiment, corrective learning, proactive memory)
- `sentiment.py`, `corrective_learning.py`, `proactive_memory.py`

### F29.7 (LLM integration via Model Router + Ollama)
- `llm_bridge.py`

### Post-F29 Improvements
- F2: Recordar tema al reconectar, detectar cambio de idioma, decir "no se", confirmar destructivas, follow-up
- F4: Correcciones + preferencias conectadas al system prompt
- F1: NoteTool con persistencia configurable (`config.db_for()`)
- F3: GitBranchTool, GitCommitTool
- F5: `ura_chat.py` CLI interactivo
- F6: `cleanup_old()` en message_store, `cleanup_assistant.py` script

## Quality
| Metric | Value |
|--------|-------|
| Tests | 97/97 assistant tests |
| Suite time | 2.2s |
| Ruff (assistant) | 0 errores nuevos |
| Bandit | 0 High, 5 Medium (conocidos) |
| Cobertura (assistant) | 15% (mejora continua) |

## Security Fixes
- `eval()` reemplazado por `_SafeCalculator` (AST interpreter sin builtins)
- `auth.py` verifica Bearer token contra `URA_API_KEY`
- Bind a `0.0.0.0` configurable vía `URA_HOST`

## Deployment
- **GX10**: `http://10.164.1.99:8003`
- **Service**: `ura-assistant.service` (systemd)
- **Model**: `qwen2.5:7b` via Ollama

## Known Gaps
- Cobertura 15% en assistant module
- `auth.py` stub funcional pero sin JWT/rotación
- Sin documentación de API para endpoints nuevos (F2-F6)
- Sin closeout previo para F25-F28 (creado en esta auditoría)

## Exit Criteria
| Criterio | Estado |
|----------|--------|
| Compilación | ✅ |
| Ruff 0 nuevos | ✅ |
| Tests sin regresión | ✅ |
| Tag creado | ✅ |
| Documentación actualizada | ✅ |
| Working tree limpio | ✅ |

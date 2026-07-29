# Tarea T3 — external_audit.sh: verificar output, quitar Claude/GPT-4o

**Fecha:** 2026-07-29
**Commit:** `69b0593`
**Estado:** ✅ Completado

## Cambios

**Un archivo:** `scripts/pro/external_audit.sh`

| Antes | Después |
|-------|---------|
| 3 LLMs: Claude, GPT-4o, Ollama local | Solo Ollama local |
| Sin verificación de output | `[ ! -s "$OLLAMA_FILE" ] \|\| [ "$(wc -c < "$OLLAMA_FILE")" -lt 500 ] → exit 1` |
| `echo "Análisis: $CLAUDE_FILE, $GPT_FILE, $OLLAMA_FILE"` | `echo "Análisis Ollama: $OLLAMA_FILE"` |

## Verificación

```bash
bash -n scripts/pro/external_audit.sh  # Sintaxis OK
```

-27 líneas (−21 Claude/GPT-4o, +6 verificación).

# T5: Auditoría Externa — Reporte

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~5 min

## Cambios Realizados

### Option B: Timeout 300 → 600
En `_call_ollama()` de `scripts/pro/external_audit.sh`:
```bash
curl -s --max-time 600  # antes: --max-time 300
```

(Nota: timeout en model_router.py y proxy.py ya fue actualizado
de 300→600 en commit a8e62ac.)

### Option A: Auto-selección de modelo
Añadida lógica en `_call_ollama()`:
```bash
local prompt_tokens=$(echo "$prompt" | wc -c)
if [ "$prompt_tokens" -gt 2000 ] && [ "$model" != "qwen2.5-coder:14b" ]; then
    model="qwen2.5-coder:14b"
    echo "Prompt grande (${prompt_tokens} chars), usando qwen2.5-coder:14b"
fi
```

El modelo por defecto ya es `qwen2.5-coder:14b` (linea 18 del script).
El auto-select es red de seguridad para prompts grandes.

## Commit
`d8dfa6e` — feat: external_audit timeout 300->600s + auto-model selection

## Verificación Pendiente
Ejecutar `bash scripts/pro/external_audit.sh manual` para verificar
que termina sin timeout y genera salida. Requiere ~5 min (10 secciones).

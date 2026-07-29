#!/usr/bin/env bash
# audit_diff.sh — Criba automática de diffs vía Ollama multi-modelo
# Uso: bash audit_diff.sh <commit-hash>
set -euo pipefail

HASH="${1:-}"
[ -z "$HASH" ] && echo "Uso: $0 <commit-hash>" >&2 && exit 1
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="$REPO/docs/audits_internal"
mkdir -p "$OUTDIR"

DIFF=$(git show "$HASH" 2>/dev/null) || { echo "Error: no se puede mostrar $HASH" >&2; exit 1; }
[ -z "$DIFF" ] && { echo "Error: diff vacío" >&2; exit 1; }

SCREENING_PROMPT="Eres un revisor de código. Analiza este diff en 15 líneas máximo. Busca bugs, mocks en tests, problemas de seguridad, o código que pueda romperse en producción. Responde solo con una de estas etiquetas al inicio: [OK] si no hay problemas graves, [BUG] si hay bug, [SEGURIDAD] si hay riesgo de seguridad, [MOCK] si hay mocks que ocultan lógica real, [CRITICO] si hay problema crítico. Luego explica brevemente.

$DIFF"

DEEP_PROMPT="Eres un revisor de código senior. Analiza este diff en profundidad. Identifica: 1) Bugs lógicos 2) Problemas de seguridad 3) Mocks que ocultan lógica real 4) Regresiones potenciales 5) Deuda técnica introducida. Propón fixes específicos.

$DIFF"

_call_ollama() {
    local model="$1" prompt="$2" outfile="$3" timeout="$4"
    local escaped
    escaped=$(echo "$prompt" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" 2>/dev/null) || return 1
    curl -s --max-time "$timeout" "http://localhost:11434/api/generate" \
        -d "{\"model\": \"$model\", \"prompt\": $escaped, \"stream\": false}" 2>/dev/null | \
    python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('response',''))
except: pass
" 2>/dev/null > "$outfile"
    [ -s "$outfile" ] && return 0 || return 1
}

echo "[$(date '+%H:%M:%S')] Criba con qwen2.5-coder:14b..." >&2
SCREENING_FILE="$OUTDIR/${HASH}_14b.txt"
if _call_ollama "qwen2.5-coder:14b" "$SCREENING_PROMPT" "$SCREENING_FILE" 120; then
    echo "[$(date '+%H:%M:%S')] ✅ Criba 14B: $SCREENING_FILE" >&2
else
    echo "[$(date '+%H:%M:%S')] [ERROR] 14B falló" >&2
    exit 1
fi

RESPONSE=$(cat "$SCREENING_FILE")
if echo "$RESPONSE" | grep -qiE "CRITICO|BUG|SEGURIDAD|MOCK"; then
    echo "[$(date '+%H:%M:%S')] ⚠️  Criba detectó señal de alerta, enviando a 32B..." >&2
    DEEP_FILE="$OUTDIR/${HASH}_32b.txt"
    if _call_ollama "qwen2.5-coder:32b" "$DEEP_PROMPT" "$DEEP_FILE" 300; then
        echo "[$(date '+%H:%M:%S')] ✅ Análisis profundo 32B: $DEEP_FILE" >&2
    else
        echo "[$(date '+%H:%M:%S')] [ERROR] 32B también falló" >&2
        exit 1
    fi
else
    echo "[$(date '+%H:%M:%S')] ✅ Criba: sin alertas graves" >&2
fi

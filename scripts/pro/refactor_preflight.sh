#!/usr/bin/env bash
set -euo pipefail

URA_ROOT="${URA_ROOT:-$HOME/URA/ura_ia_1972}"
BLOCK_FLAG="$URA_ROOT/.refactor_blocked"
OLLAMA_URL="${OLLAMA_URL:-http://10.164.1.99:11434}"

rc=0

fail() {
    echo "PREFLIGHT FAIL: $*" >&2
    rc=1
}

pass() {
    echo "  [OK] $*"
}

echo "=== Preflight Check — $(date) ==="

# 1. Block flag
if [ -f "$BLOCK_FLAG" ]; then
    reason=$(python3 -c "import json; d=json.load(open('$BLOCK_FLAG')); print(d.get('reason','?'))" 2>/dev/null || echo "desconocido")
    fail ".refactor_blocked existe — razon: $reason"
    echo "  Para desbloquear: rm $BLOCK_FLAG && resolver la causa"
else
    pass ".refactor_blocked no existe"
fi

# 2. ruff executable
ruff_bin=""
if command -v ruff &>/dev/null; then
    ruff_bin="ruff"
elif [ -x "$HOME/.local/bin/ruff" ]; then
    ruff_bin="$HOME/.local/bin/ruff"
elif [ -x "$URA_ROOT/.venv/bin/ruff" ]; then
    ruff_bin="$URA_ROOT/.venv/bin/ruff"
fi

if [ -z "$ruff_bin" ]; then
    fail "ruff no encontrado. Instalar: pip install ruff"
else
    ver=$("$ruff_bin" --version 2>&1 | head -1)
    pass "ruff: $ver"
fi

# 3. Ollama reachable
if curl -s --max-time 5 "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    pass "Ollama responde en $OLLAMA_URL"
else
    fail "Ollama no responde en $OLLAMA_URL"
fi

# 4. Disk > 5%
disk_pct=$(df "$URA_ROOT" --output=pcent 2>/dev/null | tail -1 | tr -d ' %')
if [ -n "$disk_pct" ]; then
    if [ "$disk_pct" -lt 95 ]; then
        used_pct=$((100 - disk_pct))
        pass "Disco: $disk_pct% libre"
    else
        fail "Disco: $disk_pct% libre (umbral: 5%)"
    fi
fi

# 5. RAM > 2GB
if python3 -c "
import psutil
ram = psutil.virtual_memory()
gb = ram.available / (1024**3)
exit(0 if gb > 2 else 1)
" 2>/dev/null; then
    avail=$(python3 -c "import psutil; print(f'{psutil.virtual_memory().available / 1024**3:.1f}GB')")
    pass "RAM disponible: $avail"
else
    # fallback: /proc/meminfo
    if [ -f /proc/meminfo ]; then
        avail_kb=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        avail_gb=$(python3 -c "print(round($avail_kb / 1024**2, 1))")
        if [ "${avail_kb:-0}" -gt 2097152 ]; then
            pass "RAM disponible: ${avail_gb}GB"
        else
            fail "RAM disponible: ${avail_gb}GB (umbral: 2GB)"
        fi
    else
        echo "  [WARN] No se pudo verificar RAM"
    fi
fi

# 6. No workers previos
running=$(pgrep -f "refactor_large_functions.py" 2>/dev/null | wc -l | tr -d ' ')
if [ "$running" -gt 0 ]; then
    fail "Hay $running workers previos corriendo. Mata primero: pkill -f refactor_large_functions"
else
    pass "Sin workers previos corriendo"
fi

# Summary
echo "=== Preflight: $([ $rc -eq 0 ] && echo 'TODO OK' || echo 'FALLOS ENCONTRADOS') ==="
exit $rc

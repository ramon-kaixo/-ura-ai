#!/bin/bash
set -euo pipefail
shopt -s nullglob

INBOX="$HOME/URA/ura_ia_1972/inbox"
REPO="$HOME/URA/ura_ia_1972"
cd "$REPO"
source .venv/bin/activate
# Auto-registro en el Registry (heartbeat)
curl -s -X POST http://127.0.0.1:5100/agents \
    -H "Content-Type: application/json" \
    -d "{\"id\":\"inbox_watch\",\"type\":\"buzon\",\"ip\":\"127.0.0.1\",\"port\":0,\"last_seen\":\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
    || true

for file in "$INBOX"/*; do
    [ -f "$file" ] || continue
    echo "Procesando: $(basename "$file")"

    mkdir -p /tmp/ura_inbox
    cp "$file" /tmp/ura_inbox/

    # Rodillo 0: Preflight
    if ! python3 scripts/preflight_check.py "$file"; then
        echo "🔴 Rodillo 0 (preflight) falló para $(basename "$file")"
        mv "$file" "$REPO/quarantine/"
        continue
    fi

    # Rodillo 1: ruff check
    if ! ruff check --fix "$file"; then
        echo "🔴 Rodillo 1 (ruff) falló para $(basename "$file")"
        mv "$file" "$REPO/quarantine/"
        continue
    fi

    # Rodillo 1b: autoflake
    if ! autoflake --in-place --remove-all-unused-imports "$file"; then
        echo "🔴 Rodillo 1b (autoflake) falló para $(basename "$file")"
        mv "$file" "$REPO/quarantine/"
        continue
    fi

    # Rodillo 2: ruff format
    if ! ruff format "$file"; then
        echo "🔴 Rodillo 2 (ruff format) falló para $(basename "$file")"
        mv "$file" "$REPO/quarantine/"
        continue
    fi

    # Rodillo 4: pytest
    if ! python3 -m pytest tests/test_core_basics.py tests/test_consensus_system.py -q -x; then
        echo "🔴 Rodillo 4 (pytest) falló para $(basename "$file")"
        mv "$file" "$REPO/quarantine/"
        continue
    fi

    # Todos los rodillos superados → mover a destino
    if [[ "$file" == *.py ]]; then
        mv "$file" "$REPO/agents/"
    elif [[ "$file" == *.sh ]]; then
        mv "$file" "$REPO/scripts/"
    else
        mkdir -p "$REPO/otros"
        mv "$file" "$REPO/otros/"
    fi
    git add -A && git commit -m "Instalado desde inbox: $(basename "$file")" 2>/dev/null || true
    git tag "v$(date +%Y%m%d_%H%M%S)_inbox" 2>/dev/null || true
    curl -s -X POST http://127.0.0.1:5100/agents \
         -H "Content-Type: application/json" \
         -d "{\"id\":\"$(basename "$file")\",\"type\":\"programa\",\"installed\":\"$(date)\"}" || true
    echo "✅ Instalado con éxito."

# Activar sandbox de Aprendizaje
trigger_learning_sandbox() {
    echo "🧠 Activando sandbox de Aprendizaje..."
    if [ -f "$REPO/sandbox/Aprendizaje/scripts/run.sh" ]; then
        bash "$REPO/sandbox/Aprendizaje/scripts/run.sh" --mode=on-demand &
    fi
}
trigger_learning_sandbox

done

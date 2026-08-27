#!/usr/bin/env bash
# parallel-merge-driver.sh — Merge secuencial de ramas a develop
# Uso: ./scripts/pro/parallel-merge-driver.sh [--auto]
# --auto: crea tarea en TaskQueue si hay conflictos
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

AUTO_MODE=false
[[ "${1:-}" == "--auto" ]] && AUTO_MODE=true

MERGE_ORDER=("feature/opencode-gx10" "feature/opencode-web" "feature/opencode-mac")
RESULTS=()

# Asegurar que estamos en develop
git checkout develop 2>/dev/null || {
    echo "[ERROR] No se puede checkout a develop"
    exit 1
}
git pull origin develop 2>/dev/null || true

for BRANCH in "${MERGE_ORDER[@]}"; do
    # Verificar si la rama existe en remoto
    if ! git show-ref --verify --quiet "refs/remotes/origin/$BRANCH" 2>/dev/null; then
        if ! git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
            echo "[SKIP] $BRANCH no existe"
            RESULTS+=("$BRANCH:SKIP")
            continue
        fi
    fi

    echo "[MERGE] Integrando $BRANCH → develop"

    # Intentar merge
    if git merge --no-ff -m "merge: $BRANCH → develop" "origin/$BRANCH" 2>/dev/null; then
        echo "[OK] $BRANCH mergeado sin conflictos"
        RESULTS+=("$BRANCH:OK")
    else
        echo "[CONFLICT] $BRANCH tiene conflictos"
        git merge --abort 2>/dev/null || true
        RESULTS+=("$BRANCH:CONFLICT")

        if [[ "$AUTO_MODE" == "true" ]]; then
            # Crear tarea en TaskQueue para resolución de conflictos
            PAYLOAD=$(cat <<EOF
{
  "type": "CONFLICT_RESOLUTION",
  "title": "Resolver conflictos de merge: $BRANCH → develop",
  "priority": "high",
  "payload": {"branch": "$BRANCH", "target": "develop"}
}
EOF
)
            curl -s -X POST http://localhost:4097/tasks \
                -H "Content-Type: application/json" \
                -d "$PAYLOAD" 2>/dev/null && \
                echo "[TASK] Tarea creada para resolver conflictos de $BRANCH" || \
                echo "[WARN] No se pudo crear tarea en TaskQueue"
        fi
    fi
done

# Push develop si hubo merges exitosos
OK_COUNT=0
for r in "${RESULTS[@]}"; do
    [[ "$r" == *":OK" ]] && ((OK_COUNT++))
done

if [[ $OK_COUNT -gt 0 ]]; then
    git push origin develop 2>/dev/null || echo "[WARN] Push a develop falló"
fi

echo ""
echo "=== RESUMEN DE MERGE ==="
for r in "${RESULTS[@]}"; do
    BRANCH_NAME="${r%%:*}"
    STATUS="${r##*:}"
    case "$STATUS" in
        OK)       echo "  ✅ $BRANCH_NAME" ;;
        SKIP)     echo "  ⏭️  $BRANCH_NAME (no existe)" ;;
        CONFLICT) echo "  ❌ $BRANCH_NAME (conflictos)" ;;
    esac
done

#!/bin/bash
# install-hooks.sh — instala los hooks de URA en .git/hooks/
set -e
PROJECT_ROOT=$(dirname "$(dirname "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)")")
HOOKS_DIR="$PROJECT_ROOT/scripts/pro/hooks"

for hook in post-commit; do
    if [ -f "$HOOKS_DIR/$hook" ]; then
        cp "$HOOKS_DIR/$hook" "$PROJECT_ROOT/.git/hooks/$hook"
        chmod +x "$PROJECT_ROOT/.git/hooks/$hook"
        echo "Instalado: .git/hooks/$hook"
    fi
done
echo "Hooks instalados correctamente"

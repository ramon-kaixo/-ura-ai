#!/bin/bash
# Instalador de git hooks de URA.
# Copia los hooks versionados en scripts/hooks/ a .git/hooks/.
# Uso: bash scripts/hooks/install.sh

set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
HOOKS_SRC="$PROJECT_ROOT/scripts/hooks"
HOOKS_DST="$PROJECT_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DST" ]; then
    echo "error: $HOOKS_DST no existe — ¿es un repo git?"
    exit 1
fi

for hook in "$HOOKS_SRC"/*; do
    [ -f "$hook" ] || continue
    name=$(basename "$hook")
    [ "$name" = "install.sh" ] && continue
    cp "$hook" "$HOOKS_DST/$name"
    chmod +x "$HOOKS_DST/$name"
    echo "instalado: $name"
done

echo "hooks instalados correctamente"

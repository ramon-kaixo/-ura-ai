#!/bin/bash
set -euo pipefail
# versionar_conocimiento.sh — Guarda hasta 5 versiones de cada archivo en knowledge/
KNOWLEDGE_DIR="${HOME}/URA/ura_ia_1972/knowledge"
VERSIONS_DIR="${KNOWLEDGE_DIR}/versions"
MAX_VERSIONS=5
mkdir -p "$VERSIONS_DIR"

versionar_archivo() {
    local file="$1"
    local rel_path="${file#$KNOWLEDGE_DIR/}"
    local version_dir="${VERSIONS_DIR}/$(dirname "$rel_path")"
    local base_name
    base_name=$(basename "$file")
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    mkdir -p "$version_dir"

    if [ -f "$file" ]; then
        cp "$file" "${version_dir}/${base_name}.${timestamp}.bak"
        echo "   📦 ${rel_path} → ${base_name}.${timestamp}.bak"
    fi

    local count
    count=$(find "$version_dir" -name "${base_name}.*.bak" -print 2>/dev/null | wc -l | tr -d ' ')
    while [ "$count" -gt "$MAX_VERSIONS" ]; do
        local oldest
        oldest=$(find "$version_dir" -name "${base_name}.*.bak" -exec ls -lt {} + 2>/dev/null | tail -1 | awk '{print $NF}')
        [ -n "$oldest" ] && rm -f "$oldest" && count=$((count - 1))
    done
}

if [ $# -ge 1 ]; then
    for file in "$@"; do
        [ -f "$file" ] && versionar_archivo "$file"
    done
else
    find "$KNOWLEDGE_DIR" -name "*.json" -not -path "*/versions/*" -print 2>/dev/null | while IFS= read -r file; do
        versionar_archivo "$file"
    done
fi

echo "✅ Versionado completado"

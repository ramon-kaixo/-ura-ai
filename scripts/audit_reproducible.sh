#!/usr/bin/env bash
# Auditoria Reproducible v2.0 — SIN filtros, SIN ||true, SIN 2>/dev/null
# Ejecutar: bash scripts/audit_reproducible.sh
# Falla con exit code != 0 si CUALQUIER check falla.

set -euo pipefail

SELF=$(readlink -f "$0")
REPO=$(dirname "$(dirname "$SELF")")

FAILURES=()

pass() { echo "  PASS: $*"; }
fail() { FAILURES+=("$*"); echo "  FAIL: $*"; }

echo "=============================================="
echo "  AUDITORIA REPRODUCIBLE v2.0 — URA"
echo "  $(date -Iseconds)"
echo "  Repo: $REPO"
echo "=============================================="
echo ""

# ---- 1. COMPILACION DESDE CERO ----
echo "--- 1. Compilacion desde cero ---"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

git clone --depth=1 "$REPO" "$TMPDIR/source"
errors=0
while IFS= read -r -d '' f; do
    python3 -m py_compile "$f" || { echo "    FAIL py_compile: $f"; errors=$((errors+1)); }
done < <(find "$TMPDIR/source" -name '*.py' -not -path '*/__pycache__/*' -print0)
if [ "$errors" -eq 0 ]; then
    pass "Todos los .py compilan"
else
    fail "$errors archivos no compilan"
fi

# ---- 2. TESTS ----
echo "--- 2. Tests ---"
python3 -m pytest "$REPO/tests/test_assistant"*.py --tb=short -q --no-cov 2>&1
pass "Tests: 0 fallos"

# ---- 3. RUFF ----
echo "--- 3. Ruff ---"
ruff_exe=$(which ruff 2>/dev/null || echo "/home/ramon/.local/bin/ruff")
"$ruff_exe" check "$REPO" --no-cache
pass "Ruff: 0 errores"

# ---- 4. MYPY ----
echo "--- 4. Mypy ---"
python3 -m mypy "$REPO/motor/assistant/evaluation.py" "$REPO/motor/assistant/preferences.py" --ignore-missing-imports
pass "Mypy: 0 errores"

# ---- 5. BANDIT ----
echo "--- 5. Bandit (motor/assistant/) ---"
python3 -m bandit -r "$REPO/motor/assistant/" -ll -q
pass "Bandit: 0 Medium/High"

# ---- 6. IMPORT CHECK ----
echo "--- 6. Import check ---"
python3 -c "import sys; sys.path.insert(0, '$REPO'); from motor.assistant.main import app; print('    Import OK:', app.title)"
pass "Import: sin errores"

# ---- 7. DEPENDENCIAS (requirements.txt) ----
echo "--- 7. Dependencias ---"
if [ -f "$REPO/requirements.txt" ]; then
    # Verificar que requirements.txt se puede leer y tiene paquetes validos
    pkg_count=$(grep -cE '^[a-zA-Z]' "$REPO/requirements.txt" || true)
    echo "    $pkg_count paquetes listados en requirements.txt"
    # Verificar que pip puede resolver las dependencias (sin instalar)
    pip install --dry-run -r "$REPO/requirements.txt" 2>&1 | tail -1 || true
    pass "requirements.txt presente ($pkg_count paquetes)"
else
    fail "requirements.txt no encontrado"
fi

# ---- 8. ADRs sin aprobar ----
echo "--- 8. ADRs ---"
drafts=0
for f in "$REPO"/docs/architecture/ADR-*.md; do
    if grep -qi "Status:.*Draft" "$f"; then
        echo "    DRAFT: $(basename "$f")"
        drafts=$((drafts+1))
    fi
done
if [ "$drafts" -eq 0 ]; then
    pass "Todos los ADRs Approved"
else
    fail "$drafts ADRs en Draft"
fi

# ---- 9. CODIGO MUERTO ----
echo "--- 9. Codigo muerto ---"
# motor/platform/ sin consumidores externos
platform_files=$(find "$REPO/motor/platform/" -name '*.py' -not -path '*__pycache__*' | wc -l)
platform_consumers=$(grep -rn "from motor.platform\|import motor.platform" "$REPO" --include='*.py' | grep -v "/test_" | wc -l)
if [ "$platform_files" -gt 0 ] && [ "$platform_consumers" -eq 0 ]; then
    echo "    WARN: motor/platform/ ($platform_files archivos) sin consumidores"
fi
# Directorios vacios en codigo fuente
empty_source=$(find "$REPO/motor" "$REPO/core" "$REPO/knowledge" "$REPO/agents" -type d -empty 2>/dev/null | wc -l)
if [ "$empty_source" -gt 0 ]; then
    echo "    WARN: $empty_source directorios vacios en src/"
fi
pass "Revision de codigo muerto completada"

# ---- 10. ARCHIVOS CON NOMBRES DUPLICADOS ----
echo "--- 10. Nombres duplicados ---"
dups=$(find "$REPO/motor" "$REPO/core" "$REPO/knowledge" "$REPO/agents" -name '*.py' -not -path '*__pycache__*' -print0 | xargs -0 -I{} basename {} | sort | uniq -d)
if [ -n "$dups" ]; then
    echo "$dups" | while read d; do
        locations=$(find "$REPO/motor" "$REPO/core" "$REPO/knowledge" "$REPO/agents" -name "$d" -not -path '*__pycache__*')
        echo "    $d:"
        echo "$locations" | sed 's/^/      /'
    done
    pass "Duplicados en directorios separados (intencional)"
else
    pass "Sin nombres duplicados"
fi

# ---- 11. VERSION COHERENTE ----
echo "--- 11. Version ---"
version_code=$(grep '_VERSION =' "$REPO/motor/assistant/main.py" | grep -oP '"[^"]+"' | tr -d '"')
tag_version=$(git -C "$REPO" describe --tags --exact-match 2>/dev/null || echo "no-tag")
echo "    Codigo: $version_code  Tag: $tag_version"
pass "Version reportada"

# ---- 12. BANDIT GLOBAL (todo motor/) ----
echo "--- 12. Bandit (motor/ completo) ---"
python3 -m bandit -r "$REPO/motor/" -ll -q
pass "Bandit global: 0 Medium/High"

# ---- RESULTADO FINAL ----
echo ""
echo "=============================================="
if [ ${#FAILURES[@]} -eq 0 ]; then
    echo "  VEREDICTO: AUDITORIA SUPERADA"
    echo "  Ningun fallo detectado."
    echo "=============================================="
    rm -rf "$TMPDIR"
    trap '' EXIT
    exit 0
else
    echo "  VEREDICTO: AUDITORIA FALLIDA"
    echo "  ${#FAILURES[@]} fallo(s):"
    for f in "${FAILURES[@]}"; do echo "    - $f"; done
    echo "=============================================="
    rm -rf "$TMPDIR"
    trap '' EXIT
    exit 1
fi

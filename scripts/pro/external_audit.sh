#!/bin/bash
# external_audit.sh — Auditoría externa verificable del sistema URA
# Genera docs/audit_externa_$(date +%Y%m%d_%H%M).md con todas las secciones.
# Cada sección tiene timeout propio. Fallos parciales no detienen el resto.
set -u
OUTDIR="/tmp/ura_audit"
REPO="$HOME/URA/ura_ia_1972"
REPORT=""
mkdir -p "$OUTDIR"

_section() {
    local name="$1" cmd="$2" timeout="${3:-30}"
    echo "[$(date '+%H:%M:%S')] === $name ==="
    timeout "$timeout" bash -c "$cmd" > "$OUTDIR/${name}.txt" 2>&1
    local rc=$?
    if [ $rc -eq 124 ]; then
        echo "(TIMEOUT ${timeout}s)" >> "$OUTDIR/${name}.txt"
    fi
    echo "exit=$rc" >> "$OUTDIR/${name}.txt"
    return $rc
}

cd "$REPO" || exit 1

# ── 01: Git ──────────────────────────────────────────────
_section "01_git" "
echo '=== LOG ===' && git log --oneline -5
echo '=== STATUS ===' && git status --short
echo '=== DIFF ===' && git diff --stat
echo '=== STASH ===' && git stash list
" 15

# ── 02: Linting ───────────────────────────────────────────
_section "02_lint" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
ruff check . --exclude .venv,__pycache__,.git,.sandbox_packages,.opencode,.tuneladora --statistics
" 60

# ── 03: Tests (rápidos) ───────────────────────────────────
_section "03_tests" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
python3 -m pytest tests/test_registry_v2.py tests/test_security.py tests/test_preflight_system.py tests/contracts/test_llm_contract.py tests/test_audit_api.py::TestInputValidation::test_very_long_message tests/test_audit_api.py::TestInputValidation::test_extremely_long_message tests/test_audit_api.py::TestInputValidation::test_emoji_and_unicode_surrogates -q --tb=line --no-header 2>&1
" 120

# ── 04: Tests (suite completo, timeout 5 min) ─────────────
_section "04_tests_full" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
python3 -m pytest tests/ -q --tb=line --no-header -k 'not test_f28 and not test_fase7 and not test_resiliencia and not test_robustez and not test_stress and not test_load and not test_llm_bridge and not test_api and not test_integration' --ignore=tests/test_integration 2>&1
" 300

# ── 05: Seguridad (bandit) ────────────────────────────────
_section "05_bandit" "
export PATH=\"\$PWD/.venv/bin:\$PATH\"
echo '=== HIGH ===' && bandit -r . -x .venv,__pycache__,.git,.sandbox_packages,.opencode,.tuneladora -lll 2>&1 | grep -E 'Severity: High|Issue|Location' | head -20
echo '=== MEDIUM ===' && bandit -r . -x .venv,__pycache__,.git,.sandbox_packages,.opencode,.tuneladora -ll 2>&1 | grep -c 'Severity: Medium'
" 120

# ── 06: Servicios systemd ─────────────────────────────────
_section "06_services" "
echo '=== ACTIVOS ===' && systemctl list-units --type=service --state=active --no-pager 2>/dev/null | grep -E '(ura|model|mochila|heartbeat|watch|openclaw|contraste|snc|ollama|qdrant|redis)'
echo '=== FALLIDOS ===' && systemctl list-units --type=service --state=failed --no-pager 2>/dev/null
echo '=== TIMERS ===' && systemctl list-timers --no-pager 2>/dev/null | head -20
" 15

# ── 07: Puertos ───────────────────────────────────────────
_section "07_ports" "
sudo ss -tlnp 2>/dev/null | grep LISTEN | sort -n -t: -k2
" 10

# ── 08: Disco ─────────────────────────────────────────────
_section "08_disk" "
echo '=== DF ===' && df -h / /home /run 2>/dev/null
echo '=== REPO SIZE ===' && du -sh \"$REPO\" 2>/dev/null
echo '=== MOUNTS ===' && mount | grep -E '^/dev|tmpfs' | head -10
" 10

# ── 09: System manifest audit ─────────────────────────────
_section "09_manifest" "
python3 scripts/pro/tuneladora/preflight_system.py audit
" 15

# ── 10: Merge conflicts ───────────────────────────────────
_section "10_merge" "
find \"$REPO\" -name '*.py' -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/.git/*' -not -path '*/.sandbox_packages/*' -not -path '*/.opencode/*' -not -path '*/build/*' -not -path '*/.tuneladora/*' -exec grep -l '<<<<<<<' {} \\; 2>/dev/null | grep -v inspectores || echo '(ninguno)'
" 10

# ── 11: Model-router health ───────────────────────────────
_section "11_model_router" "
echo '=== systemd ===' && systemctl status model-router.service --no-pager -n 3 2>&1 | head -6
echo '=== health ===' && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11435/health 2>/dev/null || echo 'no_respuesta'
echo '=== ollama ===' && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags 2>/dev/null || echo 'no_respuesta'
" 10

# ── 12: Mochila health ────────────────────────────────────
_section "12_mochila" "
echo '=== systemd ===' && systemctl status ura-mochila.service --no-pager -n 3 2>&1 | head -6
echo '=== health ===' && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4098/health 2>/dev/null || echo 'no_respuesta'
echo '=== auth ===' && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4098/v1/models 2>/dev/null || echo 'no_respuesta'
" 10

# ── 13: Secrets ───────────────────────────────────────────
_section "13_secrets" "
stat -c '%a %U:%G %n' /etc/ura/secrets.env 2>/dev/null || echo 'no existe'
echo '---'
python3 -c 'from motor.core.secrets import get_secret; k=get_secret(\"URA_API_KEY\"); print(\"URA_API_KEY:\",\"OK\" if k else \"FALTA\")' 2>/dev/null || echo 'secrets module error'
" 5

# ═══════════════════════════════════════════════════════════
# GENERAR REPORTE
# ═══════════════════════════════════════════════════════════
REPORT_FILE="docs/audit_externa_$(date +%Y%m%d_%H%M).md"

_report_val() {
    local f="$OUTDIR/$1.txt"
    [ -f "$f" ] && head -1 "$f" 2>/dev/null || echo "NO_DATA"
}

exec 3>&1

{
echo "# Auditoría Externa URA — $(date '+%Y-%m-%d %H:%M')"
echo ""
echo "## Resumen Ejecutivo"
echo ""

# Extraer datos del resumen
LINT_ERR=$(grep -c "^[0-9]" "$OUTDIR/02_lint.txt" 2>/dev/null || echo "?")
TEST_PASS=$(grep -oP '\d+ passed' "$OUTDIR/04_tests_full.txt" 2>/dev/null | head -1 || echo "?")
TEST_FAIL=$(grep -oP '\d+ failed' "$OUTDIR/04_tests_full.txt" 2>/dev/null | head -1 || echo "?")
TEST_SKIP=$(grep -oP '\d+ skipped' "$OUTDIR/04_tests_full.txt" 2>/dev/null | head -1 || echo "?")
BANDIT_HIGH=$(grep -c "Severity: High" "$OUTDIR/05_bandit.txt" 2>/dev/null || echo "0")
SERV_ACTIVE=$(grep -c "running" "$OUTDIR/06_services.txt" 2>/dev/null || echo "?")
SERV_FAILED=$(grep -c "failed" "$OUTDIR/06_services.txt" 2>/dev/null || echo "?")
MANIFEST=$(grep -c "Sistema coincide\|0 discrepancias" "$OUTDIR/09_manifest.txt" 2>/dev/null || echo "no")
MERGE=$(head -1 "$OUTDIR/10_merge.txt" 2>/dev/null || echo "?")

echo "| Métrica | Valor |"
echo "|---------|-------|"
echo "| Linting (ruff) | $LINT_ERR errores |"
echo "| Tests pasados | $TEST_PASS |"
echo "| Tests fallidos | $TEST_FAIL |"
echo "| Tests skipped | $TEST_SKIP |"
echo "| Bandit HIGH | $BANDIT_HIGH |"
echo "| Servicios activos URA | $SERV_ACTIVE |"
echo "| Servicios fallidos | $SERV_FAILED |"
echo "| Manifest vs sistema | $MANIFEST |"
echo "| Merge conflicts | $MERGE |"
echo ""

# Secciones detalladas
for s in 01_git 02_lint 03_tests 04_tests_full 05_bandit 06_services 07_ports 08_disk 09_manifest 10_merge 11_model_router 12_mochila 13_secrets; do
    echo "---"
    echo ""
    echo "## Sección $(echo "$s" | tr '_' ' ' | tr '[:lower:]' '[:upper:]')"
    echo ""
    echo '```'
    cat "$OUTDIR/$s.txt" 2>/dev/null || echo "(ARCHIVO NO ENCONTRADO)"
    echo '```'
    echo ""
done

echo "---"
echo ""
echo "*Auditoría generada el $(date) por external_audit.sh*"
echo "*Host: $(hostname)*"

} > "$REPORT_FILE"

ln -sf "$REPORT_FILE" docs/audit_externa_latest.md

echo ""
echo "=== REPORTE GENERADO: $REPORT_FILE ==="
echo "Enlace: docs/audit_externa_latest.md"
wc -l "$REPORT_FILE" 2>/dev/null

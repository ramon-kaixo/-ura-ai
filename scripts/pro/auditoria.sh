#!/bin/bash
# ============================================================
# 🛡️ ENGINE DE AUDITORÍA AUTOMÁTICA — URA PROJECT v2.6
# ============================================================
set -uo pipefail

PROFUNDIDAD="profundo"
while [[ $# -gt 0 ]]; do
    case $1 in
        --profundidad) PROFUNDIDAD="$2"; shift; shift ;;
        *) shift ;;
    esac
done

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="./audit_reports/${TIMESTAMP}"
mkdir -p "$REPORT_DIR"

REQ_FILE="./requirements.txt"
[ ! -f "$REQ_FILE" ] && touch "$REQ_FILE"
PIP_CMD=$(command -v pip3 || command -v pip)

# --- DETECCIÓN MULTILENGUAJE ---
JS_EXISTS="false"
if find . \( -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" \) \
    -not -path "./node_modules/*" \
    -not -path "./.venv/*" \
    -not -path "./.sandbox_packages/*" \
    -not -path "./audit_reports/*" 2>/dev/null | head -1 | grep -q .; then
    JS_EXISTS="true"
fi

ESLINT_AVAILABLE="false"
if command -v eslint &>/dev/null; then
    ESLINT_AVAILABLE="true"
fi

# --- EJECUCIÓN CONDICIONAL SEGÚN PROFUNDIDAD ---

# Capa 1: Ruff (Siempre corre)
$PIP_CMD show ruff &>/dev/null || $PIP_CMD install -q ruff
ruff check . --select=E,F,W,B,ASYNC --output-format json --exclude ".venv,venv,audit_reports,.sandbox_packages,tests,app,agents" > "${REPORT_DIR}/ruff_before.json" 2>/dev/null || true
ruff check . --select=E,F,W,B,ASYNC --fix --exclude ".venv,venv,audit_reports,.sandbox_packages,tests,app,agents" > /dev/null 2>&1 || true

# Capa 2: Bandit (Media y Profunda)
if [ "$PROFUNDIDAD" == "medio" ] || [ "$PROFUNDIDAD" == "profundo" ]; then
    $PIP_CMD show bandit &>/dev/null || $PIP_CMD install -q bandit
    bandit -r . -f json -o "${REPORT_DIR}/bandit_report.json" \
        --exclude "./.venv,./venv,./audit_reports,./.sandbox_packages,./tests,./app,./agents" \
        --skip B324,B307 \
        -ll > /dev/null 2>&1 || true
fi

# Capa 3: Semgrep y Pip-Audit (Solo Profunda)
if [ "$PROFUNDIDAD" == "profundo" ]; then
    $PIP_CMD show semgrep &>/dev/null || $PIP_CMD install -q semgrep
    semgrep scan --config=p/python --config=p/owasp-top-10 --json --output "${REPORT_DIR}/semgrep_report.json" . > /dev/null 2>&1 || true

    $PIP_CMD show pip-audit &>/dev/null || $PIP_CMD install -q pip-audit
    pip-audit -r "$REQ_FILE" --format json --output "${REPORT_DIR}/pip_audit_report.json" > /dev/null 2>&1 || true

    # ESLint: solo si hay JS/TS y está instalado
    if [ "$JS_EXISTS" == "true" ] && [ "$ESLINT_AVAILABLE" == "true" ]; then
        eslint . --format json --output-file "${REPORT_DIR}/eslint_report.json" > /dev/null 2>&1 || true
    fi
fi

# --- GENERACIÓN EXCLUSIVA DE JSON EN STDOUT ---
python3 - "$PROFUNDIDAD" "$REPORT_DIR" "$TIMESTAMP" "$JS_EXISTS" "$ESLINT_AVAILABLE" <<PYEOF
import json, os, sys

profundidad = sys.argv[1]
report_dir = sys.argv[2]
timestamp = sys.argv[3]
js_exists = sys.argv[4] == "true"
eslint_available = sys.argv[5] == "true"

def parse_json(path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            with open(path, 'r') as f: return json.load(f)
        except: return None
    return None

bandit_data = parse_json(f"{report_dir}/bandit_report.json")
semgrep_data = parse_json(f"{report_dir}/semgrep_report.json")
ruff_data = parse_json(f"{report_dir}/ruff_before.json")
pip_data = parse_json(f"{report_dir}/pip_audit_report.json")

hi = bandit_data.get('metrics', {}).get('_totals', {}).get('SEVERITY.HIGH', 0) if bandit_data else 0
med = bandit_data.get('metrics', {}).get('_totals', {}).get('SEVERITY.MEDIUM', 0) if bandit_data else 0
semgrep_hits = len(semgrep_data.get('results', [])) if semgrep_data else 0
ruff_hits = len(ruff_data) if ruff_data else 0

vulns = 0
if pip_data:
    if isinstance(pip_data, dict): vulns = len([p for p in pip_data.get('dependencies', []) if p.get('vulns')])
    elif isinstance(pip_data, list): vulns = len([p for p in pip_data if p.get('vulns')])

# Penalización con techo por categoría para evitar colapso por falsos positivos
penalty = min(hi * 25, 40) + min(med * 5, 30) + min(semgrep_hits * 5, 15) + (15 if ruff_hits > 100 else 0)
score = max(10, min(100, 100 - penalty))

hallazgos_lista = []
criticos_reales = 0
if bandit_data:
    for r in bandit_data.get("results", []):
        if r.get("issue_severity") == "HIGH":
            fn = r.get("filename", "")
            # Solo contar críticos en core/ y motor/ como bloqueantes
            if fn.startswith("./core/") or fn.startswith("./motor/"):
                criticos_reales += 1
            hallazgos_lista.append({"archivo": fn, "linea": r.get("line_number", 0), "tipo": f"Bandit {r.get('test_id','')}", "fix": r.get("issue_text","")[:80]})

output = {
    "version": "2.6",
    "timestamp": timestamp,
    "profundidad_ejecutada": profundidad,
    "score": score,
    "bloqueante": criticos_reales > 0,
    "metricas": {"criticos": hi, "criticos_reales": criticos_reales, "altos": med, "medios": semgrep_hits, "informacion": ruff_hits, "cves": vulns},
    "multilenguaje": {
        "javascript_detectado": js_exists,
        "eslint_disponible": eslint_available,
        "recomendacion": "npm install -g eslint" if js_exists and not eslint_available else ""
    },
    "hallazgos": hallazgos_lista,
    "report_dir": report_dir
}

with open("./audit_reports/registro_penalizaciones.txt", "a") as hf:
    hf.write(f"{timestamp}|{profundidad}|{score}|C:{hi}|M:{med}|R:{ruff_hits}\n")

print(json.dumps(output))
PYEOF

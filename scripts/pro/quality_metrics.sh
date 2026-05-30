#!/bin/bash
# Quality Metrics — Mide la salud del código tras cada Tuneladora
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
METRICS_DIR="${REPO}/docs/metrics"
mkdir -p "$METRICS_DIR"

{
echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
echo " \"lineas\": $(find "$REPO" -name '*.py' -not -path '*/.venv/*' -not -path '*/quarantine/*' -not -path '*/legacy/*' | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}'),"
echo " \"tests_pasados\": $(python3 -m pytest tests/test_core_basics.py tests/test_consensus_system.py -q 2>/dev/null | grep -c 'passed' || echo 0),"
echo " \"complejidad_media\": \"$(radon cc "$REPO" -a -s 2>/dev/null | grep 'Average' | awk '{print $3}' || echo '?')\","
echo " \"archivos_grandes\": $(find "$REPO" -name '*.py' -not -path '*/.venv/*' -exec wc -l {} + 2>/dev/null | awk '$1>200' | wc -l),"
echo " \"agentes_registrados\": $(curl -s http://127.0.0.1:5100/agents 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)"
echo "}"
} > "${METRICS_DIR}/quality_$(date +%Y%m%d).json"

echo "✅ Métrica: $(cat "${METRICS_DIR}/quality_$(date +%Y%m%d).json")"

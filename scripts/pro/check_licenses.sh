#!/bin/bash
# check_licenses.sh – Audita licencias de todas las dependencias Python
# Muestra resumen de licencias y alerta si alguna no es compatible
# Dependencia: pip-licenses (pip install pip-licenses)
set -e

cd /opt/ura

if ! command -v pip-licenses &>/dev/null; then
    echo "pip-licenses no instalado. Ejecuta: pip install pip-licenses"
    exit 1
fi

LOG="/var/log/ura_licencias.log"
DENIED={"AGPL-1.0","AGPL-3.0","SSPL-1.0","BUSL-1.1"}
RESTRICTED={"GPL-2.0","GPL-3.0","LGPL-3.0","MPL-2.0"}

echo "Auditando licencias de dependencias..." | tee -a "$LOG"
echo "" | tee -a "$LOG"

pip-licenses --format=columns --with-license-file --no-license-path 2>/dev/null | tee -a "$LOG"

echo "" | tee -a "$LOG"

DENIED_FOUND=$(pip-licenses --format=json 2>/dev/null | python3 -c "
import json, sys
deps = json.load(sys.stdin)
denied = {'AGPL-1.0', 'AGPL-3.0', 'SSPL-1.0', 'BUSL-1.1'}
for d in deps:
    lic = d.get('License', 'UNKNOWN')
    if lic in denied:
        print(f\"{d['Name']} ({lic})\")
" 2>/dev/null || true)

if [ -n "$DENIED_FOUND" ]; then
    echo "LICENCIAS PROHIBIDAS:" | tee -a "$LOG"
    echo "$DENIED_FOUND" | tee -a "$LOG"
    /opt/ura/scripts/notificar.sh "Licencias prohibidas detectadas: $DENIED_FOUND" 2>/dev/null || true
    exit 1
fi

RESTRICTED_FOUND=$(pip-licenses --format=json 2>/dev/null | python3 -c "
import json, sys
deps = json.load(sys.stdin)
restricted = {'GPL-2.0', 'GPL-3.0', 'LGPL-3.0', 'MPL-2.0'}
for d in deps:
    lic = d.get('License', 'UNKNOWN')
    if lic in restricted:
        print(f\"{d['Name']} ({lic})\")
" 2>/dev/null || true)

if [ -n "$RESTRICTED_FOUND" ]; then
    echo "LICENCIAS RESTRICTIVAS (revisar compatibilidad):" | tee -a "$LOG"
    echo "$RESTRICTED_FOUND" | tee -a "$LOG"
fi

echo "" | tee -a "$LOG"
echo "Auditoria de licencias completada." | tee -a "$LOG"

#!/bin/bash
set -euo pipefail
# orquestador/orquestar.sh — Orquestador del dominio de Orquestacion (reflexion)
MALETA="$1"; INFORMES="$2"; TS="$3"
# Este dominio ejecuta scripts de la propia carpeta orquestador/
REPO="${HOME}/URA/ura_ia_1972"
bash "${REPO}/sistema/gobernanza_datos.sh" 2>/dev/null &
bash "${REPO}/orquestador/auto_update.sh" 2>/dev/null || true
wait 2>/dev/null || true

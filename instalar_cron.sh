#!/usr/bin/env bash
set -euo pipefail
RAIZ="${1:-$(pwd)}"; PY="$(command -v python3)"; LOG="/var/log/ura_tuneladora.log"
if [[ ! -f "$RAIZ/run_tuneladora.py" ]]; then echo "Falta run_tuneladora.py en $RAIZ"; exit 1; fi
( crontab -l 2>/dev/null | grep -v "run_tuneladora.py" ; echo "0 3 * * * cd $RAIZ && $PY run_tuneladora.py >> $LOG 2>&1" ) | crontab -
echo "Cron: 0 3 * * * cd $RAIZ && $PY run_tuneladora.py >> $LOG 2>&1"

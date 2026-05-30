#!/bin/bash
set -euo pipefail
# serve_bootstrap.sh - Sirve el script bootstrap para que el GX10 lo descargue
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8080}"

echo "Sirviendo bootstrap en http://0.0.0.0:${PORT}/bootstrap_gx10.sh"
cd "$REPO/scripts"
python3 -m http.server "$PORT"

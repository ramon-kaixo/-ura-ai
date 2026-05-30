#!/bin/bash
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/usuario/ura.git}"
INSTALL_DIR="${HOME}/URA/ura_ia_1972"

echo "🚀 Instalador URA — $(date)"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if [[ ! "$PYTHON_VERSION" =~ ^3\.1[2-9] ]]; then
    echo "🔴 Se requiere Python 3.12+. Versión: $PYTHON_VERSION"
    exit 1
fi
echo "✅ Python $PYTHON_VERSION"

if [ ! -d "$INSTALL_DIR" ]; then
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    cd "$INSTALL_DIR" && git pull origin main
fi
cd "$INSTALL_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
[ -f requirements.txt ] && pip install -r requirements.txt -q
mkdir -p quarantine inbox logs docs/decisiones docs/sellos
for plist in ~/Library/LaunchAgents/com.coderefine.*.plist; do
    [ -f "$plist" ] && launchctl load "$plist" 2>/dev/null || true
done
echo "✅ URA instalada — Dashboard: http://127.0.0.1:5101"

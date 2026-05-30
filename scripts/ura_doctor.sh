#!/bin/bash
# ura_doctor.sh - Diagnostico previo al arranque de URA
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${REPO}/.venv/bin/python"

echo "🩺 URA Doctor — $(date)"
echo "=============================================="

# 1. Dependencias del TPV
echo ""
echo "📦 Verificando TPV..."
command -v mdb-export >/dev/null 2>&1 && echo "   ✅ mdbtools instalado" || echo "   🔴 mdbtools NO instalado. Ejecute: brew install mdbtools"
ACCESS_PATH="${TPV_ACCESS_PATH:-/Volumes/Compartida/R4/data/R4.accdb}"
[ -f "$ACCESS_PATH" ] && echo "   ✅ Archivo .accdb accesible ($ACCESS_PATH)" || echo "   🔴 Archivo .accdb no encontrado en $ACCESS_PATH"

# 2. Dependencias del sistema
echo ""
echo "🧠 Verificando sistema..."
command -v python3 >/dev/null 2>&1 && echo "   ✅ Python 3" || echo "   🔴 Python 3 no encontrado"
python3 -c "import sqlite3" 2>/dev/null && echo "   ✅ SQLite" || echo "   🔴 SQLite no disponible"
[ -x "$PYTHON" ] && $PYTHON -c "import pandas" 2>/dev/null && echo "   ✅ Pandas (venv)" || echo "   🔴 Pandas no disponible"
[ -x "$PYTHON" ] && $PYTHON -c "import chromadb" 2>/dev/null && echo "   ✅ ChromaDB (venv)" || echo "   🔴 ChromaDB no disponible"

# 3. Conexiones
echo ""
echo "🌐 Verificando conectividad..."
ping -c 1 -W 2 10.164.1.99 >/dev/null 2>&1 && echo "   ✅ GX10 alcanzable" || echo "   🔴 GX10 NO responde al ping"
curl -s --max-time 3 http://10.164.1.99:11434/api/tags >/dev/null 2>&1 && echo "   ✅ Ollama GX10" || echo "   🔴 Ollama GX10 no responde"
curl -s --max-time 3 http://localhost:5105/health >/dev/null 2>&1 && echo "   ✅ Autonomia API (5105)" || echo "   🔴 Autonomia API no responde"

# 4. Directorios
echo ""
echo "📁 Verificando estructura..."
REPO="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$REPO" ] && echo "   ✅ $REPO" || echo "   🔴 Directorio repo no existe"
[ -d "$REPO/data" ] || mkdir -p "$REPO/data" && echo "   ✅ $REPO/data"
[ -d "$REPO/data/chroma_db" ] || mkdir -p "$REPO/data/chroma_db" && echo "   ✅ $REPO/data/chroma_db"
[ -w /tmp ] && echo "   ✅ /tmp escribible" || echo "   🔴 /tmp no accesible"

# 5. Procesos activos
echo ""
echo "⚙️ Procesos URA activos..."
pgrep -f autonomia_avanzada >/dev/null 2>&1 && echo "   ✅ Autonomia corriendo" || echo "   ⏭️ Autonomia no activa"
pgrep -f bibliotecario >/dev/null 2>&1 && echo "   ✅ Orquestador corriendo" || echo "   ⏭️ Orquestador no activo"
pgrep -f agente_voz >/dev/null 2>&1 && echo "   ✅ AgenteVoz corriendo" || echo "   ⏭️ AgenteVoz no activo"
pgrep -f tpv_spy >/dev/null 2>&1 && echo "   ✅ TPV Spy corriendo" || echo "   ⏭️ TPV Spy no activo"

# 6. Timers launchd
echo ""
echo "⏰ Timers launchd..."
launchctl list 2>/dev/null | grep com.ura >/dev/null 2>&1 && echo "   ✅ Timers URA activos" || echo "   ⏭️ No hay timers URA cargados"

echo ""
echo "=============================================="
echo "Diagnostico completado"

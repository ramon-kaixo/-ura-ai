#!/bin/bash
# URA Launcher — arranca todo lo necesario
# Uso: bash start_ura.sh

cd "$(dirname "$0")"

echo "🚀 Iniciando URA..."

# Activar entorno virtual
source .venv/bin/activate

# 1. Dashboard web
echo "  📊 Dashboard en :5051..."
nohup python dashboard/ura_web.py > logs/ura_web.log 2>&1 &
DASH_PID=$!

# 2. Max Research
echo "  🧠 Max Research..."
nohup python dashboard/max_research.py > logs/max_research.log 2>&1 &
RESEARCH_PID=$!

sleep 3

# Verificar
if curl -s http://localhost:5051/ > /dev/null 2>&1; then
    echo "  ✅ Dashboard OK — http://localhost:5051"
else
    echo "  ⚠️  Dashboard no responde"
fi

echo ""
echo "PIDs: Dashboard=$DASH_PID Research=$RESEARCH_PID"
echo "Logs: logs/ura_web.log logs/max_research.log"
echo "Métricas: http://localhost:5051/metrics"
echo ""

# Guardar PIDs para stop_ura.sh
echo "$DASH_PID" > /tmp/ura_dashboard.pid
echo "$RESEARCH_PID" > /tmp/ura_research.pid

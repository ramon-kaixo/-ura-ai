#!/bin/bash
# final_install.sh - Instalacion final de dependencias y configuracion
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================="
echo "  URA - Instalacion Final"
echo "  $(date)"
echo "========================================="

# 1. Instalar dependencias Python
echo ""
echo "[1/4] Instalando dependencias Python..."
pip install -r "$REPO/requirements.txt" 2>/dev/null || pip3 install -r "$REPO/requirements.txt"
echo "   ✅ Dependencias instaladas"

# 2. Permisos de scripts
echo ""
echo "[2/4] Configurando permisos..."
find "$REPO/scripts" -name "*.sh" -exec chmod +x {} \;
find "$REPO/scripts" -name "*.py" -exec chmod +x {} \;
echo "   ✅ Permisos configurados"

# 3. Verificar Redis
echo ""
echo "[3/4] Verificando Redis..."
if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "   ✅ Redis activo"
    else
        echo "   ⚠️ Redis instalado pero no activo. Ejecuta: brew services start redis"
    fi
else
    echo "   ⚠️ Redis no instalado. Ejecuta: brew install redis && brew services start redis"
fi

# 4. Verificar Mosquitto
echo ""
echo "[4/4] Verificando Mosquitto..."
if command -v mosquitto >/dev/null 2>&1; then
    if brew services list 2>/dev/null | grep -q mosquitto; then
        echo "   ✅ Mosquitto activo"
    else
        echo "   ⚠️ Mosquitto instalado pero no activo. Ejecuta: brew services start mosquitto"
    fi
else
    echo "   ⚠️ Mosquitto no instalado. Ejecuta: brew install mosquitto && brew services start mosquitto"
fi

echo ""
echo "========================================="
echo "  Instalacion completada"
echo "========================================="
echo ""
echo "Siguiente paso: sudo bash $REPO/scripts/instalar_autonomia.sh"

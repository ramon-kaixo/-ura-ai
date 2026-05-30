#!/bin/bash
###############################################################################
# URA_STATUS.SH - Dashboard de Estado de URA
# Muestra todo el estado en una sola pantalla
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URA_DIR="$SCRIPT_DIR"
cd "$URA_DIR" || exit 1

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

check_service() {
    local nombre=$1
    local comando=$2
    if eval "$comando" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC} $nombre"
    else
        echo -e "  ${RED}❌${NC} $nombre"
    fi
}

clear
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║          URA - DASHBOARD DE ESTADO                       ║${NC}"
echo -e "${BOLD}${CYAN}║          $(date '+%Y-%m-%d %H:%M:%S')                                 ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# === SERVICIOS ===
echo -e "${BOLD}🔧 SERVICIOS:${NC}"
check_service "Ollama       (localhost:11434)" "curl -s http://localhost:11434/api/tags"
check_service "Redis        (redis-cli PING)"   "redis-cli ping | grep -q PONG"
check_service "PM2 daemon"                       "pm2 ping"
echo ""

# === PM2 PROCESOS ===
echo -e "${BOLD}📦 PM2 PROCESOS:${NC}"
pm2 jlist 2>/dev/null | python3 -c "
import json, sys
try:
    procesos = json.load(sys.stdin)
    if not procesos:
        print('  (ninguno)')
    for p in procesos:
        nombre = p.get('name', '?')
        estado = p.get('pm2_env', {}).get('status', '?')
        restarts = p.get('pm2_env', {}).get('restart_time', 0)
        mem = p.get('monit', {}).get('memory', 0) / (1024*1024)
        icon = '✅' if estado == 'online' else ('⏸️ ' if estado == 'stopped' else '❌')
        print(f'  {icon} {nombre:<30} {estado:<10} {mem:.1f}MB  restarts:{restarts}')
except Exception as e:
    print(f'  Error: {e}')
"
echo ""

# === MODELOS OLLAMA ===
echo -e "${BOLD}🤖 MODELOS OLLAMA:${NC}"
curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    modelos = data.get('models', [])
    if not modelos:
        print('  (ninguno instalado)')
    for m in modelos[:5]:
        nombre = m.get('name', '?')
        size = m.get('size', 0) / (1024**3)
        print(f'  • {nombre:<30} {size:.2f} GB')
    if len(modelos) > 5:
        print(f'  ... y {len(modelos)-5} más')
except Exception:
    print('  ❌ No se pudieron listar modelos')
"
echo ""

# === ARCHIVOS DE SALIDA ===
echo -e "${BOLD}📄 ARCHIVOS DE SALIDA:${NC}"
for archivo in core/data/output/recetas_sugeridas.json core/data/output/marketing_letreros.json; do
    if [ -f "$archivo" ]; then
        tam=$(ls -lh "$archivo" | awk '{print $5}')
        fecha=$(stat -f "%Sm" -t "%H:%M" "$archivo")
        echo -e "  ${GREEN}✅${NC} $(basename $archivo)  ${YELLOW}$tam${NC}  (actualizado $fecha)"
    else
        echo -e "  ${RED}❌${NC} $(basename $archivo)  (no existe)"
    fi
done
echo ""

# === DATOS SINTÉTICOS ===
echo -e "${BOLD}🧪 DATOS SINTÉTICOS:${NC}"
for archivo in core/data/synthetic/SYN_*.json; do
    if [ -f "$archivo" ]; then
        tam=$(ls -lh "$archivo" | awk '{print $5}')
        echo -e "  ${GREEN}✅${NC} $(basename $archivo)  ${YELLOW}$tam${NC}"
    fi
done
echo ""

# === BITÁCORA (últimas 5 líneas) ===
echo -e "${BOLD}📜 BITÁCORA (últimas 5 acciones):${NC}"
if [ -f "core/LOG_ACTIVIDAD_URA.md" ]; then
    grep -E "^[0-9]{2}:[0-9]{2} -" core/LOG_ACTIVIDAD_URA.md | tail -5 | sed 's/^/  /'
else
    echo "  (sin bitácora)"
fi
echo ""

# === BACKUPS ===
echo -e "${BOLD}💾 BACKUPS:${NC}"
if [ -d "core/data/backups" ]; then
    num=$(ls -1 core/data/backups/ 2>/dev/null | wc -l | tr -d ' ')
    ultimo=$(ls -1t core/data/backups/ 2>/dev/null | head -1)
    echo -e "  Total: ${YELLOW}$num${NC} backups  |  Último: ${CYAN}${ultimo:-ninguno}${NC}"
else
    echo "  (sin backups aún)"
fi
echo ""

# === TELEGRAM ===
echo -e "${BOLD}📱 TELEGRAM:${NC}"
if [ -f "telegram_config.json" ]; then
    python3 -c "
import json
with open('telegram_config.json') as f:
    cfg = json.load(f)
enabled = cfg.get('enabled', False)
users = cfg.get('authorized_user_ids', [])
token_ok = not cfg.get('api_key', '').startswith('TU_')
print(f'  Habilitado: {\"✅\" if enabled else \"❌\"}  |  Token: {\"✅\" if token_ok else \"❌\"}  |  Usuarios: {len(users)}')
"
fi
echo ""

echo -e "${BOLD}${CYAN}────────────────────────────────────────────────────${NC}"
echo -e "${BOLD}Comandos útiles:${NC}"
echo "  pm2 logs              → Ver logs en vivo"
echo "  pm2 monit             → Monitor interactivo"
echo "  htop                  → Monitor del sistema"
echo "  ./ura_status.sh       → Este dashboard"
echo "  python3 core/healthcheck.py  → Chequeo completo"
echo ""

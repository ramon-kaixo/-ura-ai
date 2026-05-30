#!/bin/bash
###############################################################################
# Script de verificación de conectividad Mac M4 ↔ ASUS GX10
# Verifica conexión Tailscale y respuesta de Ollama en el ASUS
###############################################################################

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuración — acepta IP como argumento $1 o variable de entorno ASUS_TAILSCALE_IP
ASUS_TAILSCALE_IP="${1:-${ASUS_TAILSCALE_IP:-}}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  VERIFICACIÓN DE CONECTIVIDAD MAC M4 ↔ ASUS GX10${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ -z "$ASUS_TAILSCALE_IP" ]; then
    echo -e "${RED}ERROR: La variable ASUS_TAILSCALE_IP no está configurada${NC}"
    echo -e "${YELLOW}Uso: export ASUS_TAILSCALE_IP=100.x.x.x${NC}"
    echo -e "${YELLOW}O pasa la IP como argumento: ./check_asus_connectivity.sh 100.x.x.x${NC}"
    exit 1
fi

# 1. Verificar ping a IP Tailscale
echo -e "${CYAN}[1/4] Verificando ping a IP Tailscale del ASUS...${NC}"
if ping -c 3 -W 2 "$ASUS_TAILSCALE_IP" > /dev/null 2>&1; then
    LATENCY=$(ping -c 3 "$ASUS_TAILSCALE_IP" | tail -1 | awk '{print $4}' | cut -d '/' -f 2)
    echo -e "  ${GREEN}✅${NC} Ping exitoso a ${ASUS_TAILSCALE_IP} (latencia: ${LATENCY}ms)"
else
    echo -e "  ${RED}❌${NC} No se puede hacer ping a ${ASUS_TAILSCALE_IP}"
    echo -e "  ${YELLOW}Verifica que:${NC}"
    echo -e "    - Tailscale está corriendo en ambas máquinas"
    echo -e "    - Ambas máquinas están en la misma red Tailscale"
    echo -e "    - El firewall no está bloqueando el tráfico"
    exit 1
fi
echo ""

# 2. Verificar que el puerto 11434 esté abierto
echo -e "${CYAN}[2/4] Verificando puerto ${OLLAMA_PORT} en ASUS...${NC}"
if nc -z -w 3 "$ASUS_TAILSCALE_IP" "$OLLAMA_PORT" 2>/dev/null; then
    echo -e "  ${GREEN}✅${NC} Puerto ${OLLAMA_PORT} está abierto en ${ASUS_TAILSCALE_IP}"
else
    echo -e "  ${RED}❌${NC} Puerto ${OLLAMA_PORT} no está accesible en ${ASUS_TAILSCALE_IP}"
    echo -e "  ${YELLOW}Verifica que:${NC}"
    echo -e "    - Ollama está corriendo en el ASUS"
    echo -e "    - Ollama está escuchando en 0.0.0.0:${OLLAMA_PORT}"
    echo -e "    - El firewall del ASUS permite conexiones entrantes"
    exit 1
fi
echo ""

# 3. Verificar que Ollama responde a /api/tags y listar modelos
echo -e "${CYAN}[3/4] Verificando API de Ollama (/api/tags)...${NC}"
OLLAMA_URL="http://${ASUS_TAILSCALE_IP}:${OLLAMA_PORT}/api/tags"
TAGS_RESPONSE=$(curl -s --max-time 5 "$OLLAMA_URL" 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$TAGS_RESPONSE" ]; then
    MODELO_COUNT=$(echo "$TAGS_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('models',[])))" 2>/dev/null || echo "?")
    MODELO_NOMBRES=$(echo "$TAGS_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); [print('    -',m['name']) for m in d.get('models',[])]" 2>/dev/null)
    echo -e "  ${GREEN}✅${NC} Ollama API responde — modelos disponibles: ${MODELO_COUNT}"
    if [ -n "$MODELO_NOMBRES" ]; then
        echo -e "$MODELO_NOMBRES"
    fi
else
    echo -e "  ${RED}❌${NC} Ollama API no responde en http://${ASUS_TAILSCALE_IP}:${OLLAMA_PORT}"
    echo -e "  ${YELLOW}Verifica que:${NC}"
    echo -e "    - Ollama está corriendo en el ASUS: OLLAMA_HOST=0.0.0.0 ollama serve"
    echo -e "    - El firewall del ASUS permite conexiones entrantes en el puerto ${OLLAMA_PORT}"
    exit 1
fi
echo ""

# 4. Medir latencia de generación (no falla si el modelo no está cargado)
echo -e "${CYAN}[4/4] Midiendo latencia de generación...${NC}"
TEST_MODEL="${TEST_MODEL:-llama3.2:3b}"
set +e
START_TIME=$(date +%s%N)
GEN_RESULT=$(curl -s --max-time 30 "http://${ASUS_TAILSCALE_IP}:${OLLAMA_PORT}/api/generate" \
  -d "{\"model\":\"${TEST_MODEL}\",\"prompt\":\"Hi\",\"stream\":false}" 2>/dev/null)
CURL_EXIT=$?
END_TIME=$(date +%s%N)
set -e
LATENCY_MS=$(( (END_TIME - START_TIME) / 1000000 ))

if [ $CURL_EXIT -eq 0 ] && [ -n "$GEN_RESULT" ]; then
    if [ $LATENCY_MS -lt 5000 ]; then
        echo -e "  ${GREEN}✅${NC} Excelente — ${LATENCY_MS}ms (10GbE funcionando)"
    elif [ $LATENCY_MS -lt 15000 ]; then
        echo -e "  ${GREEN}✅${NC} Bueno — ${LATENCY_MS}ms"
    elif [ $LATENCY_MS -lt 30000 ]; then
        echo -e "  ${YELLOW}⚠️${NC}  Lento — ${LATENCY_MS}ms (verifica Cat 8 o Tailscale routing)"
    else
        echo -e "  ${RED}❌${NC}  Muy lento o timeout — ${LATENCY_MS}ms"
    fi
else
    echo -e "  ${YELLOW}⚠️${NC}  Test de generación omitido (modelo '${TEST_MODEL}' no disponible o timeout)"
    echo -e "     Para testar: TEST_MODEL=deepseek-r1:70b $0 ${ASUS_TAILSCALE_IP}"
fi
echo ""

# Resumen
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  RESUMEN${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "  IP Tailscale ASUS: ${ASUS_TAILSCALE_IP}"
echo -e "  Puerto Ollama:     ${OLLAMA_PORT}"
echo -e "  Estado:            ${GREEN}CONECTADO${NC}"
echo ""
echo -e "${CYAN}Para activar Ollama remoto en URA:${NC}"
echo -e "  ${YELLOW}# Opción A — variable de entorno (temporal):${NC}"
echo -e "  export OLLAMA_HOST=${ASUS_TAILSCALE_IP}:${OLLAMA_PORT}"
echo ""
echo -e "  ${YELLOW}# Opción B — config/settings.json (permanente):${NC}"
echo -e "  editar \"ollama\" en settings.json:"
echo -e "    \"use_remote\": true,"
echo -e "    \"remote_host\": \"${ASUS_TAILSCALE_IP}\","
echo -e "    \"remote_port\": ${OLLAMA_PORT}"
echo ""
echo -e "${CYAN}Notas ASUS GX10 Blackwell:${NC}"
echo -e "  - Asegúrate de que Ollama escucha en 0.0.0.0, no solo 127.0.0.1"
echo -e "  - En el ASUS: OLLAMA_HOST=0.0.0.0 ollama serve"
echo -e "  - Modelos grandes (70B): pueden tardar 1-3s la primera inferencia"
echo ""

#!/bin/bash
# setup_orchestrator_mode.sh — Configura OpenCode como orquestador en las 3 máquinas
# Ejecutar en cualquier máquina (GX10 o Mac)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Configurando modo orquestador para las 3 máquinas...${NC}"

NODE=$(hostname -s)
echo -e "${YELLOW}Nodo actual: $NODE${NC}"

GX10_IP="100.72.103.12"
MAC_IP="100.123.81.101"
SSH_USER_GX10="ramon"
SSH_USER_MAC="ramonesnaola"

SCRIPT_PATH="URA/ura_ia_1972/scripts/pro/configure_single_node.sh"

case "$NODE" in
    gx10*|asus*)
        echo -e "${GREEN}Configurando GX10 (local)...${NC}"
        bash "$HOME/$SCRIPT_PATH" "gx10" "http://localhost:4097"
        
        echo -e "${GREEN}Configurando Mac vía SSH...${NC}"
        ssh "${SSH_USER_MAC}@${MAC_IP}" "cd ~/URA/ura_ia_1972 && bash scripts/pro/configure_single_node.sh mac http://100.72.103.12:4097"
        ;;
    ramon@*|*mini*|*mac*)
        echo -e "${GREEN}Configurando Mac (local)...${NC}"
        bash "$HOME/$SCRIPT_PATH" "mac" "http://100.72.103.12:4097"
        
        echo -e "${GREEN}Configurando GX10 vía SSH...${NC}"
        ssh "${SSH_USER_GX10}@${GX10_IP}" "cd ~/URA/ura_ia_1972 && bash scripts/pro/configure_single_node.sh gx10 http://localhost:4097"
        ;;
    *)
        echo -e "${RED}Nodo desconocido: $NODE${NC}"
        echo "Intentando detectar por IP..."
        
        # Detectar por IP de red
        LOCAL_IP=$(ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
        
        if echo "$LOCAL_IP" | grep -q "100.72"; then
            echo -e "${GREEN}Detectado como GX10 por IP${NC}"
            bash "$HOME/$SCRIPT_PATH" "gx10" "http://localhost:4097"
            ssh "${SSH_USER_MAC}@${MAC_IP}" "cd ~/URA/ura_ia_1972 && bash scripts/pro/configure_single_node.sh mac http://100.72.103.12:4097" || true
        elif echo "$LOCAL_IP" | grep -q "100.123"; then
            echo -e "${GREEN}Detectado como Mac por IP${NC}"
            bash "$HOME/$SCRIPT_PATH" "mac" "http://100.72.103.12:4097"
            ssh "${SSH_USER_GX10}@${GX10_IP}" "cd ~/URA/ura_ia_1972 && bash scripts/pro/configure_single_node.sh gx10 http://localhost:4097" || true
        else
            echo -e "${RED}No se pudo detectar el nodo. IP local: $LOCAL_IP${NC}"
            exit 1
        fi
        ;;
esac

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Configuración completada en las 3 máquinas${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo -e "  Para usar el orquestador:"
echo -e "  1. Reinicia OpenCode en cada máquina"
echo -e "  2. Selecciona el agente: /agent orchestrator"
echo -e "  3. Escribe tu petición — se creará como tarea"
echo ""
echo -e "  Para volver al modo normal:"
echo -e "  /agent general"
echo ""

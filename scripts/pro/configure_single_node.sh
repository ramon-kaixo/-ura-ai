#!/bin/bash
# configure_single_node.sh — Configura OpenCode como orquestador en un nodo
# Uso: configure_single_node.sh <node_name> <orchestrator_url>

set -e

NODE_NAME="${1:-}"
ORCHESTRATOR_URL="${2:-}"

if [ -z "$NODE_NAME" ] || [ -z "$ORCHESTRATOR_URL" ]; then
    echo "Uso: $0 <node_name> <orchestrator_url>"
    echo "  node_name: gx10 | mac"
    echo "  orchestrator_url: http://localhost:4097 | http://100.72.103.12:4097"
    exit 1
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Configurando nodo: $NODE_NAME${NC}"
echo -e "${YELLOW}Orquestador: $ORCHESTRATOR_URL${NC}"

if [ "$NODE_NAME" = "mac" ]; then
    OPENCODE_CONFIG="$HOME/Library/Application Support/opencode/opencode.json"
else
    OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"
fi

AGENTS_DIR="$HOME/URA/ura_ia_1972/.opencode/agents"
REPO_DIR="$HOME/URA/ura_ia_1972"

echo -e "${YELLOW}Config: $OPENCODE_CONFIG${NC}"
echo -e "${YELLOW}Agents dir: $AGENTS_DIR${NC}"

mkdir -p "$AGENTS_DIR"

AGENT_FILE="$AGENTS_DIR/orchestrator.md"
cat > "$AGENT_FILE" << 'AGENT_EOF'
---
description: "Orquestador URA — envía tareas al Task Queue API en vez de ejecutar localmente."
mode: primary
model: ollama/qwen3.6:27b
permission:
  edit: deny
  bash: { "curl *": "allow", "git *": "allow", "*": "ask" }
---

Eres el frontend de URA, un sistema de orquestación multi-nodo.

## Tu rol
Cuando el usuario te pida cualquier trabajo, NO lo ejecutes directamente.
En su lugar, crea una tarea en el Task Queue API y devuelve el ID.

## API del orquestador
La URL está en la variable de entorno `URA_ORCHESTRATOR_URL`.
Si no existe, usa la URL configurada al instalar.

### Crear tarea
```bash
curl -s -X POST "$URA_ORCHESTRATOR_URL/tasks" \
  -H "Content-Type: application/json" \
  -d '{"description": "DESCRIPCION", "priority": 0, "timeout_seconds": 1800}'
```

### Verificar estado
```bash
curl -s "$URA_ORCHESTRATOR_URL/tasks/TASK_ID"
```

### Listar tareas
```bash
curl -s "$URA_ORCHESTRATOR_URL/tasks?limit=10"
```

### Stats
```bash
curl -s "$URA_ORCHESTRATOR_URL/stats"
```

### Health check
```bash
curl -s "$URA_ORCHESTRATOR_URL/health"
```

## Flujo
1. Recibe petición del usuario
2. Resume qué vas a enviar como tarea
3. Ejecuta curl POST para crear la tarea
4. Devuelve: ID, estado, resumen
5. Para ver estado: GET /tasks/{id}

## Excepciones — ejecución local
SOLO si el usuario escribe:
- `!local COMANDO` — ejecuta en esta máquina
- `!shell` — vuelve al agente general
- Tarea trivial ("¿qué hora es?", "ls")
AGENT_EOF

echo -e "${GREEN}Agente orchestrator.md creado${NC}"

if [ -f "$OPENCODE_CONFIG" ]; then
    cp "$OPENCODE_CONFIG" "$OPENCODE_CONFIG.bak.$(date +%Y%m%d_%H%M%S)"
    
    if command -v jq &> /dev/null; then
        if ! jq -e ".agent.orchestrator" "$OPENCODE_CONFIG" > /dev/null 2>&1; then
            jq --arg url "$ORCHESTRATOR_URL" \
               '.agent.orchestrator = {
                   "model": "ollama/qwen3.6:27b",
                   "tools": {
                       "read": true, "write": false, "edit": false,
                       "bash": true, "grep": true, "glob": true,
                       "task": true, "webfetch": true, "websearch": true
                   }
               } | .env.URA_ORCHESTRATOR_URL = $url' \
               "$OPENCODE_CONFIG" > "$OPENCODE_CONFIG.tmp" && mv "$OPENCODE_CONFIG.tmp" "$OPENCODE_CONFIG"
            echo -e "${GREEN}Agente orchestrator añadido a opencode.json${NC}"
        else
            echo -e "${YELLOW}Agente orchestrator ya existe en opencode.json${NC}"
        fi
    else
        echo -e "${RED}jq no instalado — instala con: brew install jq (Mac) / sudo apt install jq (GX10)${NC}"
    fi
else
    echo -e "${RED}No se encontró $OPENCODE_CONFIG${NC}"
    exit 1
fi

ENV_FILE="$HOME/.ura/secrets.env"
mkdir -p "$(dirname "$ENV_FILE")"

if [ -f "$ENV_FILE" ]; then
    if grep -q "URA_ORCHESTRATOR_URL" "$ENV_FILE"; then
        sed -i.bak "s|URA_ORCHESTRATOR_URL=.*|URA_ORCHESTRATOR_URL=$ORCHESTRATOR_URL|" "$ENV_FILE"
        rm -f "$ENV_FILE.bak"
    else
        echo "URA_ORCHESTRATOR_URL=$ORCHESTRATOR_URL" >> "$ENV_FILE"
    fi
else
    echo "URA_ORCHESTRATOR_URL=$ORCHESTRATOR_URL" > "$ENV_FILE"
fi

echo -e "${GREEN}URA_ORCHESTRATOR_URL=$ORCHESTRATOR_URL en $ENV_FILE${NC}"
echo ""
echo -e "${GREEN}Configuración completada para $NODE_NAME${NC}"
echo -e "  Agente: $AGENT_FILE"
echo -e "  Config: $OPENCODE_CONFIG"
echo -e "  URL:    $ORCHESTRATOR_URL"
echo -e "  Para usar: reinicia OpenCode, selecciona agente orchestrator"

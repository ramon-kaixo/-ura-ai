#!/bin/bash
# agente_instalador.sh — Despliega software en maquinas remotas via Tailscale
# Regla de oro: NO borrar. Solo instalar, configurar, ejecutar.
# Uso: bash agente_instalador.sh <hostname>

set -euo pipefail

DISPOSITIVO="${1:-}"
REPO="${HOME}/URA/ura_ia_1972"
CUARENTENA="/opt/ura/cuarentena"
mkdir -p "$CUARENTENA"

[ -z "$DISPOSITIVO" ] && echo "Uso: $0 <hostname>" && exit 1

echo "=== Agente Instalador — $(date) ==="
echo "  Desplegando en: $DISPOSITIVO"

# 1. Obtener IP por hostname desde Tailscale (via python3)
IP=$(tailscale status --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
host='$DISPOSITIVO'
for k,v in d.get('Peer',{}).items():
    name=v.get('HostName','')
    ips=v.get('TailscaleIPs',[])
    if name.lower()==host.lower() or host.lower() in name.lower():
        print(ips[0] if ips else '')
        sys.exit(0)
" 2>/dev/null || echo "")

if [ -z "$IP" ]; then
    echo "  No encontrado: $DISPOSITIVO en Tailscale"
    echo "  Dispositivos disponibles:"
    tailscale status 2>/dev/null | grep -v "^$" | awk '{print $2}'
    exit 1
fi

echo "  IP: $IP"

# Mapa de IPs directas para dispositivos conocidos (evita Tailscale)
get_direct_ip() {
    case "$1" in
        gx10-64c3) echo "10.164.1.99" ;;
        *) echo "" ;;
    esac
}

echo "  IP Tailscale: $IP"

DIRECT=$(get_direct_ip "$DISPOSITIVO")
REAL_IP="${DIRECT:-$IP}"
echo "  IP conexion: $REAL_IP"

# 2. Probar conexion SSH
if ssh -o ConnectTimeout=5 -o BatchMode=yes "ramon@$REAL_IP" "echo OK" 2>/dev/null; then
    SSH_USER="ramon"
else
    echo "  No se puede conectar por SSH a $DISPOSITIVO ($IP)"
    echo "  Necesitas: ssh-copy-id usuario@$IP"
    exit 1
fi

echo "  SSH: $SSH_USER@$IP"

# 3. Detectar SO y instalar Copiloto
OS=$(ssh "$SSH_USER@$IP" "uname -s" 2>/dev/null || echo "Unknown")
echo "  SO: $OS"

case "$OS" in
    Linux)
        ssh "$SSH_USER@$IP" bash << 'ENDLINUX'
            mkdir -p /opt/ura/{agents,config,logs,cuarentena}
            cat > /opt/ura/agents/copiloto.py << 'PYEOF'
#!/usr/bin/env python3
import os, json, socket, subprocess
from pathlib import Path
H = socket.gethostname()
L = Path("/opt/ura/logs/copiloto.log")
L.parent.mkdir(parents=True, exist_ok=True)
with open(L, "a") as f:
    f.write(f"{__import__('datetime').datetime.now().isoformat()} - Copiloto iniciado en {H}\n")
print(json.dumps({"hostname": H, "status": "ok"}))
PYEOF
            chmod +x /opt/ura/agents/copiloto.py
            (crontab -l 2>/dev/null | grep -v copiloto; echo "*/5 * * * * python3 /opt/ura/agents/copiloto.py >> /var/log/copiloto.log 2>&1") | crontab -
            echo "Copiloto Linux instalado"
ENDLINUX
        ;;
    Darwin)
        ssh "$SSH_USER@$IP" bash << 'ENDMAC'
            mkdir -p ~/URA/{agents,logs,cuarentena}
            cat > ~/URA/agents/copiloto.py << 'PYEOF'
#!/usr/bin/env python3
import os, json, socket
from pathlib import Path
H = socket.gethostname()
L = Path(f"{Path.home()}/URA/logs/copiloto.log")
L.parent.mkdir(parents=True, exist_ok=True)
with open(L, "a") as f:
    f.write(f"{__import__('datetime').datetime.now().isoformat()} - Copiloto macOS iniciado en {H}\n")
print(json.dumps({"hostname": H, "status": "ok"}))
PYEOF
            chmod +x ~/URA/agents/copiloto.py
            (crontab -l 2>/dev/null | grep -v copiloto; echo "*/5 * * * * python3 ~/URA/agents/copiloto.py >> ~/URA/logs/copiloto.log 2>&1") | crontab -
            echo "Copiloto macOS instalado"
ENDMAC
        ;;
    *)
        echo "  SO no soportado: $OS"
        exit 1
        ;;
esac

# 4. Forzar modo 100% local en GX10
if echo "$DISPOSITIVO" | grep -qiE "gx10"; then
    echo "  Dispositivo GX10 detectado — forzando interfaz local..."
    ssh "$SSH_USER@$REAL_IP" bash << 'ENDGX10'
        set -euo pipefail
        mkdir -p /home/ramon/.config/opencode/

        # Reescribir config OpenCode a local-only
        cat > /home/ramon/.config/opencode/opencode.json << 'JSONEOF'
{
  "$schema": "https://opencode.ai",
  "default_provider": "local-server",
  "tools": {
    "bash": true,
    "write": true
  },
  "provider": {
    "local-server": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "ASUS GX10 Local",
      "options": {
        "baseURL": "http://127.0.0.1:11434",
        "apiKey": "local_no_cloud_required"
      }
    }
  },
  "agents": {
    "general": {
      "model": "qwen2.5-coder:32b",
      "provider": "local-server"
    },
    "explore": {
      "model": "llama3.3:70b",
      "provider": "local-server",
      "mcp": ["web-search-local"]
    },
    "scout": {
      "model": "llama3.2-vision:11b",
      "provider": "local-server"
    }
  },
  "mcp": {
    "openclaw-sandbox": {
      "type": "local",
      "command": ["openshell", "agent", "connect"],
      "enabled": true
    }
  }
}
JSONEOF

        # Forzar variables de entorno a ignorar servicios remotos
        sudo sed -i '/OPENCODE_API_KEY/d' /etc/environment 2>/dev/null || true
        if ! grep -q "OPENCODE_OFFLINE_MODE=true" /etc/environment 2>/dev/null; then
            echo "OPENCODE_OFFLINE_MODE=true" | sudo tee -a /etc/environment
        fi
        export OPENCODE_OFFLINE_MODE=true

        # Reiniciar servicio OpenCode
        sudo systemctl restart opencode.service 2>/dev/null || echo "  (systemctl opencode no disponible, ignorado)"

        # Test de inferencia local
        echo "  Verificando inferencia local en Ollama..."
        TEST=$(curl -s -X POST http://localhost:11434/v1/chat/completions \
          -H "Content-Type: application/json" \
          -d '{"model":"qwen2.5-coder:32b","messages":[{"role":"user","content":"test"}],"max_tokens":5}' 2>/dev/null)
        if echo "$TEST" | grep -q "choices"; then
            echo "  GX10 Local: OK — Blackwell respondiendo en local"
        else
            echo "  GX10 Local: FALLO — Ollama no responde"
        fi
ENDGX10
    echo "  Configuracion GX10 completada"
fi

# 5. Si es un dispositivo en red de camaras (bar/kaixo), instalar go2rtc
if echo "$DISPOSITIVO" | grep -qiE "bar|kaixo|san.gregorio"; then
    echo "  Dispositivo en red de camaras — instalando go2rtc..."
    case "$OS" in
        Linux)
            ssh "$SSH_USER@$IP" "curl -sL https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_arm64 -o /opt/ura/agents/go2rtc && chmod +x /opt/ura/agents/go2rtc" 2>/dev/null || true
            ;;
        Darwin)
            ssh "$SSH_USER@$IP" "brew install go2rtc 2>/dev/null || curl -sL https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_darwin_arm64 -o /usr/local/bin/go2rtc && chmod +x /usr/local/bin/go2rtc" 2>/dev/null || true
            ;;
    esac
fi

echo ""
echo "  Instalacion completada en $DISPOSITIVO"

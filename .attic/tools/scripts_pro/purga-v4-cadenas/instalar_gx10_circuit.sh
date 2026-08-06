#!/bin/bash
# instalar_gx10_circuit.sh – Despliega circuit breaker y mantenimiento en ASUS GX10
# Uso: bash scripts/pro/instalar_gx10_circuit.sh
# Requiere: ssh key-based auth a ramon@10.164.1.99

set -e

GX10_IP="${1:-10.164.1.99}"
GX10_USER="${2:-ramon}"

echo "=== Instalando componentes en GX10 ($GX10_USER@$GX10_IP) ==="

ssh "$GX10_USER@$GX10_IP" bash << 'EOF'
set -e

# Crear directorios
sudo mkdir -p /opt/ura/agents /opt/ura/scripts /opt/ura/data/cuarentena
sudo chown -R ramon:ramon /opt/ura

# --- Monitor circuit breaker ---
cat > /opt/ura/agents/monitor_circuit_breaker.py << 'PYEOF'
#!/usr/bin/env python3
"""monitor_circuit_breaker.py – Aísla agentes con fallos consecutivos (GX10)."""

import json
import os
import subprocess
import time
from datetime import datetime

FALLOS_FILE = "/opt/ura/data/fallos_agentes.json"
CUARENTENA_DIR = "/opt/ura/data/cuarentena"
UMBRAL_FALLOS = int(os.environ.get("CB_UMBRAL_FALLOS", "10"))
VENTANA_SEGUNDOS = int(os.environ.get("CB_VENTANA_SEGUNDOS", "120"))
NOTIFICAR_SCRIPT = "/opt/ura/scripts/notificar.sh"
SUGERENCIAS_FILE = "/opt/ura/data/sugerencias.json"

AGENTES = [
    "ollama",
    "n8n",
    "tailscaled",
    "docker",
    "ura_api.py",
    "openclaw_bridge.py",
]

def cargar_fallos():
    if os.path.exists(FALLOS_FILE):
        with open(FALLOS_FILE) as f:
            return json.load(f)
    return {}

def guardar_fallos(data):
    with open(FALLOS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def esta_en_cuarentena(agente):
    return os.path.exists(os.path.join(CUARENTENA_DIR, f"{agente}.lock"))

def verificar_agente(agente):
    if agente in ("ollama", "n8n", "tailscaled"):
        result = subprocess.run(
            ["systemctl", "is-active", agente], capture_output=True
        )
        return result.returncode == 0
    result = subprocess.run(["pgrep", "-f", agente], capture_output=True)
    return result.returncode == 0

def notificar(mensaje):
    if os.path.exists(NOTIFICAR_SCRIPT):
        subprocess.run([NOTIFICAR_SCRIPT, mensaje])

def agregar_sugerencia(problema, solucion):
    sugerencias = []
    if os.path.exists(SUGERENCIAS_FILE):
        with open(SUGERENCIAS_FILE) as f:
            sugerencias = json.load(f)
    sugerencias.append({
        "timestamp": time.time(),
        "dominio": "circuit_breaker",
        "problema": problema,
        "solucion": solucion,
        "gravedad": "alta",
    })
    with open(SUGERENCIAS_FILE, "w") as f:
        json.dump(sugerencias, f, indent=2)

def main():
    os.makedirs(CUARENTENA_DIR, exist_ok=True)
    fallos = cargar_fallos()
    ahora = time.time()

    for agente in AGENTES:
        if esta_en_cuarentena(agente):
            continue
        vivo = verificar_agente(agente)
        if not vivo:
            fallos.setdefault(agente, []).append(ahora)
            fallos[agente] = [t for t in fallos[agente] if ahora - t <= VENTANA_SEGUNDOS]
            if len(fallos[agente]) >= UMBRAL_FALLOS:
                lock_file = os.path.join(CUARENTENA_DIR, f"{agente}.lock")
                with open(lock_file, "w") as f:
                    f.write(f"Aislado por {UMBRAL_FALLOS} fallos en {VENTANA_SEGUNDOS}s\n")
                    f.write(f"Fecha: {datetime.now().isoformat()}\n")
                if agente in ("ollama", "n8n", "tailscaled"):
                    subprocess.run(["sudo", "systemctl", "stop", agente], capture_output=True)
                else:
                    subprocess.run(["pkill", "-f", agente], capture_output=True)
                notificar(f"Agente {agente} aislado en GX10")
                agregar_sugerencia(
                    f"Agente {agente} en GX10 aislado",
                    f"Revisar logs y luego eliminar {lock_file}",
                )
                fallos[agente] = []
    guardar_fallos(fallos)

if __name__ == "__main__":
    main()
PYEOF
chmod +x /opt/ura/agents/monitor_circuit_breaker.py

# --- Reactivacion cuarentena ---
cat > /opt/ura/scripts/reactivar_cuarentena.sh << 'BASH'
#!/bin/bash
CUARENTENA_DIR="/opt/ura/data/cuarentena"
MIN_EDAD="${1:-720}"
find "$CUARENTENA_DIR" -name "*.lock" -type f -mmin "+$MIN_EDAD" -delete
echo "$(date) - Reactivacion GX10: locks eliminados (min: ${MIN_EDAD}m)"
BASH
chmod +x /opt/ura/scripts/reactivar_cuarentena.sh

# --- Mantenimiento periódico GX10 ---
cat > /opt/ura/scripts/mantenimiento_gx10.sh << 'BASH'
#!/bin/bash
# mantenimiento_gx10.sh – Tareas de mantenimiento cada 6h en GX10

LOG="/var/log/ura_mantenimiento_gx10.log"
echo "$(date) - Iniciando mantenimiento GX10" >> "$LOG"

python3 /opt/ura/agents/monitor_circuit_breaker.py >> "$LOG" 2>&1
/opt/ura/scripts/reactivar_cuarentena.sh >> "$LOG" 2>&1
sudo logrotate -f /etc/logrotate.d/ura >> "$LOG" 2>&1 || true
docker system prune -f --filter "until=24h" >> "$LOG" 2>&1 || true

echo "$(date) - Mantenimiento GX10 completado" >> "$LOG"
BASH
chmod +x /opt/ura/scripts/mantenimiento_gx10.sh

# --- logrotate para Linux ---
sudo tee /etc/logrotate.d/ura << 'LROT'
/opt/ura/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ramon ramon
}
/var/log/ura_*.log {
    daily
    rotate 7
    compress
    missingok
}
LROT

# --- Crontab ---
(crontab -l 2>/dev/null | grep -v "monitor_circuit_breaker" | grep -v "reactivar_cuarentena" | grep -v "mantenimiento_gx10"; echo "* * * * * /usr/bin/python3 /opt/ura/agents/monitor_circuit_breaker.py >> /var/log/circuit_breaker.log 2>&1"; echo "0 3 * * * /opt/ura/scripts/reactivar_cuarentena.sh >> /var/log/ura_cuarentena.log 2>&1"; echo "0 */6 * * * /opt/ura/scripts/mantenimiento_gx10.sh") | crontab -

echo "GX10 instalacion completada"
EOF

echo "GX10 listo."

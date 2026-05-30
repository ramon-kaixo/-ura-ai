#!/bin/bash
# deploy_copilotos.sh — Despliega agentes Copiloto en todos los ordenadores de la red Tailscale
# Uso:
#   bash scripts/pro/deploy_copilotos.sh              # Despliega en todos los detectados
#   bash scripts/pro/deploy_copilotos.sh --dry-run     # Solo muestra que haría
#   bash scripts/pro/deploy_copilotos.sh gx10-64c3     # Despliega solo en esa máquina

set -euo pipefail
DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true && shift

TARGET="${1:-}"
REPO="${HOME}/URA/ura_ia_1972"
TRAMPA="${REPO}/scripts/pro/trampa_rm.sh"

# Mapa: hostname -> IP/usuario/OS
MAQUINAS="gx10-64c3:ramon@10.164.1.99:linux
caja0:barkaixo@100.127.217.113:windows
desktop-0d7s0tc:barkaixo@100.88.13.84:windows
mac-mini-bar-san-gregorio:barkaixo@100.109.83.16:macos
mac-mini-de-kaixo:barkaixo@100.73.155.53:macos
mac-mini-san-gregorio:barkaixo@100.90.99.76:macos
macbook-air-de-kaixo:barkaixo@100.77.230.38:macos
mini-de-ramon:barkaixo@100.118.17.96:macos"

deploy_linux() {
    local host="$1" ssh_user="$2"
    echo "  → Desplegando en Linux: $ssh_user"
    ssh "$ssh_user" bash << 'EOL'
        mkdir -p /opt/ura/{cuarentena,agents,logs}
        cat > /opt/ura/trampa_rm.sh << 'EOF'
#!/bin/bash
CUARENTENA="${URA_CUARENTENA:-/opt/ura/cuarentena}"
mkdir -p "$CUARENTENA"
for arg in "$@"; do
    case "$arg" in -rf|-r|-f|--*) continue ;; esac
    [ -e "$arg" ] && mv "$arg" "$CUARENTENA/$(basename "$arg").$(date +%s)" 2>/dev/null
done
EOF
        chmod +x /opt/ura/trampa_rm.sh
        cat > /opt/ura/agents/copiloto.py << 'PYEOF'
#!/usr/bin/env python3
import os, subprocess, json, socket
from pathlib import Path
H = socket.gethostname()
L = Path(f"/opt/ura/logs/copiloto_{H}.log")
L.parent.mkdir(parents=True, exist_ok=True)
def log(m):
    with open(L, "a") as f: f.write(f"{__import__('datetime').datetime.now().isoformat()} - {m}\n")
def reportar():
    e = {"hostname": H, "hostname -I": subprocess.run(["hostname","-I"],capture_output=True,text=True).stdout.strip()}
    log(f"Estado: {json.dumps(e)}")
    return e
if __name__ == "__main__":
    log("Copiloto iniciado")
    print(json.dumps(reportar()))
PYEOF
        chmod +x /opt/ura/agents/copiloto.py
        (crontab -l 2>/dev/null | grep -v copiloto; echo "*/5 * * * * python3 /opt/ura/agents/copiloto.py >> /var/log/copiloto.log 2>&1") | crontab -
        echo "  ✅ Copiloto instalado en $H"
EOL
}

deploy_macos() {
    local host="$1" ssh_user="$2"
    echo "  → Desplegando en macOS: $ssh_user"
    ssh "$ssh_user" bash << 'EOL'
        mkdir -p ~/URA/{cuarentena,agents,logs}
        cat > ~/URA/trampa_rm.sh << 'EOF'
#!/bin/bash
CUARENTENA="${URA_CUARENTENA:-$HOME/URA/cuarentena}"
mkdir -p "$CUARENTENA"
for arg in "$@"; do
    case "$arg" in -rf|-r|-f|--*) continue ;; esac
    [ -e "$arg" ] && mv "$arg" "$CUARENTENA/$(basename "$arg").$(date +%s)" 2>/dev/null
done
EOF
        chmod +x ~/URA/trampa_rm.sh
        cat > ~/URA/agents/copiloto.py << 'PYEOF'
#!/usr/bin/env python3
import os, subprocess, json, socket
from pathlib import Path
H = socket.gethostname()
L = Path(f"{Path.home()}/URA/logs/copiloto_{H}.log")
L.parent.mkdir(parents=True, exist_ok=True)
def log(m):
    with open(L, "a") as f: f.write(f"{__import__('datetime').datetime.now().isoformat()} - {m}\n")
def reportar():
    e = {"hostname": H, "usuario": os.getenv("USER")}
    log(f"Estado: {json.dumps(e)}")
    return e
if __name__ == "__main__":
    log("Copiloto macOS iniciado")
    print(json.dumps(reportar()))
PYEOF
        chmod +x ~/URA/agents/copiloto.py
        (crontab -l 2>/dev/null | grep -v copiloto; echo "*/5 * * * * python3 ~/URA/agents/copiloto.py >> ~/URA/logs/copiloto.log 2>&1") | crontab -
        echo "  ✅ Copiloto instalado en $(hostname -s)"
EOL
}

deploy_windows() {
    local host="$1" ssh_user="$2"
    echo "  → Desplegando en Windows: $ssh_user"
    # Windows requiere PowerShell remoto en lugar de bash
    ssh "$ssh_user" powershell << 'EOL' 2>/dev/null || echo "  ⚠️  Windows requiere PowerShell. SSH basico no funciona."
        New-Item -ItemType Directory -Force -Path "C:\URA\cuarentena", "C:\URA\agents", "C:\URA\logs" | Out-Null
        $script = @'
#!/usr/bin/env python3
import os, subprocess, json, socket
from pathlib import Path
H = socket.gethostname()
L = Path("C:/URA/logs/copiloto_{H}.log".format(H=H))
L.parent.mkdir(parents=True, exist_ok=True)
def log(m):
    with open(L, "a") as f: f.write(f"{__import__('datetime').datetime.now().isoformat()} - {m}\n")
def reportar():
    e = {"hostname": H, "os": "windows"}
    log(f"Estado: {json.dumps(e)}")
    return e
if __name__ == "__main__":
    log("Copiloto Windows iniciado")
    print(json.dumps(reportar()))
'@
        $script | Out-File -FilePath "C:\URA\agents\copiloto.py" -Encoding utf8
        # Programar tarea cada 5 min
        $action = New-ScheduledTaskAction -Execute "python3" -Argument "C:\URA\agents\copiloto.py"
        $trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes 5)
        Register-ScheduledTask -TaskName "URACopiloto" -Action $action -Trigger $trigger -Force | Out-Null
        Write-Output "  ✅ Copiloto instalado en Windows"
EOL
}

echo "=== Despliegue de Copilotos URA ==="
echo ""

if [ -n "$TARGET" ]; then
    matched=false
    while IFS=':' read -r name ssh_user os; do
        if [ "$name" = "$TARGET" ]; then
            matched=true
            echo "Desplegando en $name ($os)..."
            $DRY_RUN && echo "  [DRY-RUN] se desplegaria en $ssh_user" && exit 0
            "deploy_$os" "$name" "$ssh_user"
            break
        fi
    done <<< "$MAQUINAS"
    $matched || { echo "Maquina '$TARGET' no definida en el mapa"; exit 1; }
else
    for host in $MAQUINAS; do
        IFS=':' read -r name ssh_user os <<< "$host"
        echo "--- $name ($os) ---"
        if $DRY_RUN; then
            echo "  [DRY-RUN] ssh $ssh_user ..."
            continue
        fi
        if ssh -o ConnectTimeout=3 -o BatchMode=yes -o StrictHostKeyChecking=no "$ssh_user" "exit" 2>/dev/null; then
            "deploy_$os" "$name" "$ssh_user"
        else
            echo "  ⚠️  No accesible por SSH ($ssh_user), se omite"
        fi
    done
fi

echo ""
echo "=== Despliegue completado ==="

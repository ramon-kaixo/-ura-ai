#!/bin/bash
# instalar_autonomia_total.sh - Instala el sistema completo de autonomia URA
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
SSH_AUTH_SOCK="$HOME/.ssh/agent.sock"
SSH_KEY="$HOME/.ssh/id_ura_gx10"
SKIP_SMB=false

for arg in "$@"; do
    case "$arg" in
        --skip-smb) SKIP_SMB=true ;;
    esac
done

echo "========================================="
echo "  URA - Instalacion Autonomia Total"
echo "  $(date)"
if $SKIP_SMB; then echo "  (SMB omitido)"; fi
echo "========================================="

# 1. Configuracion SSH
echo ""
echo "[1/8] Configurando SSH dedicado para URA..."
bash "${REPO}/scripts/setup_ssh_ura.sh"
echo "   ✅ SSH configurado"

# 2. Dependencias
echo ""
echo "[2/8] Instalando dependencias..."
brew install mdbtools jq gpg 2>/dev/null || true
"${REPO}/.venv/bin/pip" install keyring paramiko requests pandas 2>/dev/null || true
echo "   ✅ Dependencias instaladas"

# 3. Directorios y permisos (Punto 5)
echo ""
echo "[3/8] Creando estructura de directorios..."
mkdir -p "$REPO/data/registry/eventos"
mkdir -p "$REPO/data/registry/procesados"
mkdir -p "$REPO/data/registry/fallidos"
mkdir -p "$REPO/data/planes"
mkdir -p "$REPO/sandbox/Aprendizaje/Enjambre/buzos"
mkdir -p "$REPO/sandbox/Aprendizaje/Enjambre/informes"
chmod 700 "$REPO/data/registry/eventos"
echo '{"nodos":[]}' > "$REPO/data/nodos_conocidos.json"
echo "   ✅ Directorios creados"

# 4. Permisos de scripts
echo ""
echo "[4/8] Configurando permisos..."
find "$REPO/scripts" -name "*.sh" -exec chmod +x {} \;
find "$REPO/scripts" -name "*.py" -exec chmod +x {} \;
find "$REPO/sandbox" -name "*.sh" -exec chmod +x {} \;
echo "   ✅ Permisos configurados"

# 5. Configuracion
echo ""
echo "[5/8] Verificando configuracion..."
for cfg in deployment_recipes.json fallback_roles.json tpv_endpoints.json; do
    if [ -f "$REPO/config/$cfg" ]; then
        echo "   ✅ $cfg"
    else
        echo "   ⚠️ $cfg falta"
    fi
done

# 6. Montaje automatico SMB (TPV)
if $SKIP_SMB; then
    echo ""
    echo "[6/8] Montaje SMB omitido (--skip-smb)"
    echo "   ℹ️  Para activar TPV Spy: security add-internet-password -a barkaixo ..."
else
    echo ""
    echo "[6/8] Configurando montaje SMB automatico..."
    mkdir -p /Volumes/Compartida 2>/dev/null || true
    cat > "$PLIST_DIR/com.ura.mount.smb.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.mount.smb</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${REPO}/scripts/mount_smb.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ura_mount_smb.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_mount_smb.err</string>
</dict>
</plist>
EOF
    launchctl bootout gui/$(id -u)/com.ura.mount.smb 2>/dev/null || true
    if launchctl bootstrap gui/$(id -u) "$PLIST_DIR/com.ura.mount.smb.plist" 2>/dev/null; then
        echo "   ✅ Montaje SMB automatico cargado"
    else
        echo "   ℹ️  Se cargara automaticamente al reiniciar sesion"
    fi
fi

# 7. Timers launchd con SSH_AUTH_SOCK
echo ""
echo "[7/8] Instalando timers..."
mkdir -p "$PLIST_DIR"

ENV_VARS="    <key>EnvironmentVariables</key>
    <dict>
        <key>SSH_AUTH_SOCK</key>
        <string>${SSH_AUTH_SOCK}</string>
        <key>SSH_USER</key>
        <string>ramon</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>"

# Timer descubrimiento nodos (cada 5 min)
cat > "$PLIST_DIR/com.ura.nodo_discovery.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.nodo_discovery</string>
    <key>ProgramArguments</key>
    <array>
        <string>bash</string>
        <string>${REPO}/sandbox/Aprendizaje/Enjambre/buzos/buzo_tailscale_discovery.sh</string>
    </array>
${ENV_VARS}
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ura_nodo_discovery.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_nodo_discovery_err.log</string>
</dict>
</plist>
EOF
launchctl bootout gui/$(id -u)/com.ura.nodo_discovery 2>/dev/null || true
if launchctl bootstrap gui/$(id -u) "$PLIST_DIR/com.ura.nodo_discovery.plist" 2>/dev/null; then
    echo "   ✅ Discovery nodos cada 5 min"
else
    echo "   ℹ️  Se cargara al reiniciar sesion"
fi

# Timer analisis nodos (cada 10 min)
cat > "$PLIST_DIR/com.ura.nodo_analisis.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.nodo_analisis</string>
    <key>ProgramArguments</key>
    <array>
        <string>${REPO}/.venv/bin/python3</string>
        <string>${REPO}/scripts/analizador_nodos.py</string>
    </array>
${ENV_VARS}
    <key>StartInterval</key>
    <integer>600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ura_nodo_analisis.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_nodo_analisis_err.log</string>
</dict>
</plist>
EOF
launchctl bootout gui/$(id -u)/com.ura.nodo_analisis 2>/dev/null || true
if launchctl bootstrap gui/$(id -u) "$PLIST_DIR/com.ura.nodo_analisis.plist" 2>/dev/null; then
    echo "   ✅ Analisis nodos cada 10 min"
else
    echo "   ℹ️  Se cargara al reiniciar sesion"
fi

# Timer TPV Spy (cada 30 min)
cat > "$PLIST_DIR/com.ura.tpvsyp.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.tpvsyp</string>
    <key>ProgramArguments</key>
    <array>
        <string>${REPO}/.venv/bin/python3</string>
        <string>${REPO}/scripts/tpv_spy.py</string>
    </array>
${ENV_VARS}
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ura_tpv_spy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_tpv_spy_err.log</string>
</dict>
</plist>
EOF
launchctl bootout gui/$(id -u)/com.ura.tpvsyp 2>/dev/null || true
if launchctl bootstrap gui/$(id -u) "$PLIST_DIR/com.ura.tpvsyp.plist" 2>/dev/null; then
    echo "   ✅ TPV Spy cada 30 min"
else
    echo "   ℹ️  Se cargara al reiniciar sesion"
fi

# Timer consolidacion resultados (cada hora)
cat > "$PLIST_DIR/com.ura.consolidar.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.consolidar</string>
    <key>ProgramArguments</key>
    <array>
        <string>bash</string>
        <string>${REPO}/scripts/consolidar_resultados.sh</string>
    </array>
${ENV_VARS}
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ura_consolidar.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_consolidar_err.log</string>
</dict>
</plist>
EOF
launchctl bootout gui/$(id -u)/com.ura.consolidar 2>/dev/null || true
if launchctl bootstrap gui/$(id -u) "$PLIST_DIR/com.ura.consolidar.plist" 2>/dev/null; then
    echo "   ✅ Consolidacion resultados cada hora"
else
    echo "   ℹ️  Se cargara al reiniciar sesion"
fi

# 8. Verificacion
echo ""
echo "[8/8] Verificacion final..."
echo "   Tailscale: $(tailscale status >/dev/null 2>&1 && echo '✅' || echo '⚠️ no configurado')"
echo "   mdbtools:  $(command -v mdb-export >/dev/null 2>&1 && echo '✅' || echo '⚠️ no instalado')"
echo "   Paramiko:  $("${REPO}/.venv/bin/python3" -c 'import paramiko' 2>/dev/null && echo '✅' || echo '⚠️ no disponible')"
echo "   Keyring:   $("${REPO}/.venv/bin/python3" -c 'import keyring' 2>/dev/null && echo '✅' || echo '⚠️ no disponible')"
echo "   GPG:       $(command -v gpg >/dev/null 2>&1 && echo '✅' || echo '⚠️ no instalado')"
echo "   SSH key:   $([ -f "$SSH_KEY" ] && echo '✅' || echo '⚠️ no generada')"
echo "   SSH gx10:  $(ssh -o ConnectTimeout=5 gx10 echo ok 2>/dev/null && echo '✅' || echo '⚠️ requiere Full Disk Access')"
echo "   SMB:       $(mount | grep -q Compartida && echo '✅' || echo '⏳ pendiente')"

echo ""
echo "========================================="
echo "  Instalacion completada"
echo "========================================="
echo ""
echo "Proximos pasos:"
echo "  1. Conceder Acceso Total al Disco a Terminal.app en Preferencias → Privacidad"
if $SKIP_SMB; then
    echo "  2. SMB pendiente — activar TPV Spy:"
    echo "     read -s SMB_PASSWORD"
    echo "     security add-internet-password -a \"barkaixo\" -s \"10.164.1.99\" -w \"\$SMB_PASSWORD\" -r \"smb \" -T /usr/bin/security -T /System/Library/CoreServices/NetAuthAgent.app -U"
    echo "     open smb://barkaixo@10.164.1.99/Compartida"
    echo "     Verificar: security find-internet-password -s \"10.164.1.99\" -w"
    echo "  3. Copiar clave publica al GX10: ssh-copy-id -i ~/.ssh/id_ura_gx10.pub ramon@10.164.1.99"
    echo "  4. Configurar URA_TOKEN para HMAC: export URA_TOKEN=\$(openssl rand -hex 32)"
    echo "  5. Ver logs: tail -f /tmp/ura_nodo_discovery.log"
else
    echo "  2. Copiar clave publica al GX10: ssh-copy-id -i ~/.ssh/id_ura_gx10.pub ramon@10.164.1.99"
    echo "  3. Configurar URA_TOKEN para HMAC: export URA_TOKEN=\$(openssl rand -hex 32)"
    echo "  4. Ver logs: tail -f /tmp/ura_mount_smb.log && tail -f /tmp/ura_nodo_discovery.log"
fi

#!/bin/bash
# auto_generate_installers.sh – Genera los scripts de instalación de Tailscale para cocinas
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Generador de scripts de instalación Tailscale para URA ===${NC}"

read -p "Introduce la clave de autenticación de Tailscale (tskey-auth-...): " TS_KEY
if [ -z "$TS_KEY" ]; then
    echo "❌ No se proporcionó clave. Saliendo."
    exit 1
fi

read -p "Introduce la IP Tailscale del Mac Mini [100.123.81.101]: " MAESTRO_IP
MAESTRO_IP=${MAESTRO_IP:-100.123.81.101}

OUT_DIR="/opt/ura/tailscale_installers"
mkdir -p "$OUT_DIR"
echo -e "${YELLOW}Generando scripts en $OUT_DIR${NC}"

# Script para aprovisionamiento remoto (SSH)
cat > "$OUT_DIR/aprovisionar_lan.sh" << 'EOF'
#!/bin/bash
# Aprovisionamiento remoto via SSH – requiere que el destino tenga SSH activo
TS_KEY="PLACEHOLDER_TS_KEY"
MAESTRO_IP="PLACEHOLDER_MAESTRO_IP"
EOF

# Script para Windows (USB)
cat > "$OUT_DIR/instalar_tailscale_ura.bat" << EOF
@echo off
title Instalador de Tailscale y URA (cocina)
echo ============================================
echo  Instalador para ordenadores de cocina (Windows)
echo ============================================
echo.

set TS_KEY=$TS_KEY
set MAESTRO_IP=$MAESTRO_IP

:: Verificar PowerShell
powershell -Command "exit 0" 2>nul
if errorlevel 1 (
    echo ERROR: PowerShell no está disponible. Instale PowerShell 3.0 o superior.
    pause
    exit /b 1
)

:: Verificar permisos de administrador
net session >nul 2>&1
if errorlevel 1 (
    echo Este script debe ejecutarse como Administrador.
    pause
    exit /b 1
)

set /p NODO="Nombre de este nodo (ej. cocina_bar1): "
if "%NODO%"=="" set NODO=cocina_%COMPUTERNAME%

echo Instalando Tailscale...
powershell -Command "Invoke-WebRequest -Uri 'https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe' -OutFile '%TEMP%\tailscale.exe'"
start /wait %TEMP%\tailscale.exe /quiet

echo Autenticando...
"%ProgramFiles%\Tailscale\tailscale.exe" up --authkey %TS_KEY% --hostname %NODO% --unattended

echo Creando script de heartbeat...
mkdir C:\ura\bin 2>nul
powershell -Command "\$heartbeat = @'\n\$disk = Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"\n\$disco_pct = [math]::Round(((\$disk.Size - \$disk.FreeSpace)/\$disk.Size)*100)\n\$ram = Get-CimInstance Win32_OperatingSystem\n\$ram_pct = [math]::Round(((\$ram.TotalVisibleMemorySize - \$ram.FreePhysicalMemory)/\$ram.TotalVisibleMemorySize)*100)\n\$json = \"{\\\"nodo\\\": \\\"%NODO%\\\", \\\"disco_pct\\\": \$disco_pct, \\\"ram_pct\\\": \$ram_pct, \\\"fallos_consecutivos\\\": 0}\"\nInvoke-RestMethod -Uri \"http://%MAESTRO_IP%:8081/api/v1/heartbeat\" -Method Post -Body \$json -ContentType \"application/json\"\n'@; Set-Content -Path 'C:\ura\bin\heartbeat.ps1' -Value \$heartbeat"

echo Programando tarea cada minuto...
schtasks /create /tn "URA_Heartbeat" /tr "powershell.exe -WindowStyle Hidden -File C:\ura\bin\heartbeat.ps1" /sc minute /mo 1 /ru "SYSTEM" /f

echo Instalación completada. El nodo reportará cada minuto.
pause
EOF

# Script para Linux (USB)
cat > "$OUT_DIR/instalar_tailscale_ura.sh" << EOF
#!/bin/bash
TS_KEY="$TS_KEY"
MAESTRO_IP="$MAESTRO_IP"

if [ "\$EUID" -ne 0 ]; then
    echo "Ejecuta con sudo: sudo bash \$0"
    exit 1
fi

read -p "Nombre de este nodo (ej. cocina_bar1): " NODO
if [ -z "\$NODO" ]; then
    NODO="cocina_\$(hostname)"
fi

echo "Instalando Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey "\$TS_KEY" --hostname "\$NODO"

echo "Creando heartbeat..."
mkdir -p /opt/ura/bin
cat > /opt/ura/bin/heartbeat.sh << INNER
#!/bin/bash
DISCO=\$(df / | tail -1 | awk '{print \$5}' | sed 's/%//')
RAM=\$(free | grep Mem | awk '{print int(\$3/\$2 * 100)}')
JSON="{\\\"nodo\\\": \\\"\${NODO}\\\", \\\"disco_pct\\\": \$DISCO, \\\"ram_pct\\\": \$RAM, \\\"fallos_consecutivos\\\": 0}"
curl -s -X POST -H "Content-Type: application/json" -d "\$JSON" http://${MAESTRO_IP}:8081/api/v1/heartbeat
INNER
chmod +x /opt/ura/bin/heartbeat.sh

(crontab -l 2>/dev/null; echo '* * * * * /opt/ura/bin/heartbeat.sh') | crontab -

echo "✅ Instalación completada para \$NODO"
EOF

chmod +x "$OUT_DIR"/aprovisionar_lan.sh "$OUT_DIR"/instalar_tailscale_ura.sh

echo -e "${GREEN}✅ Scripts generados en $OUT_DIR${NC}"
echo "📁 Copia los siguientes archivos a un USB:"
echo "   - Para Windows: ${OUT_DIR}/instalar_tailscale_ura.bat"
echo "   - Para Linux: ${OUT_DIR}/instalar_tailscale_ura.sh"
echo "   - Para aprovisionamiento remoto: ${OUT_DIR}/aprovisionar_lan.sh"

#!/bin/bash
# instalar_modem_4g.sh - Instala paquetes y configura wvdial para módem 4G USB
set -e

echo "Instalando paquetes para módem 4G..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt-get update
    sudo apt-get install -y usb-modeswitch wvdial ppp
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "En macOS no se soporta wvdial nativamente. Usa un router 4G independiente o configura la red de otra forma."
    exit 0
fi

# Configuración básica de wvdial (ejemplo para España, operador Movistar)
# El usuario deberá ajustar el APN según su operadora
sudo tee /etc/wvdial.conf > /dev/null <<'EOF'
[Dialer Default]
Modem = /dev/ttyUSB0
Baud = 460800
Init1 = ATZ
Init2 = ATQ0 V1 E1 S0=0 &C1 &D2 +FCLASS=0
Init3 = AT+CGDCONT=1,"IP","movistar.es"
ISDN = 0
Modem Type = USB Modem
Phone = *99#
Username = movistar
Password = movistar
Stupid Mode = 1
EOF

echo "Configuracion de wvdial creada en /etc/wvdial.conf"
echo "REVISA el APN y el dispositivo (/dev/ttyUSB0) según tu módem."
echo "Puedes probar con: sudo pon wvdial"

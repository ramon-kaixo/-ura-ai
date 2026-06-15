#!/bin/bash
set -e
echo "=== Limpieza segura URA ==="
echo "Protegidos (chattr +i):"
find /home/ramon/URA/ura_ia_1972 -exec lsattr -d {} \; 2>/dev/null | grep "\-i.*home" | awk '{print $NF}' | head -10
echo ""
echo "Limpieza permitida (solo no-protegidos):"
find /home/ramon/URA/ura_ia_1972/logs/ -name "*.log" -exec lsattr {} \; 2>/dev/null | grep -v "\-i" | awk '{print $NF}' | head -10
echo ""
echo "Para borrar: ejecute rm sobre los archivos SIN +i"

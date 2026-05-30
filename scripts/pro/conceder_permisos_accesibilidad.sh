#!/bin/bash
# conceder_permisos_accesibilidad.sh — Otorga permisos de accesibilidad a Terminal y navegadores
# Uso: sudo bash conceder_permisos_accesibilidad.sh
# Esto permite a URA controlar teclado y raton via pyautogui/pynput

set -euo pipefail

echo "Concediendo permisos de accesibilidad en macOS..."

APPS=(
    "com.apple.Terminal"
    "com.google.Chrome"
    "com.apple.Safari"
    "com.microsoft.VSCode"
)

for app in "${APPS[@]}"; do
    sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" \
        "INSERT OR IGNORE INTO access VALUES('kTCCServiceAccessibility','$app',0,1,1,NULL,NULL,0,'',NULL,0,1687780800);" 2>/dev/null && \
        echo "  Permiso concedido: $app"
done

echo "Permisos de accesibilidad actualizados. Reinicia las apps para aplicar cambios."

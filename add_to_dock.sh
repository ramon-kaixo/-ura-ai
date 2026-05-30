#!/bin/bash
# Script para añadir URA App al Dock de macOS

SCRIPT_DIR="$(dirname "$0")"
APP_PATH="$SCRIPT_DIR/URA_App_Optimized_Layout.app"

echo "Añadiendo URA App al Dock..."

# Añadir aplicación al Dock
defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file://$APP_PATH</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"

# Reiniciar Dock para aplicar cambios
killall Dock

echo "URA App añadida al Dock. Reiniciando Dock..."

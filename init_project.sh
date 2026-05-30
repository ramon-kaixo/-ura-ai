#!/bin/bash
# Script de inicialización para URA App
# Instala todas las dependencias necesarias

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "URA App - Inicialización del Proyecto"
echo "========================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 no encontrado"
    echo "Por favor instala Python 3.8 o superior desde python.org"
    exit 1
fi

echo "✅ Python 3 encontrado"
echo ""

# Instalar dependencias desde requirements.txt
echo "📦 Instalando dependencias desde requirements.txt..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Dependencias instaladas correctamente"
    echo ""
    echo "Para ejecutar URA App:"
    echo "1. Doble clic en URA.app en el Escritorio"
    echo "2. O ejecuta: python3 $SCRIPT_DIR/main_final.py"
    echo ""
else
    echo ""
    echo "❌ Error instalando dependencias"
    echo ""
    echo "Para instalar manualmente:"
    echo "pip3 install PyQt5>=5.15.0 requests psutil pyautogui SpeechRecognition PyAudio pyttsx3 gTTS playsound"
    exit 1
fi

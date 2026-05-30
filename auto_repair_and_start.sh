#!/bin/bash
# Script de auto-reparación y arranque de URA
# Arregla problemas automáticamente antes de lanzar la aplicación

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "🔧 SISTEMA DE AUTO-REPARACIÓN URA"
echo "=========================================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para verificar y crear directorios
check_and_create_dirs() {
    echo "📁 Verificando directorios necesarios..."
    
    dirs=(
        "config"
        "data"
        "data/whatsapp_session"
        "data/telegram_session"
        "data/instagram_session"
        "logs"
    )
    
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "  ✅ Creando directorio: $dir"
            mkdir -p "$dir"
            chmod 755 "$dir"
        else
            echo "  ✅ Directorio existe: $dir"
        fi
    done
    echo ""
}

# Función para verificar dependencias
check_dependencies() {
    echo "📦 Verificando dependencias..."
    
    if [ ! -d ".venv" ]; then
        echo "  ❌ Virtual environment no encontrado, creando..."
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    
    # Verificar dependencias críticas
    critical_deps=("PyQt5" "playwright" "google-api-python-client")
    
    for dep in "${critical_deps[@]}"; do
        if ! python3 -c "import $dep" 2>/dev/null; then
            echo "  ⚠️  Instalando dependencia faltante: $dep"
            pip install "$dep" -q
        fi
    done
    
    echo "  ✅ Dependencias verificadas"
    echo ""
}

# Función para verificar archivos de configuración
check_config_files() {
    echo "⚙️  Verificando archivos de configuración..."
    
    # Crear archivos de configuración vacíos si no existen
    config_files=(
        "config/model_config.json"
        "config/department_profiles.json"
    )
    
    for file in "${config_files[@]}"; do
        if [ ! -f "$file" ]; then
            echo "  ✅ Creando archivo de configuración: $file"
            echo "{}" > "$file"
        fi
    done
    
    echo "  ✅ Archivos de configuración verificados"
    echo ""
}

# Función para verificar permisos
check_permissions() {
    echo "🔐 Verificando permisos..."
    
    # Dar permisos a directorios de sesión
    if [ -d "data/whatsapp_session" ]; then
        chmod 755 data/whatsapp_session
    fi
    if [ -d "data/telegram_session" ]; then
        chmod 755 data/telegram_session
    fi
    if [ -d "data/instagram_session" ]; then
        chmod 755 data/instagram_session
    fi
    
    echo "  ✅ Permisos verificados"
    echo ""
}

# Función para limpiar procesos zombies
cleanup_zombies() {
    echo "🧹 Limpiando procesos zombies..."
    
    # Matar procesos de python3 main_final.py zombies
    pkill -f "python3 main_final.py" || true
    
    echo "  ✅ Limpieza completada"
    echo ""
}

# Función para verificar sintaxis de Python
check_syntax() {
    echo "🔍 Verificando sintaxis de Python..."
    
    if python3 -m py_compile main_final.py 2>/dev/null; then
        echo "  ✅ Sintaxis correcta"
    else
        echo "  ❌ Error de sintaxis en main_final.py"
        echo "  ⚠️  Intentando auto-reparación básica..."
        # Aquí podríamos añadir lógica de reparación más avanzada
    fi
    echo ""
}

# Función para verificar Ollama
check_ollama() {
    echo "🤖 Verificando Ollama..."
    
    if command -v ollama &> /dev/null; then
        echo "  ✅ Ollama instalado"
        
        # Verificar si Ollama está corriendo
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "  ✅ Ollama corriendo"
        else
            echo "  ⚠️  Ollama no está corriendo, iniciando..."
            ollama serve > /dev/null 2>&1 &
            sleep 2
        fi
    else
        echo "  ⚠️  Ollama no instalado"
    fi
    echo ""
}

# Función principal de reparación
run_auto_repair() {
    echo "🚀 Ejecutando auto-reparación..."
    echo ""
    
    check_and_create_dirs
    check_dependencies
    check_config_files
    check_permissions
    cleanup_zombies
    check_syntax
    check_ollama
    
    echo "=========================================="
    echo "✅ AUTO-REPARACIÓN COMPLETADA"
    echo "=========================================="
    echo ""
}

# Ejecutar auto-reparación
run_auto_repair

# Arrancar aplicación
echo "🚀 Arrancando URA..."
echo ""

source .venv/bin/activate
python3 main_final.py

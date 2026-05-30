#!/bin/bash
# Script de arranque y verificación de Ollama - Solución definitiva
# Este script asegura que Ollama esté corriendo correctamente antes de iniciar URA_App

echo "🔍 Verificando estado de Ollama..."

# Función para verificar si Ollama está corriendo
check_ollama() {
    # Verificar proceso
    if pgrep -f "ollama serve" > /dev/null; then
        echo "✅ Proceso Ollama encontrado"
        
        # Verificar puerto (intentar IPv4 e IPv6)
        if curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
            echo "✅ API Ollama respondiendo en 127.0.0.1:11434"
            return 0
        elif curl -s http://[::1]:11434/api/version > /dev/null 2>&1; then
            echo "✅ API Ollama respondiendo en [::1]:11434"
            return 0
        else
            echo "❌ API Ollama no responde"
            return 1
        fi
    else
        echo "❌ Proceso Ollama no encontrado"
        return 1
    fi
}

# Función para iniciar Ollama
start_ollama() {
    echo "🚀 Iniciando Ollama..."
    
    # Matar cualquier proceso existente en el puerto 11434
    lsof -ti:11434 | xargs kill -9 2>/dev/null || true
    
    # Iniciar Ollama en background
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    
    # Esperar a que Ollama arranque
    echo "⏳ Esperando a que Ollama arranque..."
    for i in {1..30}; do
        sleep 1
        if curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
            echo "✅ Ollama arrancado correctamente"
            return 0
        fi
        echo "   Esperando... ($i/30)"
    done
    
    echo "❌ Ollama no arrancó después de 30 segundos"
    return 1
}

# Verificar estado actual
if check_ollama; then
    echo "✅ Ollama ya está corriendo correctamente"
else
    echo "⚠️ Ollama no está corriendo correctamente, iniciándolo..."
    if start_ollama; then
        echo "✅ Ollama iniciado con éxito"
    else
        echo "❌ Error al iniciar Ollama"
        echo "📋 Log de Ollama:"
        cat /tmp/ollama.log
        exit 1
    fi
fi

# Verificar modelos
echo "🔍 Verificando modelos de Ollama..."
MODEL_COUNT=$(ollama list 2>/dev/null | grep -c ":" || echo "0")
if [ "$MODEL_COUNT" -gt 0 ]; then
    echo "✅ $MODEL_COUNT modelos disponibles"
else
    echo "⚠️ No se encontraron modelos"
fi

echo "🎯 Ollama listo para usar"

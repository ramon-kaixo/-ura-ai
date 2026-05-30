#!/bin/bash
# Script de auto-reparación para Tuneladora
# Soluciona problemas detectados (no solo parchea)

repair_ollama_leak() {
    echo "🔧 Reparando Ollama leak..."
    
    # Matar procesos de Ollama zombies
    pkill -9 ollama 2>/dev/null || true
    
    # Matar procesos de Python que están usando Ollama
    pkill -9 -f "ollama" 2>/dev/null || true
    
    # Reiniciar Ollama
    systemctl restart ollama 2>/dev/null || true
    
    # Esperar a que Ollama arranque
    sleep 5
    
    # Verificar que Ollama responde
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   ✅ Ollama reiniciado correctamente"
        return 0
    else
        echo "   ❌ Ollama no responde después de reiniciar"
        return 1
    fi
}

repair_zombies() {
    echo "🔧 Limpiando zombies..."
    
    # Contar zombies antes
    ZOMBIES_BEFORE=$(ps aux | awk '{print $8}' | grep -c Z || echo 0)
    
    # Intentar limpiar zombies matando sus padres
    for pid in $(ps aux | awk '$8 ~ /Z/ {print $3}'); do
        kill -9 "$pid" 2>/dev/null || true
    done
    
    sleep 2
    
    # Contar zombies después
    ZOMBIES_AFTER=$(ps aux | awk '{print $8}' | grep -c Z || echo 0)
    
    if [ $ZOMBIES_AFTER -lt $ZOMBIES_BEFORE ]; then
        echo "   ✅ Zombies limpiados: $((ZOMBIES_BEFORE - ZOMBIES_AFTER))"
        return 0
    else
        echo "   ⚠️  No se pudieron limpiar zombies"
        return 1
    fi
}

repair_memory_pressure() {
    echo "🔧 Aliviando presión de memoria..."
    
    # Limpiar caché de memoria
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
    
    # Matar procesos con alta memoria que no son críticos
    # (solo si RAM > 90%)
    RAM_PERCENT=$(free | awk 'NR==2{printf "%.0f", $3/$2*100}')
    if [ $RAM_PERCENT -gt 90 ]; then
        echo "   ⚠️  RAM crítica: ${RAM_PERCENT}%"
        # Matar procesos de Python no críticos
        pkill -9 -f "python.*test" 2>/dev/null || true
        pkill -9 -f "python.*debug" 2>/dev/null || true
    fi
    
    echo "   ✅ Memoria liberada"
    return 0
}

# Main
case "${1:-}" in
    ollama_leak)
        repair_ollama_leak
        ;;
    zombies)
        repair_zombies
        ;;
    memory)
        repair_memory_pressure
        ;;
    all)
        repair_ollama_leak
        repair_zombies
        repair_memory_pressure
        ;;
    *)
        echo "Uso: $0 {ollama_leak|zombies|memory|all}"
        exit 1
        ;;
esac

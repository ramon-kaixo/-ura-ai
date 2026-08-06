#!/bin/bash
# Detector de Entorno - Detecta si estamos en contenedor Docker o nativo
# Retorna: "container" o "native"

detect_environment() {
    # Detectar si estamos en Docker
    if [ -f /.dockerenv ]; then
        echo "container"
        return 0
    fi
    
    # Detectar si estamos en un contenedor por cgroup
    if grep -qE 'docker|lxc|kubepods' /proc/1/cgroup 2>/dev/null; then
        echo "container"
        return 0
    fi
    
    # Si no, estamos en entorno nativo
    echo "native"
    return 0
}

# Ejecutar detección
detect_environment

#!/bin/bash
# URA Environment Configuration - Fuente de verdad para rutas
# Detecta automáticamente la máquina y define URA_ROOT

set -euo pipefail

# Detectar máquina
detect_machine() {
    local machine
    if [[ "$(uname -s)" == "Darwin" ]]; then
        machine="mac"
    elif [[ "$(uname -m)" == "aarch64" ]]; then
        machine="gx10"
    else
        machine="linux"
    fi
    echo "$machine"
}

# Definir URA_ROOT según máquina
define_ura_root() {
    local machine
    machine=$(detect_machine)
    
    case "$machine" in
        mac)
            # Mac: directorio del repo
            URA_ROOT="${URA_ROOT:-/Users/ramonesnaola/URA/ura_ia_1972}"
            ;;
        gx10)
            # GX10: repo real
            URA_ROOT="${URA_ROOT:-$HOME/URA/ura_ia_1972}"
            ;;
        linux)
            # Linux genérico: usar HOME
            URA_ROOT="${URA_ROOT:-$HOME/URA}"
            ;;
        *)
            echo "ERROR: Máquina no reconocida: $machine" >&2
            exit 1
            ;;
    esac
    
    export URA_ROOT
}

# Definir subdirectorios comunes
define_subdirs() {
    export URA_AGENTS="$URA_ROOT/agents"
    export URA_SCRIPTS="$URA_ROOT/scripts"
    export URA_CONFIG="$URA_ROOT/config"
    export URA_DATA="$URA_ROOT/data"
    export URA_LOGS="$URA_ROOT/logs"
    export URA_TESTS="$URA_ROOT/tests"
    export URA_CORE="$URA_ROOT/core"
    export URA_DOCS="$URA_ROOT/docs"
    
    # Para tuneladora
    export URA_WORKSPACE="$URA_ROOT/workspace"
    export URA_ZONA_TRABAJO="$URA_ROOT/zona_trabajo"
    export URA_BACKUPS="$URA_ROOT/backups"
    export URA_CUARENTENA="$URA_ROOT/cuarentena"
}

# Inicializar entorno
init_ura_env() {
    define_ura_root
    define_subdirs
    
    # Verificar que URA_ROOT existe
    if [[ ! -d "$URA_ROOT" ]]; then
        echo "ERROR: URA_ROOT no existe: $URA_ROOT" >&2
        exit 1
    fi
    
    # Crear subdirectorios si no existen
    for dir in "$URA_DATA" "$URA_LOGS" "$URA_BACKUPS" "$URA_CUARENTENA"; do
        mkdir -p "$dir" 2>/dev/null || true
    done
}

# Ejecutar inicialización si se llama directamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    init_ura_env
    echo "URA_ROOT=$URA_ROOT"
    echo "URA_AGENTS=$URA_AGENTS"
    echo "URA_SCRIPTS=$URA_SCRIPTS"
    echo "URA_CONFIG=$URA_CONFIG"
    echo "URA_DATA=$URA_DATA"
    echo "URA_LOGS=$URA_LOGS"
fi

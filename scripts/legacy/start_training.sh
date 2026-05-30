#!/bin/bash
# Script lanzador para entrenamiento N3 con OpenClaw VM
# Ejecuta el pipeline de entrenamiento masivo

set -e

PROJECT_PATH="/Users/ramonesnaola/URA/ura_ia_1972"
TOSHIBA_PATH="/Volumes/TOSHIBA_NUEVO/URA_entrenamiento"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Verificar Toshiba
check_toshiba() {
    log_info "Verificando disco Toshiba..."
    if [ ! -d "$TOSHIBA_PATH" ]; then
        log_error "Disco Toshiba no encontrado en $TOSHIBA_PATH"
        log_info "Por favor, conecta el disco Toshiba e intenta de nuevo."
        exit 1
    fi
    log_info "Toshiba encontrado: $TOSHIBA_PATH"
}

# Verificar VM
check_vm() {
    log_info "Verificando conexión con VM OpenClaw..."
    if curl -s --max-time 5 http://192.168.64.100:5000/health > /dev/null 2>&1; then
        log_info "VM OpenClaw respondiendo correctamente"
        return 0
    else
        log_warn "VM OpenClaw no responde en http://192.168.64.100:5000"
        log_info "Asegúrate de que la VM está iniciada"
        return 1
    fi
}

# Instalar dependencias
install_dependencies() {
    log_info "Verificando dependencias Python..."
    cd "$PROJECT_PATH"

    if [ -f "requirements_n3.txt" ]; then
        pip3 install -r requirements_n3.txt
        log_info "Dependencias instaladas"
    else
        log_warn "No se encontró requirements_n3.txt"
    fi
}

# Cargar semillas manuales
load_seeds() {
    log_info "Cargando semillas manuales..."

    if [ -f "config/seeds_manuales.txt" ]; then
        cp config/seeds_manuales.txt "$TOSHIBA_PATH/seeds.txt"
        log_info "Semillas manuales cargadas"
    else
        log_warn "No se encontró config/seeds_manuales.txt"
    fi
}

# Ejecutar entrenamiento
run_training() {
    log_info "Iniciando entrenamiento N3..."
    log_info "Esto puede tardar varias horas..."
    log_info "Puedes dejar esto corriendo mientras duermes"
    echo ""

    cd "$PROJECT_PATH"

    # Ejecutar training_orchestrator
    python3 -m core.training_orchestrator --max 500 --concurrency 8

    if [ $? -eq 0 ]; then
        log_info "Entrenamiento completado exitosamente"
    else
        log_error "Entrenamiento falló con error"
        exit 1
    fi
}

# Mostrar resultados
show_results() {
    log_info "Resultados guardados en: $TOSHIBA_PATH/respuestas/"
    log_info "Informes guardados en: $TOSHIBA_PATH/reports/"

    response_count=$(find "$TOSHIBA_PATH/respuestas" -name "*.json" 2>/dev/null | wc -l)
    log_info "Total de respuestas generadas: $response_count"
}

# Main
main() {
    log_info "=========================================="
    log_info "Iniciando entrenamiento N3"
    log_info "=========================================="
    echo ""

    check_toshiba

    # VM check es opcional - permite continuar aunque VM no responda
    if ! check_vm; then
        log_warn "Continuando sin verificación de VM..."
    fi

    install_dependencies
    load_seeds
    run_training
    show_results

    echo ""
    log_info "=========================================="
    log_info "Entrenamiento N3 finalizado"
    log_info "=========================================="
}

main

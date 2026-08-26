#!/usr/bin/env bash
# run_all_tests.sh — Ejecuta todas las categorias de tests de URA
# Ejecutar: ./scripts/pro/run_all_tests.sh [categoria]
# Categorias: all, unit, infra, redes, servicios, seguridad, integracion, smoke

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CATEGORIA="${1:-all}"
ERRORS=0

log() { echo "[$(date '+%H:%M:%S')] $*"; }

run_pytest() {
    local desc="$1"
    shift
    log "Ejecutando: $desc"
    if python3 -m pytest "$@" --tb=line -q 2>&1; then
        log "OK: $desc"
    else
        log "FAIL: $desc"
        ERRORS=$((ERRORS + 1))
    fi
}

detect_machine() {
    local HOSTNAME
    HOSTNAME=$(hostname 2>/dev/null || echo "unknown")
    case "$HOSTNAME" in
        *gx10*|*asus*|*gb10*) echo "gx10" ;;
        *) echo "mac" ;;
    esac
}

MACHINE=$(detect_machine)
log "Maquina detectada: $MACHINE"

case "$CATEGORIA" in
    unit)
        run_pytest "Unit tests" tests/unit/ motor/tests/ -x --timeout=60
        ;;
    infra)
        run_pytest "Infra tests" tests/infra/ -m "gx10 or anywhere" --timeout=30
        ;;
    redes)
        run_pytest "Red tests" tests/redes/ -m "gx10 or anywhere" --timeout=30
        ;;
    servicios)
        run_pytest "Service tests" tests/servicios/ -m "gx10 or anywhere" --timeout=30
        ;;
    seguridad)
        run_pytest "Security tests" tests/seguridad/ -m "gx10 or anywhere" --timeout=60
        ;;
    integracion)
        run_pytest "Integration tests" tests/integracion/ -m "gx10 or anywhere" --timeout=30
        ;;
    smoke)
        log "Ejecutando smoke tests..."
        bash "$REPO_ROOT/scripts/pro/smoke_test.sh" || ERRORS=$((ERRORS + 1))
        ;;
    all)
        run_pytest "Infra tests" tests/infra/ -m "gx10 or anywhere" --timeout=30
        run_pytest "Red tests" tests/redes/ -m "gx10 or anywhere" --timeout=30
        run_pytest "Service tests" tests/servicios/ -m "gx10 or anywhere" --timeout=30
        run_pytest "Security tests" tests/seguridad/ -m "gx10 or anywhere" --timeout=60
        run_pytest "Integration tests" tests/integracion/ -m "gx10 or anywhere" --timeout=30
        log "Ejecutando smoke script..."
        bash "$REPO_ROOT/scripts/pro/smoke_test.sh" || ERRORS=$((ERRORS + 1))
        log "Ejecutando drift check..."
        bash "$REPO_ROOT/scripts/pro/test_drift.sh" || ERRORS=$((ERRORS + 1))
        ;;
    *)
        echo "Uso: $0 [all|unit|infra|redes|servicios|seguridad|integracion|smoke]"
        exit 1
        ;;
esac

echo ""
if [[ $ERRORS -eq 0 ]]; then
    log "TODAS LAS PRUEBAS PASARON"
else
    log "$ERRORS PRUEBAS FALLARON"
fi
exit $ERRORS

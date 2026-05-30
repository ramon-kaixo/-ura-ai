#!/usr/bin/env bash
# URA N2 Search Infrastructure Installer (Fase 1 — sin Docker)
#
# Crea entornos de datos, instala dependencias Python asíncronas y el navegador
# Chromium de Playwright. No requiere Docker ni SearXNG (Fase 1 usa DDG).
#
# Uso:
#   bash scripts/install_search_infra.sh          # instalar
#   bash scripts/install_search_infra.sh --check  # verificar estado
#   bash scripts/install_search_infra.sh --uninstall  # limpiar ~/.ura/n2
#
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "${SCRIPT_DIR}/.." && pwd )"
VENV_DIR="${PROJECT_DIR}/.venv"
URA_DATA="${HOME}/.ura"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${BLUE}[N2]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*" >&2; }

check_env() {
    log "Verificando entorno..."
    if [[ ! -d "${VENV_DIR}" ]]; then
        err "No se encuentra el venv en ${VENV_DIR}"
        exit 1
    fi
    ok "venv OK: ${VENV_DIR}"

    if ! command -v python3 >/dev/null 2>&1; then
        err "python3 no está disponible en PATH"
        exit 1
    fi
    ok "python3 OK"
}

install_python_deps() {
    log "Instalando dependencias Python asíncronas..."
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    python -m pip install --upgrade pip >/dev/null
    python -m pip install \
        aiohttp \
        aiosqlite \
        playwright \
        pytest-asyncio \
        duckduckgo-search \
        'sentence-transformers>=2,<6' \
        beautifulsoup4
    ok "Dependencias Python instaladas"
}

install_playwright_browsers() {
    log "Instalando Chromium para Playwright..."
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    python -m playwright install chromium
    ok "Chromium listo"
}

create_data_dirs() {
    log "Preparando árbol de datos ~/.ura/..."
    mkdir -p \
        "${URA_DATA}/maletas" \
        "${URA_DATA}/logs_n2" \
        "${URA_DATA}/cache"
    touch "${URA_DATA}/logs_n2/.keep" \
          "${URA_DATA}/maletas/.keep" \
          "${URA_DATA}/cache/.keep"
    ok "Directorios creados en ${URA_DATA}"
}

create_config_dirs() {
    log "Preparando config/maletas/..."
    mkdir -p "${PROJECT_DIR}/config/maletas"
    ok "config/maletas/ listo"
}

run_smoke_test() {
    log "Test rápido de import N2..."
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    python - <<'PY'
from core.ura_search_cache import get_search_cache
from core.ura_maleta_manager import get_maleta_manager
from core.ura_ddg_client import get_ddg_client
from core.ura_stealth_browser import random_user_agent
from core.ura_swarm_local import get_swarm
print("OK N2 imports")
PY
    ok "Smoke test correcto"
}

check_mode() {
    log "=== Estado actual N2 ==="
    echo "  URA_DATA:       ${URA_DATA}"
    echo "  venv:           ${VENV_DIR}"
    ls -la "${URA_DATA}" 2>/dev/null || echo "  (no existe ~/.ura aún)"
    # shellcheck disable=SC1091
    if [[ -d "${VENV_DIR}" ]]; then
        source "${VENV_DIR}/bin/activate"
        python - <<'PY' || true
import importlib, sys
mods = ["aiohttp","aiosqlite","playwright","duckduckgo_search","sentence_transformers","pytest_asyncio"]
for m in mods:
    try:
        importlib.import_module(m); print(f"  [OK]  {m}")
    except ImportError:
        print(f"  [MISS] {m}")
PY
    fi
}

uninstall_mode() {
    warn "Se eliminará ${URA_DATA}/logs_n2, ${URA_DATA}/cache y ${URA_DATA}/maletas (si están vacíos)"
    read -p "¿Confirmas? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Cancelado"
        exit 0
    fi
    rm -rf "${URA_DATA}/logs_n2" "${URA_DATA}/cache"
    # Only remove maletas if user-created is empty (keep config/maletas/ in repo)
    rmdir "${URA_DATA}/maletas" 2>/dev/null || warn "~/.ura/maletas tiene archivos; no se elimina"
    ok "Datos N2 de usuario limpiados"
}

main() {
    case "${1:-}" in
        --check)
            check_mode
            ;;
        --uninstall)
            uninstall_mode
            ;;
        *)
            check_env
            install_python_deps
            install_playwright_browsers
            create_data_dirs
            create_config_dirs
            run_smoke_test
            log "✅ Infraestructura N2 (Fase 1) instalada. No requiere Docker."
            ;;
    esac
}

main "$@"

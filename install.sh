#!/usr/bin/env bash
# URA — Install script
# Usage: bash install.sh
# Must be idempotent.

set -euo pipefail

URA_VERSION="${URA_VERSION:-0.13.0}"
INSTALL_DIR="${URA_INSTALL_DIR:-$HOME/ura}"
CREATE_VENV="${URA_CREATE_VENV:-true}"

echo "URA Installer v${URA_VERSION}"
echo "========================"

# 1. Check Python
echo "[1/5] Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
elif command -v python &>/dev/null; then
    PYTHON=$(command -v python)
else
    echo "ERROR: Python 3.8+ is required."
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+')
echo "  Found Python ${PYTHON_VERSION} at ${PYTHON}"

# 2. Check pip
echo "[2/5] Checking pip..."
if ! $PYTHON -m pip --version &>/dev/null; then
    echo "ERROR: pip is required."
    exit 1
fi
echo "  pip available"

# 3. Create installation directory
echo "[3/5] Setting up ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

# 4. Create virtual environment (optional)
if [ "${CREATE_VENV}" = "true" ]; then
    VENV_DIR="${INSTALL_DIR}/.venv"
    if [ ! -d "${VENV_DIR}" ]; then
        echo "  Creating virtual environment..."
        $PYTHON -m venv "${VENV_DIR}"
    fi
    PIP="${VENV_DIR}/bin/pip"
    echo "  Virtual environment: ${VENV_DIR}"
else
    PIP="$PYTHON -m pip"
fi

# 5. Install dependencies
echo "[4/5] Installing dependencies..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    $PIP install --quiet -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null || true
fi
$PIP install --quiet uvicorn httpx pyyaml fastapi pydantic 2>/dev/null || true
$PIP install --quiet -e "${SCRIPT_DIR}" 2>/dev/null || true
echo "  Dependencies installed"

# 6. Generate .env if not exists
echo "[5/5] Validating installation..."
ENV_FILE="${INSTALL_DIR}/.env"
if [ ! -f "${ENV_FILE}" ] && [ -f "${SCRIPT_DIR}/.env.example" ]; then
    cp "${SCRIPT_DIR}/.env.example" "${ENV_FILE}"
    echo "  Created ${ENV_FILE} — edit it to match your setup"
fi

echo ""
echo "URA installed in ${INSTALL_DIR}"
echo "Run: cd ${INSTALL_DIR} && source .venv/bin/activate && ura --help"

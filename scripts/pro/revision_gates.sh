#!/usr/bin/env bash
set -euo pipefail

echo "==> Guardián de protocolo (verify_protocol.py)"
python3 scripts/pro/verify_protocol.py

echo "==> Ruff"
ruff check .

echo "==> Mypy (sin caché)"
mypy --no-incremental core motor shared

echo "==> Pytest"
pytest -q --tb=short

echo "==> Todos los gates pasaron"

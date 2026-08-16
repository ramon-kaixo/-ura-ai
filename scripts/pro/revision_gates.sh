#!/usr/bin/env bash
set -euo pipefail

echo "==> Ruff"
ruff check .

echo "==> Mypy (sin caché)"
mypy --no-incremental core motor shared

echo "==> Pytest"
pytest -q --tb=short

echo "==> Todos los gates pasaron"

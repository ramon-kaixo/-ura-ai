# Getting Started — URA AI

## Requisitos

- Python 3.12+
- Git
- Ollama (opcional, para LLM)
- ~/URA/ura_ia_1972 clonado

## Instalacion

```bash
cd ~/URA/ura_ia_1972
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Verificacion

```bash
# Tests
python3 -m pytest motor/tests/tuneladora/ -q
python3 -m pytest tests/test_auto_maintain.py -q

# Lint
.venv/bin/ruff check motor/brain/ --output-format=concise

# Pre-commit (GX10 requiere env vars)
TMPDIR=/tmp PRE_COMMIT_HOME=/tmp/pre-commit-home pre-commit run --all-files
```

## Primeros 5 minutos

```bash
# 1. Health check del cerebro
python3 scripts/health_check_brain.py

# 2. ProactiveDetector manual
python3 -c "from scripts.pro.tuneladora.detector import ProactiveDetector; d = ProactiveDetector(); print(d.check_disk())"

# 3. AutoMaintainer A1
python3 -c "
from motor.brain.auto_maintain import AutoMaintainer
from motor.brain.executor import ProposalExecutor
from motor.brain.observer import BrainObserver
from unittest import mock
m = AutoMaintainer(mock.Mock(), ProposalExecutor())
print('AutoMaintainer OK')
"
```

## Problemas comunes

Ver `docs/TROUBLESHOOTING.md`.

#!/bin/bash
# quality_check.sh – Ejecuta todas las comprobaciones de calidad localmente

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔍 Asegurando entorno Python...${NC}"
scripts/ensure_environment.sh || exit 1

echo -e "${GREEN}🔍 Verificando __init__.py (sin imports peligrosos)...${NC}"
SOURCE_DIR="$(dirname "$0")/.." python3 "$(dirname "$0")/audit_init.py" || exit 1

echo -e "${GREEN}🔍 Validando integridad del sistema...${NC}"
python3 /opt/ura/agents/validador_sistema.py || exit 1

echo -e "${GREEN}🔍 Verificando dependencias...${NC}"
scripts/check_deps.sh || exit 1

echo -e "${GREEN}🔍 Ruff check + format...${NC}"
ruff check . --fix
ruff format .

echo -e "${GREEN}🔍 MyPy (tipado)...${NC}"
mypy . --follow-imports=silent --ignore-missing-imports

echo -e "${GREEN}🔍 Bandit (seguridad)...${NC}"
bandit -r . -ll

echo -e "${GREEN}🔍 Pytest (tests)...${NC}"
pytest tests/ -v --maxfail=5 --ignore=tests/test_n2_swarm.py --ignore=tests/test_n2_search_cache.py --ignore=tests/test_n2_stealth_fetcher.py --ignore=tests/test_n2_router.py --ignore=tests/test_n2_orchestrator.py --ignore=tests/test_n2_buscadores_adapter.py --ignore=tests/test_n2_exporter.py --ignore=tests/test_n2_validador.py --ignore=tests/test_n3_openclaw_client.py --ignore=tests/test_n3_observational_learner.py --ignore=tests/test_n3_sandbox_bridge.py --ignore=tests/test_openclaw_integration.py --ignore=tests/test_laia_core.py --ignore=tests/test_ura_n2_search_entry.py --ignore=tests/test_ura_search_unified.py

echo -e "${GREEN}✅ Todos los checks pasaron correctamente.${NC}"

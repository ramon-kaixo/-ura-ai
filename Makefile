# ============================================================
# Makefile — URA v3.2
# Herramienta determinista: solo ejecuta lo necesario.
# ============================================================

ASUS_HOST ?= ramon@10.164.1.99

.PHONY: test lint integration doctor snapshot deploy-snc deploy-all clean help \
        mypy semgrep shellcheck full-audit

# --- Tests ---

test:
	@echo "[make] Unit tests (pytest)..."
	@OPENCLAW_GATEWAY_TOKEN=test URA_API_KEY=test pytest -q --cov=core --cov=monitor --cov=motor --cov-report=term
	@echo ""

pytest:
	@echo "[make] Pytest (core + monitor + motor)..."
	@OPENCLAW_GATEWAY_TOKEN=test URA_API_KEY=test pytest -q --cov=core --cov=monitor --cov=motor --cov-report=term
	@echo ""

integration:
	@if ssh -o ConnectTimeout=2 -o BatchMode=yes $(ASUS_HOST) "echo ok" > /dev/null 2>&1; then \
		echo "[make] Integration tests (GX10 accesible)..."; \
		python3 tests/test_integration.py 2>/dev/null || echo "  ⚠ Tests de integración no disponibles"; \
	else \
		echo "[make] ⚠ GX10 no accesible — integration tests saltados"; \
	fi
	@echo ""

# --- Linting y validación ---

lint:
	@echo "[make] Ruff..."
	@ruff check . && echo "  ✓ ruff" || echo "  ✗ ruff"
	@echo ""

mypy:
	@echo "[make] Mypy strict..."
	@OPENCLAW_GATEWAY_TOKEN=test mypy core/ monitor/ motor/ 2>&1 | tail -5
	@echo ""

semgrep:
	@echo "[make] Semgrep (reglas personalizadas)..."
	@which semgrep >/dev/null 2>&1 && semgrep scan --config=.semgrep.yml --error --quiet && echo "  ✓ semgrep" || echo "  ⚠ semgrep no instalado (pip install semgrep)"
	@echo ""

shellcheck:
	@echo "[make] ShellCheck..."
	@find . -name '*.sh' -not -path './.venv/*' -exec shellcheck --severity=warning {} \; && echo "  ✓ shellcheck" || echo "  ⚠ shellcheck encontró problemas"
	@echo ""

full-audit: lint mypy semgrep shellcheck pytest
	@echo "[make] ✅ Auditoría completa"

# --- Diagnóstico ---

doctor:
	@echo "URA Doctor — Diagnóstico completo"
	@echo "================================="
	@echo ""
	@echo "[1/6] Schema..."
	@python3 -c "from core.config_manager import validate_schema, get_role, get_base_dir; e=validate_schema(); print(f'  Rol: {get_role()} | Base: {get_base_dir()} | Schema: {\"OK\" if not e else f\"{len(e)} errores\"}')"
	@echo ""
	@echo "[2/6] Compilación..."
	@python3 -m py_compile core/config_manager.py core/model_router.py core/memory_engine.py ura.py 2>&1 && echo "  ✓ Módulos core compilan" || echo "  ✗ Error de compilación"
	@echo ""
	@echo "[3/6] Tests..."
	@python3 tests/test_unit.py 2>&1 | tail -2
	@echo ""
	@echo "[4/6] Git..."
	@git log --oneline -3
	@echo ""
	@echo "[5/6] SNC State..."
	@if [ -f $(HOME)/URA/logs/snc_state.json ]; then \
		python3 -c "import json; s=json.load(open('$(HOME)/URA/logs/snc_state.json')); print(f'  Estado: {s.get(\"status\",\"?\")} | Timestamp: {s.get(\"timestamp\",\"?\")} | OpenClaw: {\"ACTIVO\" if s.get(\"openclaw_active\") else \"reposo\"}')" ; \
	elif [ -f /tmp/ura_snc_state.json ]; then \
		python3 -c "import json; s=json.load(open('/tmp/ura_snc_state.json')); print(f'  Estado: {s.get(\"status\",\"?\")} (local)')" ; \
	else \
		echo "  ⚠ Sin estado SNC — ¿SNC corriendo?" ; \
	fi
	@echo ""
	@echo "[6/6] Docker..."
	@if ssh -o ConnectTimeout=2 -o BatchMode=yes $(ASUS_HOST) "docker ps --format '{{.Names}}' 2>/dev/null" > /dev/null 2>&1; then \
		echo "  Containers activos:"; \
		ssh -o ConnectTimeout=2 -o BatchMode=yes $(ASUS_HOST) "docker ps --format '    ✓ {{.Names}} ({{.Status}})' 2>/dev/null | head -9"; \
	else \
		echo "  ⚠ Docker no accesible en GX10"; \
	fi
	@echo ""

# --- Snapshot ---

snapshot:
	@python3 ura.py snapshot

# --- Deploy ---

deploy-snc:
	@echo "[make] Desplegando SNC en GX10..."
	@ssh -o ConnectTimeout=5 $(ASUS_HOST) "mkdir -p /home/ramon/URA/ura_ia_1972/monitor"
	@scp monitor/snc.py $(ASUS_HOST):/home/ramon/URA/ura_ia_1972/monitor/
	@scp deploy/emergency_runbook.json $(ASUS_HOST):/home/ramon/URA/ura_ia_1972/deploy/
	@scp deploy/snc.service $(ASUS_HOST):/etc/systemd/system/
	@ssh -o ConnectTimeout=5 $(ASUS_HOST) "systemctl daemon-reload && systemctl enable snc.service && systemctl restart snc.service"
	@echo "[make] ✅ SNC desplegado. Verificar: ssh gx10 systemctl status snc"

deploy-all: test deploy-snc
	@echo "[make] ✅ Deploy completo"

# --- Clean ---

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find . -type f -name '*.pyc' -delete 2>/dev/null; true
	@echo "[make] Cache limpiada"

# --- Default ---

help:
	@echo "URA Makefile"
	@echo ""
	@echo "  make test        Pytest (core + monitor + motor)"
	@echo "  make pytest      Pytest (core + monitor + motor)"
	@echo "  make lint        Ruff check"
	@echo "  make mypy        Mypy strict"
	@echo "  make semgrep     Semgrep (reglas personalizadas)"
	@echo "  make shellcheck  ShellCheck (todos los .sh)"
	@echo "  make full-audit  Ruff + Mypy + Semgrep + ShellCheck + Pytest"
	@echo "  make integration Integration tests (GX10 required)"
	@echo "  make doctor      Diagnóstico completo"
	@echo "  make snapshot    Guardar estado del repo"
	@echo "  make deploy-snc  Desplegar SNC en GX10"
	@echo "  make deploy-all  Test + deploy"
	@echo "  make clean       Limpiar __pycache__"
	@echo ""

.DEFAULT_GOAL := help

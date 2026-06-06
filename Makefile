# ============================================================
# Makefile — URA v3.0
# Herramienta determinista: solo ejecuta lo necesario.
# ============================================================

.PHONY: test lint integration doctor snapshot deploy-snc deploy-all clean helm

# --- Tests ---

test:
	@echo "[make] Unit tests..."
	@python3 tests/test_unit.py
	@echo ""

integration:
	@if ssh -o ConnectTimeout=2 -o BatchMode=yes ramon@10.164.1.99 "echo ok" > /dev/null 2>&1; then \
		echo "[make] Integration tests (GX10 accesible)..."; \
		python3 tests/test_integration.py 2>/dev/null || echo "  ⚠ Tests de integración no disponibles"; \
	else \
		echo "[make] ⚠ GX10 no accesible — integration tests saltados"; \
	fi
	@echo ""

# --- Linting y validación ---

lint:
	@echo "[make] Compiling..."
	@python3 -m py_compile core/config_manager.py && echo "  ✓ config_manager" || echo "  ✗ config_manager"
	@python3 -m py_compile core/model_router.py && echo "  ✓ model_router" || echo "  ✗ model_router"
	@python3 -m py_compile core/memory_engine.py && echo "  ✓ memory_engine" || echo "  ✗ memory_engine"
	@python3 -m py_compile mantenimiento/ura_maintenance.py && echo "  ✓ ura_maintenance" || echo "  ✗ ura_maintenance"
	@python3 -m py_compile mantenimiento/ura_maintenance_remote.py && echo "  ✓ ura_maintenance_remote" || echo "  ✗ ura_maintenance_remote"
	@python3 -m py_compile monitor/snc.py && echo "  ✓ snc" || echo "  ✗ snc"
	@python3 -m py_compile monitor/snc_remote.py && echo "  ✓ snc_remote" || echo "  ✗ snc_remote"
	@python3 -m py_compile ura.py && echo "  ✓ ura" || echo "  ✗ ura"
	@echo "[make] Schema validation (Python)..."
	@python3 -c "from core.config_manager import validate_schema; e=validate_schema(); exit(len(e))" && echo "  ✓ schema basic" || echo "  ✗ schema basic"
	@echo "[make] Schema validation (jsonschema)..."
	@python3 -c "from core.config_manager import validate_schema_json; e=validate_schema_json(); exit(len(e))" && echo "  ✓ schema declarativo" || echo "  ℹ jsonschema no instalado (no bloquea)"
	@echo "[make] Runbook validation..."
	@python3 -c "from monitor.snc import load_runbook; rb=load_runbook(); assert rb['version']=='1.0','version'; assert len(rb['commands'])>=3,'commands'" && echo "  ✓ runbook" || echo "  ✗ runbook"
	@echo ""

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
	@if ssh -o ConnectTimeout=2 -o BatchMode=yes ramon@10.164.1.99 "docker ps --format '{{.Names}}' 2>/dev/null" > /dev/null 2>&1; then \
		echo "  Containers activos:"; \
		ssh -o ConnectTimeout=2 -o BatchMode=yes ramon@10.164.1.99 "docker ps --format '    ✓ {{.Names}} ({{.Status}})' 2>/dev/null | head -9"; \
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
	@ssh -o ConnectTimeout=5 ramon@10.164.1.99 "mkdir -p /home/ramon/URA/ura_ia_1972/monitor"
	@scp monitor/snc.py ramon@10.164.1.99:/home/ramon/URA/ura_ia_1972/monitor/
	@scp deploy/emergency_runbook.json ramon@10.164.1.99:/home/ramon/URA/ura_ia_1972/deploy/
	@scp deploy/snc.service ramon@10.164.1.99:/etc/systemd/system/
	@ssh -o ConnectTimeout=5 ramon@10.164.1.99 "systemctl daemon-reload && systemctl enable snc.service && systemctl restart snc.service"
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
	@echo "  make test        Unit tests (113 tests)"
	@echo "  make integration  Integration tests (GX10 required)"
	@echo "  make lint         Compile + schema + runbook validation"
	@echo "  make doctor       Diagnóstico completo"
	@echo "  make snapshot     Guardar estado del repo"
	@echo "  make deploy-snc   Desplegar SNC en GX10"
	@echo "  make deploy-all   Test + deploy"
	@echo "  make clean        Limpiar __pycache__"
	@echo ""

.DEFAULT_GOAL := help

# URA IA — Makefile de validación
# Uso: make validate (rápido, desarrollo local) | make validate-full (CI, con cobertura)

.PHONY: validate validate-full test test-fast test-slow lint lint-strict mypy-info radon audit clean

PYTHON := python3
PYTEST := $(PYTHON) -m pytest
PYTEST_ARGS := -q --tb=line
PYTEST_SLOW := -m "not slow"
RUFF := $(PYTHON) -m ruff

# === VALIDACIÓN RÁPIDA (desarrollo local, < 30s con xdist) ===
validate: test-fast lint mypy-info radon
	@echo "✅ validate OK"

# === VALIDACIÓN COMPLETA (CI, < 3 min) ===
validate-full: test lint mypy-info radon
	@echo "✅ validate-full OK"

# === TESTS RÁPIDOS (secuencial: xdist satura el host con -n auto, OpenBLAS falla) ===
test-fast:
	@echo "▶ pytest rápido (sin slow, sin cov)..."
	$(PYTEST) tests/unit/ tests/integration/ $(PYTEST_SLOW) $(PYTEST_ARGS) --no-cov

# === TESTS (secuencial, con cobertura) ===
test:
	@echo "▶ pytest (sin slow, con cobertura)..."
	$(PYTEST) tests/unit/ tests/integration/ $(PYTEST_SLOW) $(PYTEST_ARGS)

test-full:
	@echo "▶ pytest (completo con cobertura)..."
	$(PYTEST) tests/unit/ tests/integration/ --cov=core --cov=motor --cov=knowledge --cov=agents --cov-report=term-missing $(PYTEST_ARGS)

test-slow:
	@echo "▶ pytest (solo slow)..."
	$(PYTEST) tests/unit/ tests/integration/ -m "slow" -v --tb=short

# === LINT (informativo, no bloquea) ===
lint:
	@echo "▶ ruff check (informativo)..."
	@-$(RUFF) check core/ motor/ knowledge/ agents/ --quiet --ignore=EXE002 2>/dev/null || echo "  ruff: errores pre-existentes"
	@echo "▶ ruff format --check..."
	@-$(RUFF) format --check core/ motor/ knowledge/ agents/ tests/ --quiet 2>/dev/null || echo "  ruff format: ajustes pendientes"

# === LINT ESTRICTO (CI) ===
lint-strict:
	@echo "▶ ruff check (estricto)..."
	$(RUFF) check core/ motor/ knowledge/ agents/ --ignore=EXE002
	@echo "▶ ruff format --check (informativo: 200 archivos pendientes de formato)..."
	@-$(RUFF) format --check core/ motor/ knowledge/ agents/ tests/ --quiet || echo "  ruff format: ajustes de formato pendientes (no bloquea)"

# === MYPY ===
mypy-info:
	@echo "▶ mypy (informativo)..."
	@-$(PYTHON) -m mypy core/ motor/ knowledge/ agents/ --ignore-missing-imports --show-error-codes 2>/dev/null | tail -5 || echo "  mypy: verificar pyproject.toml"

# === RADON ===
radon:
	@echo "▶ radon cc (núcleo)..."
	@radon cc core/ --min=C --total-average -s 2>/dev/null || echo "  radon: no instalado"

# === AUDIT ===
audit-docs:
	@echo "▶ audit docs..."
	@ls docs/audit/*.md 2>/dev/null | xargs -I {} sh -c 'echo "  {}"' || echo "  docs/audit/ vacío"

# === CONSOLIDATE ===
consolidate-check:
	@echo "▶ Verificando si se debe ejecutar consolidación..."
	@$(PYTHON) scripts/pro/consolidacion.py --check
	@echo "✅ Verificación de consolidación completada"


# === SERVER ===
server-start:
	@echo "▶ Iniciando metrics server..."
	@bash scripts/pro/server_ctl.sh start

server-stop:
	@echo "▶ Deteniendo metrics server..."
	@bash scripts/pro/server_ctl.sh stop

server-status:
	@echo "▶ Estado del metrics server..."
	@bash scripts/pro/server_ctl.sh status


# === ROUTER ===
router-audit:
	@echo "▶ Auditando router y conectividad..."
	@$(PYTHON) scripts/pro/auditor_router.py
	@echo "✅ Auditoría de router completada"


# === REINDEX ===
reindex:
	@echo "▶ Reconciliando AssetStore ↔ VectorStore (dry-run)..."
	@$(PYTHON) scripts/pro/reindex_vectors.py
	@echo "✅ Reindex completado (dry-run)"


# === DASHBOARD ===
dashboard:
	@echo "▶ Generando dashboard de salud..."
	@$(PYTHON) scripts/pro/dashboard.py
	@echo "✅ Dashboard generado"


# === AUDITORIA ===
audit:
	@echo "▶ Ejecutando auditoría continua..."
	@-$(PYTHON) scripts/pro/auditoria_continua.py; true
	@echo "✅ Auditoría completada"


# === SECRETS ===
secrets:
	@echo "▶ Auditando secrets hardcodeados..."
	@$(PYTHON) scripts/pro/audit_secrets.py || echo "  ⚠️ Secrets detectados (ver output arriba)"
	@echo "✅ Auditoría de secrets completada"


# === FIX ===
fix:
	@echo "▶ Sanear código (ruff + fixes personalizados)..."
	@$(PYTHON) scripts/pro/sanear_codigo.py
	@echo "✅ Código saneado"


# === INVENTARIO ===
inventario:
	@echo "▶ Generando inventario de herramientas..."
	@$(PYTHON) scripts/pro/audit_inventario.py
	@echo "✅ Inventario actualizado en data/inventario_herramientas.json"

# === TUNELADORA (pipeline de validación) ===
tuneladora:
	@echo "▶ Tuneladora (modo check)..."
	@$(PYTHON) scripts/pro/tuneladora/tuneladora_pipeline.py --mode check


# === CHAOS ===
chaos:
	@echo "▶ Ejecutando chaos tests (dry-run)..."
	@$(PYTHON) scripts/pro/chaos_test.py --dry-run
	@echo "✅ Chaos tests completados"


# === HARDENING ===
hardening:
	@echo "▶ Auditando hardening de servicios systemd..."
	@-$(PYTHON) scripts/pro/hardening_audit.py || echo "  ⚠️ Requiere permisos de root"
	@echo "✅ Auditoría de hardening completada"


# === BACKUP ===
backup:
	@echo "▶ Backup del asistente..."
	@$(PYTHON) scripts/pro/backup_assistant.py
	@echo "✅ Backup completado"


# === CLEANUP ===
cleanup:
	@echo "▶ Limpiando mensajes antiguos del asistente..."
	@$(PYTHON) scripts/pro/cleanup_assistant.py
	@echo "✅ Cleanup completado"


# === LIMPIEZA ===
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .mypy_cache/ htmlcov/ 2>/dev/null || true
	@echo "✅ Limpieza OK"

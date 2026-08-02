# URA IA — Makefile de validación
# Uso: make validate (rápido, desarrollo local) | make validate-full (CI, con cobertura)

.PHONY: validate validate-full test test-slow lint lint-strict mypy-info radon audit clean

PYTHON := python3
PYTEST := $(PYTHON) -m pytest
PYTEST_ARGS := -q --tb=line
PYTEST_SLOW := -m "not slow"

# === VALIDACIÓN RÁPIDA (desarrollo local, < 3 min) ===
validate: test lint mypy-info radon
	@echo "✅ validate OK"

# === VALIDACIÓN COMPLETA (CI, < 5 min) ===
validate-full: test-full lint mypy-info radon
	@echo "✅ validate-full OK"

# === TESTS ===
test:
	@echo "▶ pytest (sin slow)..."
	$(PYTEST) tests/unit/ tests/integration/ $(PYTEST_SLOW) $(PYTEST_ARGS)

test-full:
	@echo "▶ pytest (completo con cobertura)..."
	$(PYTEST) tests/unit/ tests/integration/ --cov=core --cov=motor --cov=knowledge --cov=agents --cov-report=term-missing $(PYTEST_ARGS)

test-slow:
	@echo "▶ pytest (solo slow)..."
	$(PYTEST) tests/unit/ tests/integration/ -m "slow" -v --tb=short

# === LINT (informativo, no bloquea — desarrollo local) ===
lint:
	@echo "▶ ruff check (informativo)..."
	@-ruff check core/ motor/ knowledge/ agents/ --quiet --ignore=EXE002 2>/dev/null || echo "  ruff: errores pre-existentes (no bloquean)"
	@echo "▶ ruff format --check..."
	@-ruff format --check core/ motor/ knowledge/ agents/ tests/ --quiet 2>/dev/null || echo "  ruff format: ajustes pendientes"

# === LINT ESTRICTO (CI — bloquea) ===
lint-strict:
	@echo "▶ ruff check (estricto)..."
	ruff check core/ motor/ knowledge/ agents/ --ignore=EXE002
	@echo "▶ ruff format --check..."
	ruff format --check core/ motor/ knowledge/ agents/ tests/

# === MYPY INFORMATIVO (no bloqueante) ===
mypy-info:
	@echo "▶ mypy (informativo)..."
	@-$(PYTHON) -m mypy core/ motor/ knowledge/ agents/ --ignore-missing-imports --show-error-codes 2>/dev/null | tail -5 || echo "  mypy: verificar pyproject.toml"

# === COMPLEJIDAD CICLOMÁTICA ===
radon:
	@echo "▶ radon cc (núcleo)..."
	@$(PYTHON) -m radon cc core/ --min=C --total-average -s 2>/dev/null || echo "  radon: no instalado (pip install radon)"

# === AUDIT ===
audit:
	@echo "▶ audit docs..."
	@ls docs/audit/*.md 2>/dev/null | xargs -I {} sh -c 'echo "  {}"' || echo "  docs/audit/ vacío"

# === LIMPIEZA ===
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .mypy_cache/ htmlcov/ 2>/dev/null || true
	@echo "✅ Limpieza OK"

# URA IA — Makefile de validación
# Uso: make validate (rápido, desarrollo local) | make validate-full (CI, con cobertura)

.PHONY: validate validate-full test test-fast test-slow lint lint-strict mypy-info radon audit clean security dead-code

PYTHON := .venv/bin/python
PYTEST := $(PYTHON) -m pytest
PYTEST_ARGS := -q --tb=line
PYTEST_SLOW := -m "not slow"
RUFF := $(PYTHON) -m ruff

# === VALIDACIÓN RÁPIDA (desarrollo local, < 30s con xdist) ===
validate: test-fast lint mypy-info radon verify-hooks test-udo
	@echo "✅ validate OK"

# === VALIDACIÓN COMPLETA (CI parity: tests + lint + security, < 5 min) ===
validate-full: test lint mypy-info radon security test-udo
	@echo "✅ validate-full OK"

# === TESTS UDO (F5 N2: integrados en validate — bash autónomo, sin pytest) ===
test-udo:
	@echo "▶ tests UDO (udo + engineering)..."
	bash tests/udo/test_udo.sh
	bash tests/engineering/test_engineering.sh

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

# === SNAPSHOT (Fase 3 Plan de Testing) ===
test-snapshot:
	@echo "▶ pytest (snapshots estables)..."
	$(PYTEST) tests/snapshot/ $(PYTEST_ARGS)

# === LOAD TESTING (Fase 4 Plan de Testing, locust) ===
test-load:
	@echo "▶ locust (100 usuarios, 60s)..."
	@echo "  Requiere ura-api activo (puerto 8000)"
	/home/ramon/URA/ura_ia_1972/.venv/bin/locust -f tests/load/locustfile.py --host=http://localhost:8000 -u 100 -r 10 -t 60s --headless

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
	@echo "▶ Ejecutando auditoría paralela..."
	@-$(PYTHON) scripts/pro/auditoria_paralela.py || echo "  auditoría paralela: ${'$'}? checks fallaron"
	@echo "✅ Auditorías completadas"


# === SECRETS ===
secrets:
	@echo "▶ Auditando secrets hardcodeados..."
	@$(PYTHON) scripts/pro/audit_secrets.py || echo "  ⚠️ Secrets detectados (ver output arriba)"
	@echo "✅ Auditoría de secrets completada"


# === ADUANA LOCAL (paridad con job security del CI, < 1 min, rootfs RO-safe) ===
security:
	@echo "▶ ADUANA LOCAL — SAST/SCA (parity CI job security)..."
	@echo "  [1/4] audit_secrets (hardcodeados, fail si críticos)..."
	@$(PYTHON) scripts/pro/audit_secrets.py --fail-critical
	@echo "  [2/4] audit_git_secrets (historial git, fail si hallazgos)..."
	@$(PYTHON) scripts/pro/audit_git_secrets.py --fail --max-commits 300
	@echo "  [3/4] pip-audit (SCA requirements.txt, fail si CVEs)..."
	@XDG_CACHE_HOME=/tmp/opencode/xdg-cache $(PYTHON) -m pip_audit -r requirements.txt --progress-spinner off
	@echo "  [4/4] semgrep (reglas .semgrep.yml, caches a /tmp)..."
	@XDG_CACHE_HOME=/tmp/opencode/xdg-cache SEMGREP_SETTINGS_FILE=/tmp/opencode/semgrep-settings.yml SEMGREP_LOG_FILE=/tmp/opencode/semgrep.log .venv/bin/semgrep --config=.semgrep.yml --quiet core/ motor/ knowledge/
	@echo "✅ ADUANA LOCAL OK (0 hallazgos)"


# === BANDIT SAST (paridad hook pre-commit, informativo) ===
security-bandit:
	@echo "▶ bandit (SAST motor/, skips B404/B603/B110 - 0 shell=True verificado, except:pass auditado)..."
	@-$(PYTHON) -m bandit -q -x "*/tests/*" --skip B311,B108,B101,B404,B603,B110 -r motor/ || echo "  bandit: hallazgos (revisar) o no instalado"
# === CÓDIGO HUÉRFANO (plan 4.1: vulture, informativo) ===
dead-code:
	@echo "▶ vulture (código muerto, min-confidence 70)..."
	@-$(PYTHON) -m vulture core/ motor/ knowledge/ --min-confidence 70 || true
	@echo "✅ dead-code completado (revisar output; alta confianza = borrable tras verificación)"


# === FIX ===
fix:
	@echo "▶ Sanear código (ruff + fixes personalizados)..."
	@$(PYTHON) scripts/pro/sanear_codigo.py
	@echo "✅ Código saneado"



# === TESTING AVANZADO (Plan de Testing v2.0) ===
test-random:
	@echo "▶ pytest con orden aleatorio (randomly)..."
	$(PYTEST) tests/unit/ $(PYTEST_SLOW) $(PYTEST_ARGS) -p no:cacheprovider

test-deadfixtures:
	@echo "▶ Fixtures muertas..."
	@-$(PYTEST) tests/unit/ --dead-fixtures -q -p no:cacheprovider 2>/dev/null || echo "  deadfixtures: no hay o error"

complexity:
	@echo "▶ Complejidad ciclomática (radon + xenon)..."
	@.venv/bin/python -m radon cc core/ motor/ knowledge/ --average | tail -3
	@echo "▶ xenon (umbral B absoluto / A módulos)..."
	@-.venv/bin/python -m xenon --max-absolute B --max-modules A --max-average A core/ motor/ knowledge/ || echo "  xenon: supera umbral — refactorizar funciones complejas"

test-suite: test-random test-deadfixtures complexity
	@echo "✅ test-suite completado"
# === HOOKS ===
install-hooks:
	@echo "▶ Instalando hooks..."
	@bash scripts/pro/hooks/install-hooks.sh

verify-hooks:
	@echo "▶ Verificando hooks..."
	@test -x .git/hooks/post-commit && echo "✅ post-commit instalado" || (echo "❌ post-commit NO instalado — ejecuta make install-hooks"; exit 1)

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

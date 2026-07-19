# Plan de Saneamiento Total

**Objetivo:** Cero fisuras. Reproducible, portable, documentado, automatizado.

---

## Fase 0 — Requisitos (2h)

**Dependencia de todo lo demás.** Sin esto, nada es instalable.

### 0.1 Separar requirements.txt en capas

| Archivo | Contenido | Tamaño estimado |
|---------|-----------|-----------------|
| `requirements/base.txt` | Core: pydantic, httpx, pytest, ruff… | ~30 líneas |
| `requirements/gpu.txt` | `-r base.txt` + torch, nvidia, vllm, cuda | ~15 líneas |
| `requirements/mac.txt` | `-r base.txt` + pyobjc, coreaudio… | ~5 líneas |
| `requirements/dev.txt` | `-r base.txt` + pre-commit, mypy, bandit… | ~15 líneas |
| `requirements.txt` | `-r requirements/dev.txt` (legacy compat) | 1 línea |

### 0.2 pyproject.toml dinámico

```toml
[project.optional-dependencies]
gpu = ["torch", "vllm", ...]
mac = ["pyobjc", ...]
dev = ["pytest", "ruff", ...]
```

### 0.3 Verificar instalación limpia

```bash
docker run --rm -v .:/app python:3.12-slim bash -c "
  pip install -r /app/requirements/base.txt
  python -c 'from motor.core.config import UraConfig; print(\"OK\")'
"
```

**Criterio de éxito:** `pip install .` funciona en Ubuntu, macOS, Debian slim, sin errores.

---

## Fase 1 — CI/CD (4h)

### 1.1 GitHub Actions: matriz de compatibilidad

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest -q
```

### 1.2 Pipeline completo

| Step | Comando | Falla si… |
|------|---------|-----------|
| Lint | `ruff check .` | 1 error |
| Format | `ruff format --check .` | 1 archivo sin formatear |
| Type check | `mypy motor/platform/` | 1 error nuevo (solo plataforma) |
| Test | `pytest -q --no-cov` | 1 test fallido |
| Security | `bandit -r motor/ -ll` | 1 issue HIGH |
| Install | `pip install -e .` | error de instalación |

### 1.3 Pre-commit checks (ya existen, solo asegurar que CI los ejecuta igual)

**Criterio de éxito:** `git push` → GitHub ejecuta los checks → sale verde.

---

## Fase 2 — Repo Limpio (3h)

### 2.1 Eliminar data de ejecución del repo

| Patrón | Tamaño estimado | Acción |
|--------|-----------------|--------|
| `knowledge/knowledge.db` | ~1MB | `git rm --cached`, añadir a `.gitignore` |
| `knowledge/interacciones/*.json` | ~100KB | `git rm --cached` |
| `motor/data/snapshots/*.json` | ~10MB (100+ archivos) | `git rm --cached`, son preflight temporales |
| `coverage.xml` | ~500KB | Ya en `.gitignore`? Verificar |
| `logs/` | variable | Ya en `.gitignore`? Verificar |
| `*.pyc`, `__pycache__/` | variable | Verificar `.gitignore` |

### 2.2 .gitignore definitivo

```gitignore
# Data
knowledge/knowledge.db
knowledge/interacciones/
motor/data/snapshots/
motor/data/benchmarks/
coverage.xml
htmlcov/

# Python
__pycache__/
*.pyc
*.egg-info/
dist/
build/

# Env
.venv/
.env

# IDE
.vscode/
.idea/

# Logs
logs/
*.log
```

### 2.3 Resolver colisión case-insensitive

```bash
# Eliminar el que sobre (ARCHITECTURE.md es duplicado de architecture.md)
git rm docs/ARCHITECTURE.md
```

**Criterio de éxito:** `git clone` en macOS → 0 warnings, repo <100MB.

---

## Fase 3 — Scripts Huérfanos (3h)

### 3.1 Auditoría de scripts/pro/

```bash
# Listar scripts no referenciados por ningún otro archivo
for f in scripts/pro/*.py; do
  name=$(basename $f .py)
  if ! grep -qr "$name" --include="*.py" --include="*.sh" --include="*.md" . | grep -v "$f"; then
    echo "HUERFANO: $f"
  fi
done
```

### 3.2 Archivar en .nervioso/ los huérfanos

```
scripts/pro/.nervioso/descarte/
  ├── experimento_1.py
  ├── experimento_2.py
  └── README.md  # Fecha de archivado, SHA original
```

### 3.3 Los que se quedan: añadir docstring con propósito

```python
# scripts/pro/tuneladora_master.py
"""Pipeline de mejora continua URA. Timer systemd cada 6h.
Dependencias: tuneladora_mantenimiento.py, tuneladora_mejora.py
Uso: python3 scripts/pro/tuneladora_master.py [--dry-run]
"""
```

**Criterio de éxito:** `scripts/pro/` de 146 → ~80 scripts, cada uno documentado y referenciado.

---

## Fase 4 — Cobertura de Tests (8h)

### 4.1 Prioridad P1 (4h)

| Módulo | Líneas | Tests a escribir | Objetivo cobertura |
|--------|--------|------------------|--------------------|
| `motor/core/qdrant_client.py` | 597 | QA client, collection ops, vectores | 40% |
| `motor/core/llm/router.py` | 535 | Ruteo, fallback, timeout, cache | 50% |
| `motor/memory/memory.py` | 280 | CRUD, recover, snapshot cycle | 60% |
| `motor/platform/tracing.py` | 894 | (ya tiene tests → 80% real, falta medir) | — |

### 4.2 Prioridad P2 (4h)

| Módulo | Líneas | Tests a escribir |
|--------|--------|------------------|
| `motor/agents/runner.py` | 281 | Ejecución de tools, errores |
| `motor/agents/scheduler.py` | 223 | FIFO, aging, graceful shutdown |
| `motor/events/bus.py` | 133 | Pub/sub, tópicos, async |
| `motor/plugin/registry_v2.py` | 391 | Registro, versionado, carga |

### 4.3 Métrica objetivo

```bash
pytest --cov=motor --cov-report=term-missing --cov-fail-under=30
```

**Criterio de éxito:** Cobertura `motor/` ≥ 30% (hoy: ~0.7%).

---

## Fase 5 — Release Process (3h)

### 5.1 GitHub Actions: publish.yml

```yaml
on:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: pip install build
      - run: python -m build
      - uses: actions/upload-artifact@v4
        with:
          path: dist/
```

### 5.2 CHANGELOG.md

Formato Keep a Changelog:
```markdown
# Changelog

## v0.29.0 (2026-07-19)
### Added
- CircuitBreaker + Backpressure (F29 B5)
- Health probes, metrics, logging estructurado (F29 B1)
- 101 tests de cobertura

### Fixed
- F14-F02: MultiAgentRuntime.cancel() workflow_id opcional
- F14-F03: EpisodeStore auto-recreate SQLite corrupta
- F14-F05: HybridRetriever fallback graceful
- 2356 lint errors → 0
```

### 5.3 Release checklist (ya existe en AGENTS.md, formalizar)

**Criterio de éxito:** `git tag v0.30.0 && git push --tags` → GitHub publica release automáticamente.

---

## Fase 6 — Documentación (4h)

### 6.1 QUICKSTART funcional

```markdown
# Quickstart
## Prerrequisitos
- Python 3.11+
- pip

## Instalación
pip install ura  # o: pip install -e ".[dev]"

## Uso básico
from motor.memory import Memory
m = Memory()
m.append({"type": "test", "data": "hello"})
print(m.state_at())

## Ejecutar tests
pytest -q
```

### 6.2 README.md actualizado

Estructura:
```markdown
# URA — Multi-Agent Platform
## Quickstart (3 líneas)
## Arquitectura (diagrama + link a docs/architecture/)
## Roadmap
## Contribuir
```

### 6.3 Generar API docs con pydoc o mkdocs

```bash
pip install mkdocs mkdocstrings
mkdocs serve  # Sirve en :8000
```

**Criterio de éxito:** Una persona nueva puede leer QUICKSTART y tener el sistema funcionando en <10 minutos.

---

## Resumen de Esfuerzo

| Fase | Descripción | Esfuerzo | Depende de |
|------|-------------|----------|------------|
| **0** | Requisitos | 2h | — |
| **1** | CI/CD | 4h | Fase 0 |
| **2** | Repo limpio | 3h | — |
| **3** | Scripts huérfanos | 3h | — |
| **4** | Cobertura tests | 8h | Fase 0 |
| **5** | Release process | 3h | Fase 1 |
| **6** | Documentación | 4h | Fase 2, 3 |
| **Total** | | **27h** | |

## Orden Recomendado de Ejecución

```
Fase 0 (reqs) → Fase 1 (CI) → Fase 2 (repo limpio) → Fase 5 (release)
                               → Fase 3 (scripts) → Fase 6 (docs)
                                                    → Fase 4 (tests, paralelo a docs)
```

**Nota:** Fase 2 y 3 pueden ir en paralelo con Fase 1. Fase 4 y 6 pueden ir en paralelo entre sí.

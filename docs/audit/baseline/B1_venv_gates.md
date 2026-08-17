# BLOQUE B1 — Regeneración de .venv y gates (TASK-20260817-015) — 2026-08-17

**Objetivo P1-03**: restaurar instrumentación de calidad tras la eliminación de `.venv` en F4.

## Creación del entorno

- `python3 -m venv .venv` → OK (Python 3.12.3, pip del venv).
- Instalación: `requirements/base.txt` + `requirements/dev.txt` (+ `pytest-rerunfailures` añadido a dev.txt,
  ya que `addopts = --reruns 2` de pyproject.toml lo exige y NO estaba declarado — laguna de la
  instrumentación corregida).
- `gpu.txt` NO instalado (torch no necesario para gates del protocolo; el sistema ya lo tiene).

## Herramientas verificadas (.venv/bin)

| Herramienta | Versión | Estado |
|-------------|---------|--------|
| python | 3.12.3 | ✅ |
| pip | (venv) | ✅ |
| ruff | 0.16.3 | ✅ (ver gate) |
| mypy | 2.3.1 | ✅ |
| pytest | 9.1.1 | ✅ (7 passed) |
| bandit | 1.9.4 | ✅ |
| coverage / safety / mkdocs / pre-commit | presentes | ✅ |

## Gates

| Gate | Resultado | Nota |
|------|-----------|------|
| `ruff check .` | **300 errores** — 270 `CPY001 missing-copyright-notice` + 30 `PLR0917 too-many-positional-arguments` | Reglas nuevas activas en ruff 0.16.3; el baseline del proyecto (0 errores, commit 8ba50ca) se alineó con versión anterior. **No es regresión de código**. Decisión requerida: añadir `CPY`/`PLR0917` a ignores de pyproject o fijar versión de ruff. |
| `pytest tests/unit/test_protocol_coordination.py` | ✅ **7 passed** (1.39s) | Con pytest 9.1.1 + rerunfailures |

## Hallazgos del bloque

- **B1-H1 (decisión)**: ruff 0.16.3 reporta 300 errores (CPY001×270, PLR0917×30). Proposición: ignorar
  `CPY` (el proyecto nunca exigió copyright notices) y revisar los 30 PLR0917 puntualmente o ignorar.
  Alternativa: pin `ruff==<versión anterior>` en dev.txt (perpetúa versión vieja).
- **B1-H2 (resuelto)**: `pytest-rerunfailures` faltaba en dev.txt pese a estar en addopts → añadido.

## Estado

- TERM: ejecución completada, entregada a revisión (TASK-015 en_revision).
- Pendiente decisión Ramón: resolución de B1-H1 antes de cerrar el gate ruff.
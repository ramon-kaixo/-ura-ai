# Herramientas de diagnóstico instaladas 2026-08-30 — estado y decisión

**Fecha detección:** 2026-09-08 (agente Build)
**Motivo:** aparecieron en el venv de GX10 sin estar en requirements del proyecto.

## Instaladas (en .venv, NO en requirements/pyproject/CI)
- black 26.5.1, flake8 7.3.0, pylint 4.0.8, isort 9.0.1, sphinx 9.1.0 (+astroid, mccabe, dill, objgraph/gprof/undill, docutils...)
- ollama 0.6.2 (cliente python — esta SÍ es útil para el proyecto)

## Análisis
- El proyecto ya usa **ruff** (lint+format ALL rules) y **mypy** como estándar de calidad.
- pylint/flake8/black/isort **duplican** funciones de ruff → si se integran, crearían doble estándar y ruido.
- sphinx no se usa (la doc es MkDocs).
- **Nada en core/motor/knowledge/scripts las importa.** No están en Makefile ni CI.

## Decisión (pendiente de Ramón)
- [ ] Opción A: desinstalar del venv (pip uninstall) — limpio pero irreversible sin reinstalar
- [ ] Opción B: documentar como tooling personal (estado actual) — no molesta
- [ ] Opción C: integrar alguna con propósito real (p.ej. sphinx si se quisiera doc API)

**Recomendación del agente Build:** Opción B (dejarlas, ya documentadas). El estándar del proyecto es ruff+mypy+pytest; añadir pylint/flake8/black fragmentaría la calidad.

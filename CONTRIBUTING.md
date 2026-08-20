# Contributing — URA

Guía para contribuir al repositorio URA. Reglas operativas completas en
`AGENTS.md` (Metodología Universal de Ingeniería, reglas UDO, seguridad).

## Entorno

- Python 3.11+ (CI corre 3.11/3.12/3.13).
- Lint/format: `ruff check .` y `ruff format --check .`.
- Tests: `pytest -q` (necesita hypothesis, pytest-asyncio, pytest-timeout).
- Typecheck: `mypy --no-incremental core motor shared`.

## Gates obligatorios (antes de commitear)

```bash
ruff check .
mypy --no-incremental core motor shared
pytest -q --tb=short
python3 scripts/pro/audit_secrets.py --fail-critical
```

## Cobertura (política RAMON 2026-08-13)

- Todo código nuevo DEBE tener cobertura ≥85% POR MÓDULO (gate escalonado
  Fase 5; meta 100x100).
- Medición: `pytest` + `coverage` con `--source` relativo al módulo. Para
  scripts/pro usar rcfile propio sin el `omit = scripts/*` del .coveragrc.
- Verificación: `python3 scripts/pro/verificador_cobertura.py <módulo>`.
- Excepción: scripts bash (verificación por smoke manual documentada).

## Convenciones

- Ficheros nuevos: kebab-case. Directorios: kebab-case.
- Fechas: ISO 8601 (YYYY-MM-DD).
- Ruff con todas las reglas. Type hints obligatorios en funciones nuevas.
- Docstrings estilo Google.
- Prefijos de fábricas: `build_*` (infra), `create_*` (servicios), `get_*` (lazy).
- NUNCA `shell=True` en subprocess. Sin secretos hardcodeados (usar
  `motor/core/secrets.py` o env).

## Protocolo de commits

- Formato: `tipo(scope): [TASK-YYYYMMDD-NNN][WEB|TERM] descripción`.
- Los commits llevan TASK-ID del expediente UDO (`docs/udo/tasks/`).
- No commitear a `main` directo salvo hotfix de seguridad (auditado).

## Revisión (ejecutor-revisor)

- Ejecutor crea rama `ia/TASK-XXXX` desde `main`, commits con el formato.
- Revisor (independiente) ejecuta gates y emite veredicto:
  `APROBADO` / `CAMBIOS_SOLICITADOS` / `PENDIENTE`.
- Solo tras `APROBADO` se fusiona a `main`.

## Tests

- No dividir tests de cobertura largos sin mantener conteo exacto (ADR-038).
- Fixtures compartidas viven en `_<nombre>_helpers.py` con re-exports
  `# noqa: F401` (el `--fix` de ruff las borra).
- Fixtures-parametro en tests → `# noqa: F811` (patrón legítimo).
# Closeout Plan Maestro URA IA v3.1 — Validación y Cobertura

**Fecha:** 2026-08-02
**Duración:** Sprint continuo (sesiones 2026-08-01/02)
**Objetivo:** Consolidar validación (make validate), inventariar herramientas,
corregir shadowing M1 y llevar cobertura de core/ a >=40%.

## Resumen de Fases

| Fase | Objetivo | Resultado | Estado |
|------|----------|-----------|--------|
| 0 | Consolidación validación | `make validate` (rápido) + `validate-full` (CI con cobertura); SKIPPED.md (40 justificados); WARNINGS.md (6 documentados); flaky `test_100_exitos` aislado | ✅ |
| 1 | Reconocimiento | `scripts/pro/audit_inventario.py` (324 archivos, 4 zonas → JSON); INVENTARIO_HERRAMIENTAS.md; MYPY_BASELINE.md (core 87 / motor 238); SYSTEMD_TIMERS.md (8 timers ura); CANDIDATOS_BASURA.md (19 .bak, 14 movidos a .attic/) | ✅ |
| 2 | Shadowing M1 | `core/model_router/__init__.py`: singletons `metrics`/`vram_guard` re-exportados como `metrics_singleton`/`vram_guard_singleton` — `import core.model_router.metrics` vuelve a devolver el módulo | ✅ |
| 3 | Cobertura core/ >=40% | 38.8% → **51.1%** (29 tests nuevos: infraestructura mochila 100%: _state, adapter, helpers, interfaces, routes health/breaker/metrics) | ✅ |
| 4 | Integración | Hook mypy informativo no bloqueante en pre-commit (ejecuta mypy real, remite a MYPY_BASELINE.md, nunca falla) | ✅ |
| 5 | Cierre | Este closeout + AGENTS.md actualizado | ✅ |

## Incidente Crítico Resuelto (2026-08-02 08:04 UTC)

**Pérdida de trabajo por test destructivo:**
`tests/integration/test_tuneladora_cleanup_integration.py` ejecutaba
`BackupPlugin.backup_code()` → `git stash push` sobre el **repo real**,
revirtiendo cualquier cambio sin commitear (destruyó Makefile editado y
6 marks @slow). Corregido con:

1. **Fix tests** (138b799): fixture `backup` usa repo temporal (`tmp_path` + `git init` + commit inicial) + WARNING en cabecera
2. **Guardia** (bd996c7): `backup_code()` lanza `RuntimeError("Working tree dirty — commit or stash manually before backup")` antes de tocar git
3. **Work perdido recuperado**: Makefile validate (eaf3951) + @slow marks (73d485a, 05e223c)

## Métricas

| Métrica | Antes | Después |
|---------|-------|---------|
| Cobertura core/ | 38.8% | **51.1%** |
| make validate | no existía | ✅ pasa (2689 tests, CC>=20: 0) |
| CC>=20 núcleo productivo | 0 (S5c) | 0 (verificado en validate) |
| Módulos mochila 0% | ~15 | 0 (todos >25%, 11 a 100%) |
| mypy hook pre-commit | falso (`exit 0` con echo) | real + informativo + baseline doc |
| Tests suite (not slow) | ~2670 | 2700+ |

## Baseline de Referencia

- Cobertura: `data/baseline/coverage_post_s5b.json`
- Mypy: `docs/audit/MYPY_BASELINE.md` (core 87 errores / motor 238)
- Complejidad: S5c (0 funciones CC>=20 en núcleo productivo)
- Inventario: `data/inventario_herramientas.json`

## Regla de No Regresión (Plan Maestro)

- `make validate` debe pasar (tests sin slow + lint informativo + mypy-info + radon)
- `validate-full` en CI con `--cov-fail-under` acorde al baseline (51% core)
- Ninguna fase degrada cobertura por debajo del baseline sin documentarlo
- Ningún test de integración ejecuta git sobre el repo real (regla documentada
  en cabecera de test_tuneladora_cleanup_integration.py)

## Commits Clave

| Commit | Contenido |
|--------|-----------|
| 138b799 | fix(tests): repo temporal para BackupPlugin |
| bd996c7 | fix(backup): guardia working tree sucio |
| eaf3951 | feat(make): validate/validate-full |
| 73d485a / 05e223c | test(slow): benchmarks F25 + infra mochila |
| 9d3c4a6 / 4f717b0 | fix(model_router): shadowing M1 + test vram_guard |
| ae0af0f / d7a87e1 | feat(audit): inventario + JSON + docs (incl. mypy baseline) |
| 913f25e | ci(pre-commit): mypy informativo no bloqueante |

# Release Checklist — Knowledge Engine

## Pre-release
- [ ] `SCHEMA_VERSION` actualizado en `migrations.py`
- [ ] `ENGINE_VERSION` actualizado en `migrations.py`
- [ ] Migración SQL creada en `schemas/migrations/`
- [ ] Migration registrada en `MIGRATIONS` dict
- [ ] `storage_verifier.py` actualizado con nuevas tablas
- [ ] `CHANGELOG.md` actualizado

## Validación
- [ ] `ruff check knowledge/engine/`
- [ ] `ruff format --check knowledge/engine/`
- [ ] `bandit -r knowledge/engine/ -q`
- [ ] Tests unitarios: `pytest tests/ -q --tb=short`
- [ ] Golden master: `pytest tests/::TestGoldenMaster -q`
- [ ] Property tests: `pytest tests/::TestProperty -q`
- [ ] Tests de estrés: `python3 /tmp/stress_5_scenarios.py`
- [ ] Tests de resiliencia: `python3 /tmp/test_resiliencia.py`
- [ ] Tests cross-process: `python3 /tmp/test_cross_process.py`

## Comandos de operación
- [ ] `ke init` — DB limpia
- [ ] `ke compile --source-dir ...` — compilación
- [ ] `ke doctor` — health check (0 errors)
- [ ] `ke audit-db` — invariantes (0 errors)
- [ ] `ke search ...` — búsqueda funcional
- [ ] `ke archive source --source-dir ... --archive-dir ...` — archive
- [ ] `ke archive verify ... --archive-dir ...` — verificación
- [ ] `ke archive restore ... --dest ... --archive-dir ...` — restore
- [ ] `ke status` — estadísticas
- [ ] `ke job-process` — procesar cola

## Post-release
- [ ] Coverage report generado
- [ ] Benchmark guardado en `docs/benchmarks/`
- [ ] ADRs actualizados si aplica
- [ ] Tag git + release notes

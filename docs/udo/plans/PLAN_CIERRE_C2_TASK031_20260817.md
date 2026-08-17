# PLAN v2 — Cierre administrativo del Bloque C2 (TASK-20260817-031) y hallazgos

- **Fecha**: 2026-08-18 (v2 tras investigación del WEB; v1: 2026-08-17)
- **Autor**: [WEB] OpenCode Web (ASUS)
- **Origen**: petición RAMON — "modifica el plan, mete todas las mejoras, las cosas sin hacer y los errores, lo ejecutas y mandas informe" (2026-08-18)
- **Contexto**: v1 quedó con defectos detectados en la investigación (D1-D5, M1-M6). Este plan v2 los incorpora TODOS y es el plan que se ejecuta.

## Correcciones de la investigación (v1 → v2)

| ID | Defecto detectado | Corrección en v2 |
|----|-------------------|------------------|
| D1 | Check 1 usaba `git diff 61a30ca6 --stat` (working tree → 4 files, falso) | → `git show 61a30ca6 --stat \| tail -1` (55 files, 182+/128-) |
| D2 | Check 7 ambiguo ("si aplica") | → OBLIGATORIO: expediente .md + `commits:` en coordination.json |
| D3 | Gate UDO nunca cumplido: `commits:` vacío, sin expediente .md | → crear expediente `docs/udo/tasks/TASK-20260817-031.md` (formato TASK-019) + registrar SHA 61a30ca6 en coordination.json |
| D4 | Contradicción AUTO-REVISIÓN vs veredicto ajeno | → la tarea se registra en `docs/udo/review-pending.md` (v1.1: cierre sin gates del revisor = AUTO-REVISIÓN; revisión en bloque posterior) + humano valida con este informe |
| D5 | Solo gates estáticos, sin verificación funcional | → smoke funcional: pytest de los módulos con cambio de comportamiento (lista abajo) |
| M1 | — | Limpieza RUF100 en 4 archivos tocados (ruff --fix selectivo) |
| M2 | — | Smoke funcional (D5) con tests existentes |
| M3 | — | Prueba real del hook pre-commit antes/después (`pre-commit run ruff --files`) |
| M4 | — | RUF100 global (120) → se documenta como SUGERENCIA de TASK dedicada (fuera de alcance) |
| M5 | — | Cómo se commiteó 61a30ca6 con hook activo → NO VERIFICABLE; se documenta |
| M6 | — | Destino de rama 031 → sugerencia al humano (no se borra sin autorización) |

## Estado real verificado (HECHO, con evidencia)

| Hecho | Evidencia |
|-------|-----------|
| Commit `61a30ca6`: 55 files, 182+/128- | `git show 61a30ca6 --stat \| tail -1` |
| Merge `6eebf4f4`, cierre `44c9b8ce` (coordination.json → aprobada, veredicto APROBADO) | `git log --oneline -5` |
| Rama `ia/TASK-20260817-031` en origin (61a30ca6) | `git ls-remote --heads origin` |
| main == origin/main (44c9b8ce) | `git rev-parse HEAD origin/main` |
| mypy gate 87→0 | `.venv/bin/mypy --no-incremental core motor shared ... \| wc -l` → 0 |
| verify_protocol OK (25 tareas) | `python3 scripts/pro/verify_protocol.py` |
| RUF100: 4 en 3 archivos (handlers.py:181, context.py:77, engine.py:85/104) | `ruff --select RUF100 <3 archivos>` → Found 4 |
| RUF100 GLOBAL: 120 (30 noqa PLR0917 muertos) | `ruff --select RUF100 .` → Found 120 |
| NO existe expediente 031 (.md); ura-udo verify → "tarea no encontrada" | `bash scripts/pro/ura-udo verify TASK-20260817-031` |
| coordination.json TASK-031: `commits:` ausente | python json |
| 2 archivos ajenos modificados (pendientes-fase.md, diagnostico/__init__.py) | `git status --short` |
| coordination.json reservada por TASK-008 (REVIEW) — escritura con AUTORIZACIÓN EXPRESA del humano (2026-08-18) | `ura-udo check` |
| smoke imports OK (mochila_engine en RAÍZ, no core/mochila/) | `.venv/bin/python -c "import mochila_engine; ..."` |

## Objetivo

Cerrar administrativamente el Bloque C2 (TASK-031) con trazabilidad UDO COMPLETA y verificación funcional de los cambios de comportamiento:
1. Verificar la integración (contenido commit, sincronización main/origin).
2. Crear expediente TASK-031.md + registrar SHA en coordination.json (gate UDO real).
3. Limpiar RUF100 (4 noqa muertos) en los 3 archivos tocados.
4. Smoke funcional: pytest de módulos con cambio de comportamiento.
5. Probar el hook pre-commit (M3) y documentar cómo se commiteó 61a30ca6 (M5, NO VERIFICABLE).
6. Registrar AUTO-REVISIÓN en review-pending.md (D4).
7. Informe final con separación HECHO/DECLARADO.

## Cambios de comportamiento a verificar (smoke)

| Módulo | Cambio | Test a ejecutar |
|--------|--------|-----------------|
| `core/logs/guardian_logger.py` | Eliminada 2ª definición de `_save_to_qdrant` (publish de alertas ahora SÍ se emite) | test_guardian_acciones.py |
| `mochila_engine.py` (raíz) | `fin()`: assert → if/return defensivo | test_mochila.py |
| `core/debate/debate_engine.py` | `_resultado_seguro` devuelve dict | test_debate_engine.py |
| `motor/agents/agent.py` | audit con AuditEvent (contrato ABC) | test_agents_*.py (unit) |
| `motor/assistant/api/handlers.py`, `routes.py` | str() en payloads | test_motor_assistant_handlers.py |
| `motor/core/qdrant_client.py` | acepta IConfigProvider; import desde motor.core.config | test_qdrant_client.py, test_motor_qdrant_client.py |
| `motor/core/fusion/engine.py` | noqa PLR0917 | test_motor_fusion_config_urls.py |
| `motor/scanner/*`, `sliding_window.py` | dicts tipados | test_motor_scanner_scanner.py, test_motor_sliding_weather_vector.py |
| `knowledge/engine/rules.py`, `memory_store.py`, `asset_store.py` | cast/object | test_rules_*.py, test_knowledge_snapshot_store.py |

## MÍNIMOS OBLIGATORIOS (sin esto no se declara terminado)

- [ ] `git show 61a30ca6 --stat | tail -1` → 55 files, 182+, 128-
- [ ] `.venv/bin/ruff check .` → All checks passed (0 errores)
- [ ] `.venv/bin/ruff check --select RUF100 <3 archivos>` → 0 (tras limpieza)
- [ ] mypy gate → 0
- [ ] `python3 scripts/pro/verify_protocol.py` → OK
- [ ] Smoke funcional: pytest de módulos listados → 0 fallos nuevos (solo se excluye test_heartbeat, pre-existente documentado)
- [ ] `pre-commit run ruff --files <3 archivos>` → pasa (o documenta fallo del entorno)
- [ ] Expediente `docs/udo/tasks/TASK-20260817-031.md` creado (formato estándar: estado, commits, gates, hallazgos)
- [ ] coordination.json: `commits: ["61a30ca6"]` registrado (con flock + AUTORIZACIÓN EXPRESA auditada)
- [ ] review-pending.md: TASK-031 registrada (AUTO-REVISIÓN)
- [ ] Commits con formato `tipo(scope): [TASK-20260817-031][WEB] desc`
- [ ] Informe final entregado (QUÉ SE HIZO / QUEDA / SUGERENCIAS)

## PUNTOS CRÍTICOS / INVARIANTES

- NO tocar los 2 archivos ajenos (`docs/udo/pendientes-fase.md`, `motor/diagnostico/__init__.py`)
- NO reescribir historia (no amend/rebase sobre 61a30ca6/44c9b8ce)
- NO borrar la rama ia/TASK-20260817-031 (decisión del humano; sugerencia M6)
- Escritura en coordination.json SIEMPRE con flock (colisión detector TERM)
- Commits directos en main (tarea ya mergeada/aprobada; limpieza administrativa autorizada por el humano — se documenta en el informe como desviación justificada del flujo rama→merge)
- `git add` SELECTIVO (nunca `git add .` — hay archivos ajenos en el working tree)

## NO HACER

- No corregir `test_heartbeat.py::test_error_instancia_inexistente` (pre-existente; solo documentar)
- No ejecutar pytest completo (2+ h); solo smoke funcional definido
- No modificar el plan de modelos ni coordinación de otros agentes
- No limpiar los 120 RUF100 globales (fuera de alcance → sugerencia M4 de TASK dedicada)

## VALIDACIÓN (comandos)

1. `git show 61a30ca6 --stat | tail -1` → 55 files, 182 insertions, 128 deletions
2. `.venv/bin/ruff check .` → All checks passed
3. `.venv/bin/ruff check --select RUF100 motor/assistant/api/handlers.py motor/assistant/context.py motor/core/fusion/engine.py` → 0
4. `.venv/bin/mypy --no-incremental core motor shared 2>&1 | grep -E 'arg-type|assignment|return-value|union-attr|attr-defined' | grep -v tests/ | wc -l` → 0
5. `python3 scripts/pro/verify_protocol.py` → OK
6. Smoke: `pytest -q --tb=short <tests de la tabla>` → 0 fallos nuevos
7. `pre-commit run ruff --files <3 archivos>` → exit 0
8. `bash scripts/pro/ura-udo verify TASK-20260817-031` → gate de integridad (tras crear expediente + commits)
9. `git log --oneline -4` → SHAs esperados

## CRITERIOS DE CIERRE

- Los 9 checks de validación pasan (o fallo documentado con causa y responsable)
- Expediente TASK-031 existe con: estado, commits, gates, hallazgos (test_heartbeat pre-existente, guardian_logger bug corregido, RUF100 global, gate UDO incompleto del cierre ajeno)
- coordination.json con `commits:` y nota de AUTORIZACIÓN EXPRESA
- review-pending.md actualizado
- Informe final entregado con separación HECHO/DECLARADO
- Veredicto del humano recibido (el informe ES el vehículo de validación)

## ANÁLISIS DEL PLAN v2

- **Puntos buenos**: incorpora TODAS las correcciones de la investigación (D1-D5, M1-M6); verificación funcional real (no solo estática); gate UDO completo; sin ampliar alcance (RUF100 global y rama 031 quedan como sugerencias).
- **Riesgos residuales**: (1) coordinación con el detector TERM en coordination.json → mitigado con flock; (2) la limpieza RUF100 toca archivos con noqa pre-existentes → riesgo bajo (directivas muertas verificadas); (3) el hook pre-commit puede fallar por entorno (rootfs/caché) → se documenta, no se bloquea.
- **Veredicto**: **GO** (autorizado por el humano el 2026-08-18).

## CORRECCIÓN EN EJECUCIÓN (2026-08-18, descubrimiento D6)

Durante la ejecución se descubrió que **el check 3 del plan (RUF100 → 0) era INCORRECTO**:

- Evidencia: `pyproject.toml` tiene `select = ["ALL"]` → **PLR0917 está ACTIVA** y los `# noqa: PLR0917` son NECESARIOS.
- `ruff check --select RUF100` los marca como muertos ("non-enabled") — **falso positivo de RUF100 con select ALL** (no expande ALL al evaluar directivas).
- Verificación: sin los noqa, `ruff check .` → 4 errores PLR0917; con los noqa, `All checks passed!`.
- **Acción tomada**: limpieza de 4 noqa REVERTIDA (`git checkout` de los 3 archivos). Código en HEAD sin cambios del cierre administrativo.
- **Gate sustituido**: check 3 pasa de "RUF100=0" a "ruff check . = All checks passed" (0 errores) — ya verificado.
- **Acción futura (sugerencia M4-M5)**: TASK dedicada para el hook: excluir RUF100 del check del hook pre-commit (o revisar versión de ruff) — el hook bloquea falsamente commits que tocan archivos con noqa PLR0917 válidos (evidencia: 61a30ca6 requirió bypass).

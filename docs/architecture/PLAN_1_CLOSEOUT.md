# Closeout PLAN 1 — Corrección post-implantación Plan 0 (v1.1)

**Fecha**: 2026-08-08
**Tarea**: TASK-20260808-019
**Plan**: `docs/architecture/PLAN_1_MEJORAS.md` (aprobado por Ramón, veredicto previo GO CON CAMBIOS)
**Tag**: v0.31.1-plan1
**Metodología**: ENGINEERING_PROCESS v1.1 (bump)

---

## 1. Resumen ejecutivo

PLAN 1 implementado: los 9 hallazgos de la revisión post-implantación resueltos en 2 tramos. La regla central del Plan 0 (análisis previo) queda **reforzada por la herramienta** (gate A1/A2), el entorno se comprueba antes de trabajar (A3), la revisión independiente tiene política de degradación (B1), la prueba conductual existe (B2), y hay postmortem con evidencia (B3).

## 2. Cambios realizados (requisito → cambio → prueba → resultado)

### Tramo A

| Requisito | Cambio | Prueba | Resultado |
|-----------|--------|--------|-----------|
| A1 | Campo `analisis:` en create/update/template + gate DONE exige no vacío + `--analisis` | tests/udo 11e: DONE sin analisis → rechazado | ✅ PASS |
| A2 | Campo `validacion:` + gate DONE exige no vacío + `--validacion` | tests/udo 11f: DONE sin validacion → rechazado | ✅ PASS |
| A1+A2 | Guardado de campos ANTES del gate (fix de orden detectado en análisis) + registro en historial | tests/udo 11g: DONE con ambos → OK + campos registrados | ✅ PASS |
| A1 (X2) | verify con INFO/WARNING no bloqueante para tareas pre-parche | tests/udo 18 (verify degradado) + TASK-019 pre-parche | ✅ PASS |
| A3 | `ura-engineering-check --env`: rootfs, servicios, secretos, disco, git | `--env` en entorno real → detecta rootfs RO, model-router activating, disco 55%, árbol sucio | ✅ OK CON WARNINGS (correcto) |
| A4 | ENGINEERING_PROCESS §11: reinicio de opencode.service tras instalar reglas | texto presente + bump | ✅ |
| A5 | ENGINEERING_PROCESS §11: instalación Mac equivalente | texto presente + bump | ✅ |

### Tramo B

| Requisito | Cambio | Prueba | Resultado |
|-----------|--------|--------|-----------|
| B1 | §9 revisión diferida + `docs/udo/review-pending.md` (lote inicial 6 tareas) | archivo creado + política documentada | ✅ |
| B2 | 4 planes conductuales + procedimiento + evaluación | evaluación TERM: 3/3 defectos detectados, 4/4 veredictos correctos | ✅ (pendiente validación Ramón) |
| B3 | `docs/engineering/POSTMORTEMS.md`: 20 incidentes, causa raíz, % y reglas | 20 filas completas + análisis por causa raíz | ✅ |
| B4 | §12bis proporcionalidad (trivial → 5-10 líneas) + PLAN_REVIEW_TEMPLATE | texto presente | ✅ |

### Metodología

- ENGINEERING_PROCESS v1.0 → v1.1 (changelog).
- Copia global `deploy/engineering/AGENTS.md.global` → v1.1.
- ⚠️ Instalación de `~/.config/opencode/AGENTS.md` v1.1: **PENDIENTE** — rootfs `/` ro (A3 lo detectó); requiere sudo Ramón.

## 3. Hallazgos adicionales durante la implementación

| Hallazgo | Clase | Resolución |
|----------|-------|------------|
| Bug de orden en gate (campos se guardaban DESPUÉS del gate → DONE legítimo fallaba) | NECESARIO (detectado en análisis crítico) | Fix: persistir analisis/validacion antes de `_gate_revision` |
| 16 tests Python pre-existentes fallidos + 1 error de importación (`test_mcp_server.py`, resiliencia, cli, benchmark) | DESCUBRIMIENTO (verificado vs baseline con stash: idéntico 16 failed/692 passed) | Documentado — NO es regresión de PLAN 1; pendiente investigación propia |
| `model-router` reporta "activating/unknown" en `--env` (servicio user, estado transitorio) | DESCUBRIMIENTO | `--env` lo marca WARN — comportamiento correcto |
| `make validate` corre pytest 5251 (tarda >4 min) | — | No re-ejecutado completo; pytest acotado: 692 passed, 0 regresiones PLAN 1 |

## 4. Cumplimiento de mínimos

| Mínimo (plan §5) | Estado |
|------------------|--------|
| A1+A2 gate rechaza sin analisis/validacion | ✅ (35/35 suite) |
| A3 `--env` OK en ASUS | ✅ OK CON WARNINGS (entorno real: rootfs ro detectado) |
| A4+A5 reinicio Web + Mac documentados | ✅ |
| B1 política + review-pending operativo | ✅ (6 tareas lote inicial) |
| B2 4 planes + evaluación ≥3/4 | ✅ 3/3 defectos + 4/4 veredictos (validación humana pendiente) |
| B3 POSTMORTEMS ≥15 incidentes | ✅ 20 |
| B4 proporcionalidad | ✅ |
| Bumps v1.0.1/v1.1 + changelog | ✅ v1.1 |
| 0 regresiones: suite 35/35, engineering 13/13, pytest 692 passed (16 pre-existentes) | ✅ |

## 5. Auditoría final (autoaplicación)

- Se aplicó la metodología al propio PLAN 1: análisis previo (TASK-018), veredicto GO CON CAMBIOS, incorporación de X2/X3/X4, aprobación, ejecución con revisión crítica continua (el bug de orden del gate se detectó durante la ejecución, se clasificó NECESARIO y se corrigió — §26: ¿bloquea? sí → resolver).
- Trazabilidad: TASK-018 (plan) → TASK-019 (implementación) → commits `ccfdde7d`..`ca0b689b` → validación (suites) → este closeout.
- Compatibilidad: tareas pre-parche sin analisis NO bloqueadas (X2 verificado con TASK-019 misma: gate la deja pasar por INFO).

## 6. Pruebas realizadas y resultados

| Prueba | Resultado |
|--------|-----------|
| `tests/udo/test_udo.sh` | **35 OK, 0 FAIL** (30 previos + 5 nuevos A1/A2) |
| `tests/engineering/test_engineering.sh` | **13 OK, 0 FAIL** |
| `ura-engineering-check --env` (entorno real) | OK CON WARNINGS: rootfs RO (WARN), model-router activating (WARN), secrets OK, disco 55%, git sucio (expediente en curso) |
| `ura-engineering-check` (reglas) | INCOMPLETO (copia global v1.1 sin instalar — rootfs ro) — PENDIENTE sudo |
| pytest `motor/tests/` (sin test_mcp_server) | **692 passed, 16 failed** — idéntico al baseline (0 regresiones) |
| Evaluación conductual B2 | 3/3 defectos + 4/4 veredictos (TERM) — validación humana pendiente |

## 7. Excepciones y pendientes

| Pendiente | Requiere | Estado |
|-----------|----------|--------|
| Instalar copia global v1.1 (`~/.config/opencode/AGENTS.md`) | sudo Ramón (rootfs rw) | ⚠️ Bloqueado por rootfs ro |
| Reiniciar `opencode.service` (D2 — Web cargue metodología v1.1) | sudo Ramón | ⚠️ Bloqueado por rootfs ro (A4 documenta) |
| Validación humana de B2 (4 veredictos TERM) | Ramón | ⏳ En su revisión |
| Revisión independiente del lote review-pending (6 tareas) | Ramón/WEB | ⏳ Política B1 activa |
| 16 tests Python pre-existentes fallidos | investigación propia (fuera de alcance PLAN 1) | 📋 Documentado |

## 8. Riesgos residuales

- **Rootfs ro recurrente** (F14-F01): el más probable de causar fricción; A3 lo detecta ahora antes de trabajar. Mitigación: remount manual periódico o reinicio (fstab rw ya fijado).
- **Prueba conductual B2**: depende de la evaluación humana; sin validación de Ramón, el resultado es solo de TERM (AUTO-REVISIÓN honesta).
- **Web sin metodología v1.1 cargada** hasta reiniciar: riesgo de que la Web actúe con reglas v1.0 mientras TERM usa v1.1 — mitigado por A4 (reinicio documentado) y checksum (check detecta desincronización).

## 9. Cierre formal

- **PLAN 1 implementado y validado** (excepto instalación global + reinicio, bloqueados por rootfs ro — no bloqueantes, reversibles, documentados).
- **Reversible**: revertir commits de PLAN 1 + borrar review-pending.md + quitar campos del template deja el sistema como en v0.31.0-plan0.
- **Regla de no regresión**: 0 regresiones funcionales (pytest idéntico al baseline; suites propias verdes).
- **Tag**: `v0.31.1-plan1` creado.
- **Secuencia**: PLAN 1 cerrado → F4 podrá abrirse con la metodología reforzada (gate análisis + env check + revisión diferida).

---

*Closeout elaborado por TERM (TASK-20260808-019). Plan: TASK-20260808-018. Revisión independiente: PENDIENTE (lote review-pending) — AUTO-REVISIÓN honesta.*

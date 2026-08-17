# PLAN — Auditoría post-C2 (17-18 agosto) y plan de mejoras sin regresión

- **Fecha**: 2026-08-18
- **Autor**: [WEB] OpenCode Web (ASUS)
- **Origen**: petición RAMON — "auditoría de lo hecho estos dos días: puntos buenos, malos, fallos, mejoras; plan que evalúe que no rompa nada"
- **Estado**: PROPUESTA — pendiente de revisión humana (GO / GO CON CAMBIOS / NO-GO)

## 1. ALCANCE AUDITADO

Trabajo del 2026-08-17/18: bloque C2 (mypy 87→0), cierre administrativo, TASK-001..004 (hook, test, expedientes, rama), sync Mac, reconciliación rama del TERM, ratificación del lote. Evidencia: 145 commits (main), 131 expedientes UDO, 25 tareas en coordination.json.

## 2. PUNTOS BUENOS (con evidencia)

| # | Punto | Evidencia |
|---|-------|-----------|
| B1 | mypy P1 87→0 en producción (55 archivos) | gates re-ejecutados: 0 errores |
| B2 | Bug real corregido: `guardian_logger` doble definición de `_save_to_qdrant` (el publish de alertas NUNCA se emitía) | expediente TASK-031, hallazgo documentado |
| B3 | Hook pre-commit reparado: ruff 0.15.18→0.16.3 (RUF100 falso positivo con select ALL) | `pre-commit run ruff` → Passed |
| B4 | Trazabilidad UDO completada: expedientes 024-030 retroactivos, 026 CANCELLED, commits registrados, gate verify OK, actas | `ura-udo verify` OK, review-pending |
| B5 | Autorizaciones expresas auditadas (--force con justificación) en cierres DONE | expedientes TASK-001..004 |
| B6 | Anti-alucinación: verificación con comandos reales, NO VERIFICABLE declarado, HECHO/DECLARADO separados | informes de sesión |
| B7 | Smoke funcional real: 750 tests passed en módulos con cambio de comportamiento | pytest 27 archivos |
| B8 | Cero pérdida de trabajo ajeno: stash del TERM recuperable (06025a36) + diff vacío vs main | fsck + diff |

## 3. PUNTOS MALOS / FALLOS (autocrítica con evidencia)

| # | Fallo | Evidencia | Lección |
|---|-------|-----------|---------|
| M1 | **Limpieza RUF100 basada en diagnóstico erróneo**: `--select RUF100` deshabilitaba PLR0917 en la evaluación → 4 noqa válidos eliminados → revertido con git checkout | plan v2 check 3 + corrección D6 | `--select` NO sirve para diagnosticar noqa muertos con select=ALL; usar solo `ruff check .` |
| M2 | **scp multi-fuente dejó test_heartbeat.py en la raíz de la Mac** (en vez de tests/unit/) | `git status` Mac: `?? test_heartbeat.py` | Verificar destino tras scp con rutas múltiples |
| M3 | **stash pop aplicó un stash AJENO del TERM** en la Mac (conflicto UU en ARCHITECTURE.md) | `UU docs/ARCHITECTURE.md` tras pop | Verificar `git stash list` ANTES de pop; nunca `pop` a ciegas en repo ajeno |
| M4 | **Rama temporal test-rebase + worktree** creados en zona ajena y limpieza manual posterior | branch -D, worktree remove | Operaciones git en la Mac exigen plan previo y estado documentado |
| M5 | **3 rebases fallidos** ("unstaged changes" fantasma: la Mac regenera ARCHITECTURE.md en checkout) | intentos autostash | Documentar el comportamiento del detector de la Mac (hook post-checkout) |
| M6 | **Commit del trabajo ajeno** (52e2dd74) atribuido a [WEB] — contamina autoría | git log | Los archivos ajenos se committean con mensaje de procedencia (hecho) pero el ideal es que los commitee su dueño |
| M7 | **El cierre 031 se auditó 1 día tarde**: gate UDO (commits, expediente) NO se cumplió en 44c9b8ce | coordination.json sin commits | El gate de integridad debe ejecutarse en TODA tarea cerrada (ya es regla; faltó cumplimiento) |
| M8 | **Ruido operativo**: 67/145 commits (46%) son auto-push del TERM (41) + auto-integraciones (26) | git log --grep | El auto-push commitea 1 vez por ciclo; debería agruparse y/o usar rama dedicada estable |
| M9 | **La divergencia Mac↔ASUS no tiene arreglo estructural**: se resolvió con reset --hard (contenido redundante verificado) pero volverá a ocurrir | rama ia/TASK-005 41 locales vs 3 remotos | El detector TERM commitea en la rama de tarea actual; debería commitea en mac-veredictos siempre |
| M10 | **6 rondas "haz lo pendiente"**: los informes dejaban siempre un último pendiente sin cerrar | conversación 2026-08-18 | Los informes deben declarar CERO pendientes cuando no los hay; el cierre del lote con ratificación puede ser final |

## 4. MEJORAS PROPUESTAS (plan de acciones, sin regresión)

Cada acción con: QUÉ · POR QUÉ · IMPACTO · VERIFICACIÓN · RIESGO/REVERSIBILIDAD.

### A1. Documental — Lecciones operativas en `docs/udo/hallazgos-fondo.md` (MEJORA)
- QUÉ: registrar M1 (--select RUF100), M2 (scp), M3 (stash pop), M5 (detector Mac regenera ARCHITECTURE.md) como hallazgos con lección.
- POR QUÉ: no repetir los 4 fallos en futuras sesiones.
- IMPACTO: solo docs. VERIFICACIÓN: grep de las 4 entradas. RIESGO: nulo (reversible: borrar entradas).

### A2. Documental — Nota operativa del flujo Mac↔ASUS en AGENTS.md (MEJORA)
- QUÉ: añadir §"Operación en la Mac": (a) el detector regenera ARCHITECTURE.md en checkout → operaciones git requieren pausa del detector o expectativa de archivo regenerado; (b) scp con múltiples fuentes verifica rutas destino; (c) nunca `git stash pop` sin `git stash list` previo en el repo Mac.
- POR QUÉ: M2/M3/M5 causaron incidentes evitables.
- IMPACTO: AGENTS.md (zona TASK-008 reservada → requerirá autorización/coordinación). VERIFICACIÓN: lectura + ejemplo. RIESGO: bajo; reversible con revert.

### A3. Config — Agrupar auto-push del TERM (NECESARIO, requiere TERM)
- QUÉ: que el detector del TERM agrupe veredictos pendientes en 1 commit por ciclo (o por lote de N minutos) en lugar de 1 commit por evento.
- POR QUÉ: M8 (41 commits en 2 días, 46% del log es ruido).
- IMPACTO: detector del TERM (zona del TERM; requiere coordinación con él — NO ejecutable por WEB solo).
- VERIFICACIÓN: tras el cambio, ≤3 commits de auto-push por día.
- RIESGO: bajo si lo hace el TERM; REVERSIBLE (config del detector).

### A4. Coordinación — Rama dedicada para veredictos del TERM (NECESARIO, requiere TERM)
- QUÉ: el auto-push del TERM debe committea SIEMPRE en `mac-veredictos` (rama estable) con rebase automático antes del push, nunca en la rama de tarea actual.
- POR QUÉ: M9 (divergencias 41/3, reconciliaciones forzadas).
- IMPACTO: flujo del TERM; ASUS ya integra mac-veredictos (a18217ed, 25a880c5) → el detector del TERM en ASUS ya funciona. Requiere cambio en el detector del TERM.
- VERIFICACIÓN: 0 divergencias de ramas de tarea en 1 semana.
- RIESGO: medio si se toca sin test; REVERSIBLE (config).

### A5. Proceso — Gate de integridad UDO en todo cierre (NECESARIO)
- QUÉ: añadir a `ura-udo` (o al proceso) que `verify` + gate de integridad se ejecuten SIEMPRE en el cierre DONE (no solo si el que cierra lo recuerda); el cierre 031 lo saltó y se detectó al día siguiente.
- POR QUÉ: M7.
- IMPACTO: `scripts/pro/ura-udo` (script del TERM, commits 2d45cf43/533cf2cd — requiere TASK propia con reserva y revisión); alternativa sin tocar código: procedimiento documentado.
- VERIFICACIÓN: cerrar una TASK de prueba sin verify → bloqueada.
- RIESGO: bajo (script bash ya validado); REVERSIBLE (git revert).

### A6. Deuda — Cobertura de módulos tocados por C2 (MEJORA, TASK futura)
- QUÉ: medir y subir cobertura de los módulos con cambios de comportamiento del C2 (guardian_logger, debate_engine, mochila_engine, motor/agents/agent.py) hacia ≥80% (política RAMON 2026-08-13).
- POR QUÉ: los fixes cambiaron runtime; la política exige ≥80% por módulo en trabajo nuevo.
- IMPACTO: solo tests nuevos (sin tocar producción). VERIFICACIÓN: `coverage run --source=<módulo>` ≥80%.
- RIESGO: nulo para producción; REVERSIBLE (borrar tests).

### A7. Verificación — Confirmar estado de los 30 noqa PLR0917 (MEJORA, rápida)
- QUÉ: con ruff 0.16.3 activo en hook, re-verificar que `ruff check .` sigue en 0 (noqa válidos) — sin limpiarlos.
- POR QUÉ: M1 dejó la duda; validación de que el hallazgo D6 (falso positivo) es estable.
- IMPACTO: ninguno (solo ejecutar ruff). VERIFICACIÓN: ruff check . = 0. RIESGO: nulo.

## 5. MÍNIMOS OBLIGATORIOS del plan
- A1+A2+A5(proc.)+A7: ejecutables por WEB, sin tocar zonas ajenas (salvo A2 que toca AGENTS.md — requiere autorización expresa o coordinación con TASK-008).
- A3+A4: SOLO con el TERM (se delega, no se ejecuta por WEB).
- A6: TASK propia con su plan y reservas (fuera de esta ejecución).
- Cero cambios en producción. Cero cambios en la rama del TERM.
- Al final: gates (ruff 0, mypy 0, verify_protocol OK) y working tree limpio.

## 6. NO HACER
- No tocar el detector del TERM ni su rama (A3/A4 se delegan).
- No limpiar los noqa PLR0917 (válidos).
- No ejecutar pytest completo (2+ h).
- No crear infraestructura nueva.

## 7. VALIDACIÓN
1. `grep -c` de las entradas nuevas en hallazgos-fondo.md (A1)
2. `git diff AGENTS.md` revisable (A2)
3. `ruff check .` → All checks passed (A7, post-ejecución)
4. `python3 scripts/pro/verify_protocol.py` → OK
5. `git status --short` → limpio (excepto zonas ajenas autorizadas)

## 8. CRITERIOS DE CIERRE
- A1, A2 (si autorizada), A5-proceso, A7 completados y verificados
- A3/A4 delegados al TERM con registro en coordination.json
- A6 registrada como TASK propuesta pendiente
- Informe final con HECHO/DECLARADO y estado de zonas ajenas

## 9. ANÁLISIS DE RIESGO GLOBAL (no romper nada existente)
- Acciones A1/A5/A7: solo lectura/escritura docs → riesgo nulo.
- A2: toca AGENTS.md (reservado por TASK-008 en REVIEW) → se hará solo con autorización expresa (--force auditado) o se delega; reversible.
- A3/A4: delegadas al TERM → riesgo cero para el WEB; el TERM evaluará impacto en su detector (con su plan y reversión).
- A6: tests nuevos → riesgo nulo en producción.
- NINGUNA acción toca código de producción, la rama del TERM ni el estado ya ratificado del lote C2.

## 10. VEREDICTO DEL PLAN
**GO CON CAMBIOS** — el plan es conservador (nada toca producción ni zonas ajenas sin autorización); las dos acciones de mayor impacto (A3/A4) se delegan al TERM con su propia evaluación. Aprobación humana requerida antes de ejecutar (al menos A1, A5-proceso, A7 son ejecución inmediata si se autoriza).

# PLAN 0 — Revisión post-implantación (autoaplicación §46)

**Fecha**: 2026-08-08
**Tarea**: TASK-20260808-017
**Método**: la propia metodología aplicada a su implantación — comprobar eficacia real, no existencia. Cada hallazgo verificado contra el código (no asumido).
**Veredicto**: la implantación es funcional pero tiene 2 brechas BLOQUEANTES de eficacia y 3 NECESARIO que deben repartirse entre Plan 0 (parche) y F4.

---

## 1. Hallazgos (verificados)

### B1 — BLOQUEANTE: el gate UDO no verifica el análisis previo

**Evidencia** (`scripts/pro/ura-udo:127-160` `_gate_revision`): el gate de DONE verifica `commit_base`, `commits:` no vacíos, diff no vacío, pinning de SHAs, árbol limpio. **No verifica ningún campo de análisis** (`revision:`, veredicto, ANÁLISIS DEL PLAN).

**Consecuencia**: un agente puede ejecutar sin análisis previo y cerrar DONE igualmente. La regla central del Plan 0 (§2) no está reforzada por la herramienta — depende de la buena voluntad del LLM. El §48 afirma "Web/Terminal aplican la metodología" pero nada lo hace verificable.

**Verificado**: campo `revision:` vacío en 15 de 16 expedientes; solo TASK-010 lo pobló (formato F3 antiguo, hoy retirado). El análisis previo real de TASK-015/016 (auditoría) quedó en el historial como nota libre, no como campo estructurado.

### B2 — BLOQUEANTE: no existe comprobación previa del entorno de trabajo

**Evidencia**: hoy mismo el rootfs `/` estaba `ro` (F14-F01) y bloqueó la instalación de `~/.config/opencode/AGENTS.md`; hubo que remontar a mano. `ura-engineering-check` verifica reglas (versión, checksum, puntero) pero **nada de entorno**: rootfs, servicios, secretos, espacio en disco, git saneado.

**Consecuencia**: el entorno degradado se descubre *durante* el trabajo, no antes. Es el patrón recurrente de 4 meses (rootfs ro reapareció tras "resolverse" en julio; servicios fallidos conocidos: ura-fix, ura-detector, etc.).

### N1 — NECESARIO: sin política de revisor independiente operativa

**Evidencia**: 0 commits `[WEB]` en el verano (verificado en inventario); Web idle de facto. AUTO-REVISIÓN (F2.2) es honesta pero se convirtió en la norma. El Plan 0 §33 contempla degradación, pero no define qué pasa *sistemáticamente* cuando el revisor no está: ni retraso, ni lote, ni revisión diferida.

**Consecuencia**: los errores sistémicos (2356 lint, config duplicada, secretos en .bashrc) no los detecta el ejecutor; históricamente los detectó el humano o una auditoría puntual.

### N2 — NECESARIO: la prueba de eficacia actual es de presencia, no de conducta

**Evidencia** (`tests/engineering/test_engineering.sh`): 13 asserts que comprueban que los archivos *contienen* cadenas ("buscar contradicciones", "más sencilla que cumpla..."). No prueban que un agente real detecte un plan incompleto/contradictorio/complejo. Es una prueba de instalación, no de eficacia.

**Consecuencia**: el §44 (10 casos) queda sin validación conductual real. El cierre del Plan 0 se apoyó en una prueba que no demuestra lo que afirma.

### N3 — NECESARIO: sin postmortem retrospectivo (evidencia para §46)

**Evidencia**: §46 exige "evidencia de que el cambio aporta valor" antes de modificar la metodología, pero no hay registro central de incidentes con causa raíz. Los ~20 errores de 4 meses (secretos, lint masivo, scripts que corrompían código, rootfs, config duplicada, F3 prematuro) están dispersos en closeouts y auditorías.

**Consecuencia**: sin postmortem no hay base para decidir qué regla preventiva añadir — la mejora continua es anecdótica.

### M1 — MEJORA: divergencia entre máquinas no cubierta

**Evidencia**: AGENTS.md:12-16 "Desarrollar en Mac, sincronizar a ASUS" es flujo manual (scp/rsync, `sync_ura.sh`). La metodología global solo se instala en ASUS (`~/.config/opencode/AGENTS.md`); en Mac (`/Users/ramonesnaola/URA/ura_ia_1972/`) no hay copia ni check. §43 dice "no depender de una máquina concreta" pero la instalación es máquina-específica.

**Consecuencia**: trabajar desde Mac implica trabajar sin la metodología instalada — se desvanece el principio rector cuando más se necesita (desarrollo).

### M2 — MEJORA: riesgo de burocracia (teatro de proceso)

**Evidencia**: las 20 preguntas (§50) pueden convertirse en checklist relleno sin análisis. El propio Plan 0 (§20, §47) advierte contra sobreingeniería, y F3 murió por ceremonia — riesgo de repetir el patrón con el proceso.

**Consecuencia**: el proceso debe tener proporcionalidad (plan trivial → análisis breve; plan complejo → análisis completo), y debe medirse el coste del proceso vs el error evitado.

### D1 — DESCUBRIMIENTO: trazabilidad de "validación" débil

**Evidencia**: el expediente registra commits y estado, pero la *validación* (qué pruebas pasaron) queda en notas del historial; no hay campo estructurado `validacion:` en el template. El gate no exige evidencia de validación (tests pasados) antes de DONE.

**Consecuencia**: "qué pruebas pasaron" (§34) no es respondible de forma verificable sin abrir el historial de notas.

### D2 — DESCUBRIMIENTO: la Web no tiene forma de recibir la metodología si no se reinicia

**Evidencia**: el servicio `opencode.service` (Web) arrancó a las 00:29; AGENTS.md global se instaló a las 18:10. Config no hot-reload (opencode carga config al arranque). La Web en ejecución **no ha cargado** la metodología instalada hoy.

**Consecuencia**: "Web aplica la metodología" (§48) no es cierto hasta reiniciar el servicio. Hay que documentar el reinicio como parte del cierre/verificación.

---

## 2. Soluciones mínimas propuestas (sin infraestructura nueva)

| Hallazgo | Solución mínima | Coste |
|----------|-----------------|-------|
| **B1** análisis no verificado | Añadir a `_gate_revision` (ura-udo): exigir campo `analisis:` en el expediente (no vacío, con texto) antes de DONE. El campo se rellena vía `update --analisis "…"` al pasar a IN_PROGRESS. Sin infraestructura: un campo + una comprobación. | ~30 min |
| **B2** sin check de entorno | Extender `ura-engineering-check` con subcomando `--env`: rootfs rw/ro (`findmnt`), servicios críticos activos (opencode, model-router, ollama), secretos presentes (`OPENCODE_WEB_PASS`), espacio en disco, git saneado (`git status` limpio). Salida OK/WARN/FAIL. | ~45 min |
| **N1** revisor ausente | Política de degradación: (a) si no hay revisor distinto al ejecutor, la tarea se cierra con AUTO-REVISIÓN **y** entra en cola de revisión diferida (archivo `docs/udo/review-pending.md` con lista de tareas sin revisión independiente); (b) en cada cierre de fase, revisión cruzada por lotes de las tareas pendientes; (c) regla: un humano o el otro agente revisa el lote antes de cerrar la fase. | ~1h |
| **N2** prueba de eficacia | Prueba conductual mínima: 3 planes de ejemplo reales (uno incompleto, uno contradictorio, uno con fase futura) en `tests/engineering/planes/`; el agente (Web o TERM) debe completar el ANÁLISIS DEL PLAN sobre cada uno y registrar el veredicto; criterio de cierre: los 3 análisis detectan el defecto correspondiente. Evaluable manualmente por Ramón (no automatizable al 100% — es conducta LLM). | ~1h + evaluación |
| **N3** postmortem | `docs/engineering/POSTMORTEMS.md`: tabla con ~20 incidentes de 4 meses: fecha, síntoma, causa raíz, ¿fallo de proceso?, regla preventiva (¿ya existe en Plan 0?), estado. Rellenado en una sesión de análisis histórico (closeouts + AGENTS.md "Problemas Conocidos" + auditorías). | ~1-2h |
| **M1** divergencia Mac | Documentar en ENGINEERING_PROCESS §13: "en Mac, instalar la copia de `deploy/engineering/AGENTS.md.global` igualmente (instalación manual o script de sync)"; el check `ura-engineering-check` en Mac avisa si falta. Sin infraestructura: documentación + check ya cubre. | ~20 min |
| **M2** burocracia | Regla de proporcionalidad en PLAN_REVIEW_TEMPLATE: "plan trivial → análisis de 5 líneas; plan complejo → análisis completo". Y métrica de coste: en el closeout, anotar tiempo de análisis vs tiempo de ejecución. | ~15 min |
| **D1** validación no registrada | Añadir campo `validacion:` al template de expediente (rellenable en DONE) + comprobación en gate (no vacío). | ~20 min |
| **D2** Web sin reiniciar | Documentar en ENGINEERING_PROCESS §11 y en el closeout: tras instalar/actualizar AGENTS.md global, **reiniciar opencode.service** (o los servicios relevantes) y verificar con `ura-engineering-check`. | ~5 min + reinicio |

---

## 3. Diseño mínimo de los 4 elementos pedidos

### 3.1 Prueba real de eficacia de la metodología
- **Qué**: 3 planes de ejemplo defectuosos (incompleto / contradictorio / fase futura) + 1 correcto.
- **Cómo**: el agente completa PLAN_REVIEW_TEMPLATE sobre cada uno; se evalúa si detecta el defecto.
- **Dónde**: `tests/engineering/planes/{correcto,incompleto,contradictorio,prematuro}.md` + `tests/engineering/README.md` con el procedimiento de evaluación.
- **Criterio de éxito**: 3 de 4 defectos detectados en primera pasada (75%); re-ejecución tras fallo = evidencia para §46.
- **Limitación honesta**: no automatizable; requiere evaluación humana (Ramón) o revisión cruzada TERM/WEB.

### 3.2 ura-env-check (extensión de ura-engineering-check)
- Subcomando `--env`: 
  - rootfs: `findmnt -T / -o OPTIONS` → rw/ro (WARN si ro)
  - servicios: `systemctl is-active` para opencode, model-router, ollama, ura-api (FAIL si crítico inactivo)
  - secretos: `/etc/ura/secrets.env` legible + `OPENCODE_WEB_PASS` presente
  - disco: `df /` uso < 90%
  - git: `git status --porcelain` limpio en el repo (WARN si sucio)
  - Salida: OK / WARN (lista) / FAIL — exit code correspondiente.
- Sin BD, sin deps: bash + findmnt + systemctl + df + git.

### 3.3 Política de revisión independiente con degradación controlada
- **Normal**: revisor distinto del ejecutor (UDO `--revisor`), gate F2.2 completo.
- **Degradación 1 (revisor idle)**: cierre con AUTO-REVISIÓN **obligatoria marcada** (ya existe) + registro en `docs/udo/review-pending.md`.
- **Degradación 2 (nadie disponible)**: tarea queda en REVIEW indefinidamente (estado actual) — nunca se finge.
- **Revisión diferida**: al cerrar una fase, el revisor (o Ramón) revisa el lote de `review-pending.md`; las tareas revisadas se marcan en el archivo con fecha + revisor + veredicto.
- **Regla de fase**: una fase no se cierra si el lote de review-pending no está revisado o explícitamente aceptado por Ramón (decisión humana — nunca automática).

### 3.4 Postmortem retrospectivo
- `docs/engineering/POSTMORTEMS.md` — estructura por incidente: fecha | síntoma | causa raíz | fallo de proceso (sí/no) | regla preventiva (¿existe? ¿cuál?) | estado.
- Fuentes: AGENTS.md "Problemas Conocidos", closeouts de fases, AUDITORIA-F3, PLAN_0_AUDITORIA, historial de esta sesión.
- **Objetivo**: responder con evidencia "¿qué falló y qué regla lo previene?" para que §46 tenga datos.

---

## 4. Reparto propuesto (Plan 0 / F4 / posteriores)

| Elemento | Dónde | Justificación |
|----------|-------|---------------|
| B1 gate analisis + D1 campo validacion | **Plan 0 — parche v1.0.1** (inmediato, sin esperar F4) | La regla central del Plan 0 no está reforzada: es un defecto de la implantación, no una mejora. |
| B2 ura-env-check --env | **Plan 0 — parche v1.0.1** | Fue parte del §40 original ("comprobación") — la implantación lo dejó a medias. |
| D2 reinicio Web documentado | **Plan 0 — parche v1.0.1** | El §48 afirma algo que hoy es falso (Web no ha cargado la metodología). |
| N1 política de revisión + review-pending | **F4** (o parche si Ramón prefiere) | Afecta al proceso UDO global; merece diseño propio con su auditoría. |
| N2 prueba de eficacia conductual | **F4** | Requiere planes de ejemplo + evaluación humana; es la validación de la metodología, no su corrección. |
| N3 postmortem retrospectivo | **F4 — entrada** | Es la evidencia que F4 usará para ajustar la metodología (§46). |
| M1 divergencia Mac (documentación) | **F4** (o parche, 20 min) | No bloquea; documentar en el parche si se toca ENGINEERING_PROCESS. |
| M2 proporcionalidad (burocracia) | **F4** | Regla de proceso, se incorpora al template con la prueba de eficacia. |

**Regla de parche v1.0.1**: solo B1, B2, D1, D2 (+ M1 si va incluido) — cambios acotados al gate, template y script existentes, sin infraestructura nueva. Nada más entra en el parche sin autorización.

---

## 5. Veredicto

**La implantación es funcional pero incompleta en eficacia**: cumple la forma (§48 verificable en presencia/checksum) pero no la función — la regla central (análisis previo) no está reforzada por la herramienta, y no hay comprobación del entorno. **2 BLOQUEANTES** (B1, B2) que deben parchearse en Plan 0 v1.0.1 antes de considerar F4 sólida, y 3 NECESARIO (N1-N3) que conforman F4.

No se implementa nada de esto sin tu aprobación. La propuesta queda en este documento y en el expediente TASK-017.

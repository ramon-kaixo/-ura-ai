# AUDITORÍA CRÍTICA F3 — Revisión formal por pares (GO/NO-GO)

**Fecha:** 2026-08-08 · **Auditor:** TERM (protocolo de Ramón §21.1–21.10)
**Objeto:** Plan F3 (estados CHANGES_REQUESTED/APPROVED, subcomando `review`, máquina de transiciones) — revertido en `f0ededd5`, ahora auditado antes de decidir.
**Método:** auditoría del estado real (exploración) + búsqueda adversarial (2 rondas) + revisión de diseño + verificación contra el protocolo y la REGLA PERMANENTE.

---

## 21.1 Auditoría previa — estado real verificado

- UDO actual = F1+F2 puro: 9 subcomandos, 7 estados (PLANNED/IN_PROGRESS/REVIEW/DONE/BLOCKED/CONFLICT/CANCELLED), sin `review`, sin máquina de transiciones. Revert limpio, 0 código muerto F3.
- Expedientes: 12 tareas (5 DONE, 6 CANCELLED, 1 REVIEW — TASK-006, única activa, esperando Ramón desde 11:13).
- Tests: 24 asserts (20 escenarios); no cubren `verify` completo, `status`/`list`, ni el ciclo F3 propuesto.
- Realidad operativa: **0 commits [WEB]** — todos los cierres reales son de un único agente (TASK-011 auto-revisión explícita, TASK-012 sin identidad de revisor). El modelo dual es hoy ficción; "DONE desde REVIEW" se cumple formalmente, la independencia real no existe.

## 21.2 Búsqueda adversarial — hallazgos

Los hallazgos del adversario (informe completo recuperable en sesión de auditoría) se clasifican:

**Fallo estructural (H0):** no es frontera de seguridad, es una convención — mismo unix user, mismo repo, expediente y git reescribibles. Evidencia: 10 commits huérfanos en el repo, TASK-012 registra SHAs (`e20f6021`, `e1d1deea`) que NO son ancestros de HEAD (reescritos tras cerrar).

**Los 5 modos de fallo más probables en la práctica:**
1. **Cierre sin revisión independiente** — self-review o DONE sin identidad (es el 100% de los cierres reales).
2. **Aprobación que ya no cubre el contenido actual** — sin pinning de SHA, la revisión se desacopla del árbol (ya ocurrió: SHAs no-ancestros).
3. **Evidencia vacía o editada a mano** — `revision:` nunca poblado (0/12), `commits:` stale, estructura canónica rota por edición manual en TASK-006/011/012.
4. **DONE sin integridad comprobada** — verify opcional, base mal puesto vacía el diff, árbol sucio, tests no exigidos.
5. **Esquive por fricción** — 6/12 CANCELLED, campos vacíos, `--force` como vía normal.

**Otros hallazgos relevantes:** commit-before-IN_PROGRESS vacía el diff legítimamente (E2); TOCTOU revisor/ejecutor (C1); asimetría broad/narrow del enforcement de reservas (C3); expediente partido fuera del frontmatter (H2); doc↔código: "--force con nota" no validado (H4); verify sobre-declara con commits intermedios ajenos (H1); `verify` imprime `REQUEST: OK` sin comprobar nada (P5).

## 21.3 Revisión de diseño — ¿qué aporta el plan F3?

El plan F3 (2 estados nuevos + subcomando review + transiciones) **no resuelve ninguno de los 5 modos de fallo**:

| Fallo principal | ¿Lo resuelve F3? |
|---|---|
| Cierre sin revisión independiente | NO — F3 tampoco fija identidad de revisor ni evita self-review |
| Aprobación que no cubre el contenido actual | NO — F3 no introduce pinning de SHA |
| Evidencia vacía/editada a mano | PARCIAL — subcomando review estructura el historial, pero sigue siendo texto libre editable |
| DONE sin integridad comprobada | NO — el gate de integridad es lo que falta, no estados nuevos |
| Esquive por fricción | EMPEORA — más estados y transiciones = más ceremonia que esquiva |

Los problemas REALES están en F2 (pinning, gate, identidad, integridad), no en la máquina de estados F3. La ronda actual REVIEW→IN_PROGRESS→REVIEW con notas ya cubre el ciclo de corrección; CHANGES_REQUESTED es ese mismo ciclo con otro nombre.

## 21.4 Definición de "revisado" (requisito del protocolo)

Evidencia mínima verificable y reconstruible (adaptada a la realidad de 1 agente):

1. `revision:` **obligatorio** al cerrar: `[revisor, SHAs exactos revisados, nota]`.
2. Los SHAs revisados deben ser **ancestros de HEAD** en el momento del DONE (pinning).
3. Gate de integridad ejecutado **dentro** del update a DONE (no en verify, que es opcional).
4. Si revisor == ejecutor (o ausente) → marca automática `AUTO-REVISIÓN` (la dice la herramienta, no el texto libre).

## 21.5 Fuente de verdad

Git = contenido (commits + SHAs pinneados). Expediente = estado + decisión + evidencia. La conversación NO es fuente de verdad. No se duplica información reconstruible sin razón de trazabilidad (los SHAs en `commits:` son el vínculo expediente↔git; con pinning + gate, la reconstrucción es determinista).

## 21.6 Seguridad/concurrencia

El flock serializa el CLI; las ediciones manuales no (C2, ya evidenciado). Mitigación: el gate de integridad en DONE no evita la edición manual, pero el pinning hace que una revisión falsa sea detectable (`revision:` vacío, SHAs no-ancestros, `commits:` stale). TOCTOU se elimina con pinning (la aprobación fija SHAs; commits posteriores al DONE quedan fuera de la revisión y visibles como "post-cierre").

## 21.7 Roles

Roles por tarea (no fijos por agente): `agente_web`/`agente_terminal`. No se ata la revisión a Web ni a Terminal. Con un solo agente activo, la revisión honesta es re-lectura del diff y DEBE marcarse como tal (AUTO-REVISIÓN) — sin fingir independencia.

## 21.8 Estados

Los 7 estados actuales cubren el flujo completo (PLANNED→IN_PROGRESS→REVIEW→DONE, BLOCKED/CONFLICT/CANCELLED como salidas). No se añaden CHANGES_REQUESTED/APPROVED: la ronda se expresa como REVIEW→IN_PROGRESS→REVIEW con notas (menos estados, mismo ciclo, sin transiciones inválidas nuevas que mantener). Transiciones inválidas: no hay máquina, solo reglas: DONE solo desde REVIEW; DONE requiere pinning + gate; CANCELLED documentado en nota.

## 21.9 Casos extremos (resueltos en el diseño mínimo)

| Caso | Solución |
|---|---|
| Revisor aprueba versión antigua | Pinning: DONE registra SHAs y valida ancestros |
| Ejecutor commitea tras la revisión | Commits post-DONE visibles en `verify` post-cierre (información, no bloqueo) |
| Base mal puesto / diff vacío | Gate: diff base..HEAD no vacío en DONE |
| Árbol sucio al cerrar | Gate: aviso + opción de bloquear con --force auditado |
| Self-review | Marca AUTO-REVISIÓN automática |
| --force sistemático | Ratio force/transiciones reportable en `status`; cada force auditado |
| Reserva amplia vs estrecha (C3) | Documentado como riesgo menor; verificar asimetría en `check` (aplazado) |
| Un solo agente | CASO A (ejecutar→revisar→corregir→cerrar) honesto con AUTO-REVISIÓN |
| Tarea REVIEW abandonada | `status` muestra antigüedad; escalado manual a Ramón (sin timer nuevo) |

## 21.10 DECISIÓN — NO-GO para F3 tal como está planificado

**Motivo:** el plan F3 no proporciona las garantías que promete (no toca los 5 modos de fallo reales) y añade ceremonia (2 estados, subcomando, transiciones) que incrementa la fricción — el peor riesgo detectado (U1, esquive por deriva). Por la REGLA PERMANENTE ("si una solución más sencilla proporciona las mismas garantías, utiliza la más sencilla"), NO se implementa la máquina de estados F3.

**Alternativa recomendada (F3-rediseñada o "F2.2 — Garantías de revisión", si Ramón da GO):** los 3 mínimos del adversario, implementados en el ura-udo existente:
1. `revision:` obligatorio con pinning de SHAs + validación de ancestros en DONE.
2. Gate de integridad dentro del update a DONE (diff no vacío, base anterior al trabajo, árbol limpio en zona reservada, commits no vacíos).
3. Marca automática AUTO-REVISIÓN cuando no hay revisor distinto del ejecutor.

**Supone:** ~2-3h, sin infraestructura nueva, sin BD, sin servicios, sin estados nuevos. Reutiliza 100% de F1/F2. Cumple los criterios 21.4-21.9 con menos código que el F3 original.

**Fuera de alcance (NO implementar en esta fase):** máquina de transiciones, subcomando `review`, estados CHANGES_REQUESTED/APPROVED, panel, timer de escalado, autenticación de identidad, sellado de tiempo (todo registrado como pendiente).

---

*Informe de auditoría según protocolo Ramón §21.1-21.10 y REGLA PERMANENTE (docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md).*

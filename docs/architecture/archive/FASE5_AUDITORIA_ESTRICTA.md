# FASE 5 — Auditoría estricta (segunda vuelta, exhaustiva)

**Fecha**: 2026-08-08
**Tarea**: TASK-20260808-020 (ampliación)
**Base**: `docs/architecture/FASE5_AUDITORIA.md` (primera vuelta — GO CON CAMBIOS)
**Método**: verificación punto por punto del plan contra el código real. Todo comprobado con ejecución real, no asumido.

---

## A. Hallazgos NUEVOS (no detectados en la primera vuelta)

| Id | Hallazgo | Evidencia (verificado) | Clase | Propuesta mínima |
|----|----------|------------------------|-------|------------------|
| N1 | **`ura-udo status` NO muestra lo que §5.10 exige** — el plan pide por tarea: Estado, Owner, Última actividad, Commit, Pendiente. El status actual solo lista estados + reservas + últimos commits del repo; no hay "última actividad" ni owner por tarea | `status` subcommand (ura-udo:474) — solo `list IN_PROGRESS/REVIEW/BLOCKED + check + git log` | **BLOQUEANTE** (no cumple §5.10/§5.13) | Ampliar `status` para mostrar por tarea activa: TASK, estado, owner (agente_web/term con "(ejecutor)"), última transición (del historial), commits (de `commits:`), pendientes (de `pendientes:`) |
| N2 | **Los tests UDO no están integrados en Makefile** — §5.20 exige "tests de UDO" en validación; hoy `make validate`/`test-fast` solo corren pytest, `test_udo.sh` se ejecuta a mano | Makefile:21-25 test-fast = pytest; grep test_udo → 0 | **NECESARIO** | Añadir target `test-udo` (bash test_udo.sh + test_engineering.sh) e incluirlo en `validate` |
| N3 | **`ura-chat` tiene nombres equivocados** — el comentario de cabecera y el mensaje de uso dicen "ura-ask" (copy-paste del script hermano) | scripts/pro/ura-chat:1-3 | MEJORA | Corregir cabecera/uso a "ura-chat" |
| N4 | **La validación declarada no se contrasta con la realidad** (§5.8 caso B) — el gate solo exige que `validacion:` no esté vacío (texto libre); si un agente declara "Tests: OK" cuando fallan, nada lo detecta | ura-udo:163-171 — gate solo comprueba no vacío | **NECESARIO** | En `verify` (no gate): comparar `validacion:` con evidencia real (si menciona tests/suite → ejecutar rápido o avisar); al menos WARNING heurístico + documentación de cómo verificar |
| N5 | **`verify` detecta archivos modificados SIN DECLARAR en la reserva, pero NO los compara con lo declarado como "cambios"** (§5.8 casos A/D parcial) — sí detecta A y D (MODIFICADOS SIN DECLARAR ✅) pero no cruza con el campo `cambios:` del expediente | verify:451-540 — cruza reserva vs git, no `cambios:` vs git | MEJORA | Añadir a verify: comparar `cambios:` (declarados) vs archivos reales modificados → WARNING por omisión/extra |
| N6 | **`.agent_lock` es código muerto** — existe (0 bytes, gitignored) pero NINGÚN script lo usa (el bloqueo real es flock + reservas UDO) | grep agent_lock → solo docs; ura-udo usa flock (L:48) | DESCUBRIMIENTO | §5.17: eliminar o justificar en closeout |
| N7 | **Mensaje BLOQUEADO no incluye OWNER/SCOPE explícitos** (§5.4) — el enforcement dice "está reservada por TASK-XXX" pero no "OWNER=WEB SCOPE=..." | ura-udo:117 | MEJORA (cosmético) | Formatear el mensaje como pide §5.4: `BLOQUEADO TASK-XXX OWNER=... SCOPE=...` |
| N8 | **`pendientes:` y `resultado:` existen en el template pero NO tienen subcomando** — no hay `--pendientes` ni `--resultado` en update; solo se escriben a mano editando el expediente | template: pendientes/resultado; update: sin flags | **NECESARIO** | Añadir `--pendientes "…"` y `--resultado "…"` a update (mismo patrón que --analisis) |
| N9 | **No hay distinción resultado_web/resultado_terminal** (§5.7) — un solo campo `resultado:`; no se puede responder "¿qué hizo Web?" vs "¿qué hizo Terminal?" de forma estructurada | template: resultado: único | NECESARIO (confirmado) | O bien 2 campos (resultado_web/resultado_terminal) o usar agente_web/term + notas; decisión en implementación |
| N10 | **`ura-udo check` sin argumentos solo lista reservas activas pero no detecta conflictos futuros con rutas** — correcto por diseño, pero §5.4 pide que TERM al intentar ESCRIBIR reciba el bloqueo; el enforcement solo actúa al `update --reserva`, no al modificar archivos físicos | enforcement en update/reserve (L:307-320, 358-376) | MEJORA | Documentar en CONFLICTS.md: el bloqueo es por declaración (reserva), no por escritura física — el agente debe `check` antes de tocar; no automatizable sin fs watchers (sobreingeniería) |

## B. Confirmaciones de la primera vuelta (re-verificadas)

- §5.4/5.5/5.6 conflictos y paralelismo: ✅ (reservas + check, simétrico)
- §5.9 reconstrucción sin conversación: ✅ (TASK-015/016/019 reconstruidas)
- §5.12 commit sin TASK-ID: ✅ política correcta (no exigir, no inventar)
- §5.16 rendimiento: ✅ (status <1s, verify ~0.1s)
- §5.3 ligereza: ✅ sin BD/servidor/panel/dispatcher
- §5.22: ~15/23 criterios ya cumplidos

## C. Contradicciones internas del plan (Documento B)

| C1 | §5.10 pide "Última actividad / Owner / Pendiente" en status, pero el status actual no los da (N1) | Contradicción plan vs implementación → el plan asume capacidad inexistente |
| C2 | §5.14 pide "recuperar el control sin editar archivos manualmente" para lock huérfano, pero §5.13 dice "no generar procesos automáticos innecesarios" | Tensión: recuperación automática vs no automatizar → solución: comando explícito `ura-udo reserve TASK --clear` documentado (no timer automático) |
| C3 | §5.8 caso B exige detectar "Tests: OK declarado pero falla" pero §5.20 dice "la batería correspondiente al estado real" — la detección de contradicción de tests requeriría ejecutar tests en verify (lento) | Resolución: WARNING heurístico en verify (si validacion menciona tests → sugerir ejecutarlos), no ejecución automática |
| C4 | §5.7 "la misma solicitud se registra para Web y Terminal" — el flujo actual TERM crea tarea y la envía a Web (ura-opencode); la "perspectiva de Terminal" no se registra como resultado hasta que revisa | Alineación: usar `--resultado`/`--resultado_web`/`--resultado_terminal` al registrar cada lado |

## D. Riesgos adicionales no contemplados en el plan

| R1 | **La prueba real (§5.21) depende de la Web activa** — Web está idle de facto (0 commits [WEB] en verano); la TASK-REAL-001 con flujo Web no podrá completarse si la Web no responde | Plan de contingencia: si Web no está disponible, la prueba real usa TERM como programador y se marca AUTO-REVISIÓN (degradación documentada §33) |
| R2 | **§5.19 regla 7 "no guardar conversaciones completas"** — hay `~/.config/opencode/ura_context.json` (contexto compartido) y `docs/pro/sesiones/` (29 registros diarios) que podrían considerarse "conversaciones" — aclarar qué cuenta como conversación vs registro operativo | Definir en FASE5: registros de sesiones = operativos (commits, decisiones) no conversacionales |
| R3 | **Ampliar status con historial (N1)**: el historial puede crecer mucho; leer todo el expediente por tarea activa es lento — solución: mostrar solo última transición (tail del historial) | Diseño: `tail -1 historial` por tarea |

## E. Mejoras propuestas (adicionales, no pedidas pero dentro del espíritu)

| M1 | `ura-udo context` ya muestra expediente + commits; añadir a `ura-ask` un modo "resumen reconstruible" que responda las 5 preguntas de §5.9 (qué se quería, qué se hizo, quién, qué se revisó, qué falta) — el §5.9 es el corazón de la fase | Bajo coste: script que consolida campos del expediente |
| M2 | Verificar en §5.20 que `make validate` incluye los tests UDO (N2) — sin esto la "validación completa" es falsa | Target test-udo en Makefile |

## F. VEREDICTO FINAL (estricto)

# **GO CON CAMBIOS** (reafirmado, con más cambios)

El plan es válido y alineado, pero la auditoría estricta revela que **3 requisitos del propio plan no se cumplen hoy con la implementación existente** y exigen trabajo real (no solo documentación):

1. **N1 (BLOQUEANTE)**: §5.10 status sin Owner/Última actividad/Pendiente → ampliar `ura-udo status`.
2. **N8 (NECESARIO)**: campos `pendientes:`/`resultado:` sin subcomando → añadir `--pendientes`/`--resultado` (y decidir resultado_web/terminal).
3. **N2 (NECESARIO)**: tests UDO fuera del Makefile → integrar en `validate`.
4. **N4/N5 (NECESARIO/MEJORA)**: verify no contrasta declaraciones con realidad → WARNING heurístico + cruce `cambios:` vs git.
5. **H8/H11 (OBLIGATORIO primera vuelta)**: 4 documentos de docs/udo/ + prueba real TASK-REAL-001.

Y 1 contradicción interna a resolver (C2: recuperación de lock huérfano sin procesos automáticos → comando explícito documentado).

**Decisión pendiente de Ramón**: confirmar Documento B como referencia (descartar A), aprobar estos hallazgos, y autorizar la implementación de F5 con este alcance ampliado. Nada se implementa sin esa autorización.

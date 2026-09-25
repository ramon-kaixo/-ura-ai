# FASE 5 — Auditoría del plan (análisis previo obligatorio, §5.2 "primero identifica")

**Fecha**: 2026-08-08
**Tarea**: TASK-20260808-020
**Plan**: "FASE 5 — Integración con URA y Orquestación Autónoma (v4.0)" + "FASE 5 — Hardening, Prueba Real y Cierre del Sistema"
**Método**: metodología universal (Engineering Process v1.1) — análisis previo, verificación contra código real, clasificación, veredicto. NO implementar.

---

## 1. Contradicción estructural del plan

El plan Fase 5 se entregó con **DOS documentos que se contradicen**:

| Aspecto | Documento A (v4.0 "Orquestación Autónoma") | Documento B ("Hardening y Cierre") |
|---------|---------------------------------------------|-------------------------------------|
| Objetivo | URA como único punto de interacción, router de tareas, coordinador, delegación inteligente, supervisión, aprendizaje operativo | Cierre del sistema: verificación, pruebas, limpieza; NO añadir capacidades |
| Componentes | Router de tareas, gestor de contexto, coordinador, delegación, supervisión, aprendizaje, multi-LLM | Solo coordinar Web↔Terminal, trazabilidad, Git como evidencia |
| §5.24/§47 | **Violado**: sugiere orquestador, panel, dispatcher, sistema de agentes | **Cumplido**: "NO estamos construyendo un Jira/Linear/multiagente/orquestador/panel" |
| Conclusión | "URA se convierte en el centro operativo" | "No necesitamos convertir URA en una infraestructura distribuida" |

**Decisión propuesta**: el Documento B es la versión vigente (el propio plan en su §5.24 y "Cierre del Plan Completo" lo confirma, alineado con el Plan 0 §47 y con el precedente F3 NO-GO). El Documento A (v4.0) debe **descartarse como referencia de implementación** (quedar documentado como borrador que reintroduce la sobreingeniería ya rechazada). La auditoría se realiza contra el Documento B.

## 2. Qué existe ya (auditoría §5.2 — inventario real)

| Elemento | Estado | Evidencia |
|----------|--------|-----------|
| `docs/udo/` | ✅ 9 archivos + tasks/ + templates/ + review-pending.md | verificado |
| `scripts/pro/ura-udo` | ✅ 544+ líneas, 9 subcomandos | verificado |
| `scripts/pro/ura-opencode` | ✅ puente TERM→Web | verificado |
| `scripts/pro/ura-engineering-check` | ✅ reglas + `--env` (PLAN 1 A3) | verificado |
| `scripts/pro/ura-ask`, `ura-chat` | ✅ wrappers contexto | verificado |
| `scripts/pro/commit_msg_validator.py` | ✅ conventional commits (no exige TASK-ID) | verificado |
| `Makefile` | ✅ validate/validate-full | verificado |
| `.agent_lock` | ✅ existe (0 bytes, gitignored) | verificado |
| Hooks | ✅ commit-msg, post-commit, pre-commit, pre-push | verificado |
| `.gitignore` | ✅ `.agent_lock` incluido | verificado |
| AGENTS.md | ✅ sección UDO + metodología | verificado |
| `.github/tests-ci-exclude.txt`, `CI_POLICY.md` | ✅ creados (PLAN 1) | verificado |

**Conclusión §5.3 (revisión arquitectónica)**: la solución es ligera — Git como fuente de verdad, documentación de tareas, identificación Web/Terminal, asociación TASK→cambios→commits, verificación automática (verify + gate), mecanismo de bloqueo (flock + reservas). ✅ Sin BD, sin servidor, sin panel, sin cola, sin sistema de agentes. ✅ Cumple.

## 3. Verificación de pruebas §5.4–§5.16 contra código real

| Prueba | Estado real | Evidencia |
|--------|-------------|-----------|
| 5.4 Web↔Terminal conflicto (BLOQUEADO con OWNER/SCOPE) | ✅ Implementado — el enforcement de reservas (`_conflicto_reserva`, ura-udo:108-123) rechaza escrituras en zona reservada; `check` detecta CONFLICTO con TASK-ID | test_udo.sh esc. 5-8 |
| 5.5 Prueba inversa | ✅ Simétrico — no hay prioridad Web sobre Terminal; el propietario es quien tiene el lock (reserva) | `_reservas_activas_ajenas` trata igual |
| 5.6 Tareas independientes en paralelo | ✅ Permitido — solo se bloquea la zona solapada | test_udo.sh esc. 4, 6 |
| 5.7 Documentación cruzada (ambas perspectivas al mismo TASK-ID) | ⚠️ **Parcial** — el expediente registra agente_web/agente_terminal y contexto compartido (`ura-udo context`), pero no hay un campo estructurado para "resultado de Web" + "resultado de Terminal" por separado; las notas del historial lo permiten pero no lo garantizan | docs/udo/README §contexto |
| 5.8 Contradicciones (A: declara sin cambios pero git muestra 3; B: tests OK pero falla; C: revisión limpia pero cambio no registrado; D: A,B,C,D no declarados) | ⚠️ **Parcial** — `verify` detecta MODIFICADOS SIN DECLARAR (caso A y D ✅); NO detecta contradicciones de declaración (casos B y C) — no hay mecanismo que compare "declaración del agente" con la realidad (tests ejecutados, revisión limpia) | verify |
| 5.9 Pérdida de contexto (reconstruir sin conversación) | ✅ **Fundamental cumplido** — expediente + commits + `context` + gate; verificado de facto en TASK-015/016/019 (reconstruidas sin conversación) | docs/udo/README |
| 5.10 Recuperación tras interrupción | ✅ `ura-udo status` muestra TASK/estado/owner; `commit_base` automático; sin dependencia de sesión abierta | status |
| 5.11 Recuperación tras error | ✅ Gate: DONE solo desde REVIEW; tarea incompleta no puede cerrarse (CASO B); si falla el gate → bloqueado | test_udo.sh esc. 10, 11b |
| 5.12 Commit sin TASK-ID | ✅ Política ya implementada: el validador NO exige TASK-ID (conventional commits basta); no inventa tarea | commit_msg_validator.py |
| 5.13 Abandono de tarea | ⚠️ **Parcial** — `status` muestra tareas por estado (una tarea abandonada en IN_PROGRESS es visible), pero no hay "última actividad" ni detección de inactividad; no se inventa terminación ✅ | status |
| 5.14 Locks (normal, duplicado, huérfano, incorrecto) | ⚠️ **Parcial** — lock normal ✅ (flock), duplicado ✅ (rechazado por enforcement), incorrecto ✅ (no se puede liberar lock ajeno: la reserva es por TASK); **huérfano ⚠️** — no hay comando específico para recuperar reservas de tareas abandonadas (se puede con `--force` o `reserve --clear` manual, pero no es automático) | ura-udo |
| 5.15 Seguridad | ⚠️ **Pendiente de auditoría** — no se ha ejecutado una revisión formal (permisos, secretos, path traversal, comandos) | — |
| 5.16 Rendimiento | ✅ `status` <1s, `verify` ~0.1s con 20 tareas | medido |
| 5.17 Limpieza de código | ⚠️ **Pendiente** — no ejecutada; hay restos documentados (watchdog stub, residuos ~/.opencode) | §52 PLAN_0_REVISADO |
| 5.18 Documentación definitiva | ⚠️ **Parcial** — existe README.md; faltan WORKFLOW.md, TASKS.md, CONFLICTS.md, TROUBLESHOOTING.md | docs/udo/ |
| 5.19 AGENTS.md 8 reglas | ⚠️ **Parcial** — reglas 1-5, 8 ya presentes (Git fuente, TASK-ID, locks, no DONE sin evidencia, no infraestructura); falta regla 6 explícita (discrepancias se registran) y regla 7 (no guardar conversaciones) | AGENTS.md |
| 5.20 Validación completa | ⚠️ **Pendiente** — py_compile/ruff/mypy/bandit/pytest/tests UDO/integración | — |
| 5.21 Prueba operativa real | ⚠️ **Pendiente** — TASK-REAL-001 con flujo 1-10 | — |
| 5.22 Criterios de aceptación (23) | ⚠️ ~15 ya cumplidos; ~8 pendientes (dependen de 5.7, 5.8-B/C, 5.13, 5.14-huérfano, 5.15, 5.17, 5.18, 5.21) | — |

## 4. Hallazgos y clasificación

| Id | Hallazgo | Clase | Propuesta mínima |
|----|----------|-------|------------------|
| H1 | Dos documentos contradictorios en el plan F5 | BLOQUEANTE (decisión) | Confirmar que el Documento B es la referencia; archivar A como borrador descartado |
| H2 | §5.7: resultado de Web y Terminal no distinguidos estructuralmente | NECESARIO | Añadir campo `resultado_web:` / `resultado_terminal:` al expediente (o usar `revision:` + notas — decisión) |
| H3 | §5.8 casos B/C: contradicciones de declaración no detectadas | NECESARIO | `ura-udo verify` ampliado: verificar `validacion:` (campo A2) contra evidencia real (git status + tests) — WARNING si la declaración no coincide |
| H4 | §5.13: sin detección de abandono | MEJORA | `status` muestra fecha de última transición (historial) — sin procesos automáticos (alineado §5.13) |
| H5 | §5.14 lock huérfano: sin recuperación automática | MEJORA | Comando `ura-udo reserve TASK --clear` ya existe; documentar procedimiento en TROUBLESHOOTING.md; NO automatizar la liberación (riesgo de falso abandono) |
| H6 | §5.15: auditoría de seguridad no ejecutada | NECESARIO | Ejecutar auditoría de seguridad ligera (permisos, secretos en scripts, path traversal en ura-udo) |
| H7 | §5.17: limpieza de código pendiente | NECESARIO | Ejecutar limpieza (restos documentados: watchdog stub, residuos; revisar imports/permisos) |
| H8 | §5.18: faltan 4 documentos | OBLIGATORIO | Crear WORKFLOW.md, TASKS.md, CONFLICTS.md, TROUBLESHOOTING.md (cortos, prácticos) |
| H9 | §5.19: faltan reglas 6-7 de AGENTS.md | NECESARIO | Añadir "las discrepancias se registran" y "no guardar conversaciones completas" |
| H10 | §5.20: validación completa no ejecutada | NECESARIO | Ejecutar al final: py_compile, ruff, mypy, bandit, pytest, tests UDO + integración |
| H11 | §5.21: prueba operativa real pendiente | OBLIGATORIO | TASK-REAL-001 con flujo 1-10 documentado |
| H12 | El Documento A reintroduce la sobreingeniería rechazada (F3 NO-GO, Plan 0 §47) | DESCUBRIMIENTO (registrado) | Documentar en closeout: decisión de no implementar A (sin infraestructura nueva) |

## 5. Veredicto

# **GO CON CAMBIOS**

- **El plan (Documento B) es correcto, alineado con la infraestructura real y con la metodología**: la mayoría de las pruebas (§5.4-5.6, 5.9-5.12, 5.16) ya están implementadas y verificadas en UDO — la fase 5 es mayoritariamente **verificación + documentación + limpieza**, no desarrollo nuevo.
- **Cambios necesarios antes de implementar**:
  1. Confirmar Documento B como referencia y descartar A (H1).
  2. H8: crear los 4 documentos de docs/udo/ (trabajo principal real).
  3. H3: ampliar verify para detectar contradicciones de declaración (casos B/C).
  4. H6+H7: auditoría de seguridad + limpieza.
  5. H11: prueba operativa real TASK-REAL-001.
- **No es NO-GO**: no hay impedimento técnico; la infraestructura existente es compatible; los cambios son acotados.
- **NO se implementa nada de esto sin tu aprobación** (autoridad humana sobre el alcance, §24).

---

*Auditoría: TASK-20260808-020. Base: infraestructura real verificada (ura-udo 35/35, PLAN 0/1 cerrados, tag v0.31.1-plan1).*

# INFORME DETALLADO — Sesión UDO: 2026-08-08 → 2026-08-09 (dos días)

**Redactado**: 2026-08-09, desde evidencia (Git con horas, expedientes, closeouts, auditorías, suites)
**Ámbito**: **75 commits** · **21 expedientes UDO** (15 DONE, 6 CANCELLED) · **4 tags** · **17+ documentos nuevos** · **3 scripts nuevos** · **28 errores lint resueltos**
**Sistema**: URA / GX10 (ASUS GB10) — capa de coordinación UDO (UDO = URA Development Orchestrator)

---

## 1. Resumen ejecutivo

En dos días se construyó de cero **la capa de coordinación, trazabilidad y verificación de URA** (proyecto "UDO", 5 fases): un sistema ligero donde el usuario habla una vez, las tareas se identifican con TASK-ID, Web programa, Terminal consulta/revisa, Git demuestra qué ocurrió y nada depende de la conversación. Además se instaló la **Metodología Universal de Ingeniería** (Plan 0) que obliga a todo agente a analizar un plan antes de ejecutarlo.

Hitos clave del viaje:
1. **F1-F2** (trazabilidad + reservas) cerradas con tag `v0.30.0-f2`.
2. **F3** (revisión formal) auditada y **rechazada (NO-GO)** por sobreingeniería → sustituida por **F2.2** (gate de integridad + AUTO-REVISIÓN honesta).
3. **Plan 0** (metodología universal) auditado, revisado, implementado y verificado con tag `v0.31.0-plan0`.
4. **Plan 1** (corrección post-implantación: 2 bloqueantes) cerrado con tag `v0.31.1-plan1`.
5. **F4+F5** (verificación automática + hardening + prueba real) cerradas con tag `v0.32.0-f45`.
6. **28 errores ruff pre-existentes** resueltos → lint 100% limpio.

**Resultado final**: F1-F5 cerradas, 23/23 criterios de aceptación F5, 0 tareas activas, lote de revisión 7/7 aprobado por Ramón, B2 4/4 validado, árbol limpio.

---

## 2. Qué había antes (punto de partida, 2026-08-08 madrugada)

| Aspecto | Estado previo |
|---------|---------------|
| HEAD | `c468246d` (chore cleanup monitorear_opencode.sh) |
| Fases de motor URA | 29 fases cerradas (hasta v0.29.0-fase29) + post-F29 (F1-F4 + PM v3.1, 5251 tests baseline) |
| Coordinación entre agentes | **No existía**: sin tareas, sin reservas, sin TASK→commit |
| OpenClaw | Retirado del repo (`c6d60c8c` previo) pero servicio systemd vivo y crash-looping |
| Web (opencode.service :8081) | Activa pero sin metodología; **idle de facto** (0 commits [WEB] en el verano) |
| Rootfs `/` | Montado RO de forma recurrente (F14-F01) — causa conocida de bloqueos |
| Secretos | `OPENCODE_WEB_PASS=***REDACTED***` viejo en secrets.env; TAILSCALE_AUTH_KEY y HCLOUD_TOKEN hardcodeados en `.bashrc` |
| Alias de shell | `alias opencode='/usr/local/bin/opencode'` (wrapper de OpenClaw ya inexistente) |
| Ruff | 28 errores pre-existentes en 5 archivos que CI no alineaba |
| Referencias CI | `.github/CI_POLICY.md` y `tests-ci-exclude.txt` **inexistentes** pero referenciados en AGENTS.md |

---

## 3. CRONOLOGÍA COMPLETA (75 commits, hora a hora)

### 3.1 F1 — Base de coordinación, identidad y documentación (2026-08-08, 00:36–09:21)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 00:36 | `2b038179` | Trackear `monitorear_opencode.sh` (monitor de la Web) |
| 00:41 | `248902b4` | Fase 1: expedientes, ura-task, ura-status, ura-opencode integrado |
| 07:31 | `57eeb81a` | **UDO F1**: `scripts/pro/ura-udo` (create/show/update/list/status/verify) — orquestación mínima (TASK-001) |
| 07:32 | `b78db1ac` | Cerrar expediente TASK-001 |
| 07:55 | `c6d60c8c` | Retirar OpenClaw del código vivo (criterio grep → 0; excepciones SNC/router/test) |
| 09:12 | `9c5630d4` | Registro retirada OpenClaw + AGENTS.md sincronizado |
| 09:21 | `c11709b3` | Closeout 2026-08-08 (F1 + OpenClaw): decisiones, validación, pendientes |

**Qué se construyó**: `docs/udo/` (README, templates, .seq con flock), expedientes `TASK-YYYYMMDD-NNN.md` con historial auditado, saneo de credenciales (`ura-opencode` → `OPENCODE_WEB_PASS` vía env/secrets.env, sin hardcode).
**Por qué**: no había forma de responder "qué se pidió, quién lo hizo, qué commit lo produjo".

### 3.2 F2 — Reserva de archivos + verificación de discrepancias (2026-08-08, 10:24–11:13)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 10:24 | `cc59d36d` | **F2**: reserva de archivos + verificación de discrepancias (TASK-005) |
| 11:12 | `5f972290` | Auditoría F2 — fixes **D1-D8** + modelo dual + closeout (TASK-006) |
| 11:13 | `bcdea05b` | Expediente TASK-006 a REVIEW |

**Qué se construyó**:
- Reservas con enforcement (`reserve --add/--clear`, `check`), match exacto o prefijo `dir/`.
- `verify`: `MODIFICADOS SIN DECLARAR` / `RESERVADOS NO MODIFICADOS`.
- Modelo dual de roles por tarea: `--agente_web "WEB (ejecutor)" --agente_terminal "TERM (revisor)"`.
- Contexto compartido: `ura-udo context TASK` + wrapper `ura-ask` (recuperable aunque el otro agente esté idle).
- Fixes D1-D8 de la auditoría F2 (canal, commit_base compat F1, verificación de tareas, etc.).

**Por qué**: Web y Terminal se pisaban; no había forma de saber si lo declarado coincidía con lo real.

### 3.3 F3 — propuesta de revisión formal → **NO-GO** (2026-08-08, 11:29–13:48)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 11:29 | `43232acb` | **F3 implementada** (máquina de estados CHANGES_REQUESTED/APPROVED — TASK-009) |
| 13:40 | `f0ededd5` | **Revert F3** + F1/F2 corregido (19 tests OK) — TASK-011 |
| 13:48 | `54735d82`, `0367f527` | Verify + cierre TASK-011 |

**Por qué se revirtió**: auditoría crítica (§21.1-21.10, con subagente adversarial) demostró que la máquina de estados **no resolvía los 5 modos de fallo reales** (auto-aprobación, aprobación desacoplada del árbol, evidencia vacía, DONE sin integridad, esquive por fricción) y **añadía ceremonia**. Además hubo **trabajo prematuro**: F3 se implementó durante F2 (el caso fundacional del Plan 0 §13).
**Decisión de Ramón**: NO-GO → sustituida por F2.2 (garantías mínimas con la misma protección, mucho menos código).

### 3.4 F2.2 — Garantías de revisión (2026-08-08, 14:24–16:43)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 14:24 | `a74018f0` | Endurecimiento: `--force` auditado + campos instrucciones/restricciones (TASK-012) |
| 14:26 | `e20f6021` | Marcar `--force` en DONE forzado |
| 14:30 | `e1d1deea` | Cobertura reservas con prefijo `dir/` en verify y conflicto |
| 14:37 | `b63720e3` | **REGLA PERMANENTE** (plan/mínimos/descubrimientos) + AUDITORIA-F3 GO/NO-GO |
| 15:09 | `e06762c5` | **F2.2 gate integridad en DONE**: pinning SHAs, commits no vacíos, diff base..HEAD, árbol limpio, AUTO-REVISIÓN (TASK-013) |
| 15:14-15:15 | `d46ff1e8`, `30f1f979` | Sincronizar expedientes; cerrar F3 — F2.2 validado |
| 15:57 | `beabe807` | **Fix IFS** (bug de word-splitting en el gate de la sesión paralela) + docs F2.2 |
| 16:37 | `296d826b` | Cierre formal fases F1-F2-F2.2 + F3 NO-GO (closeout §13) |
| 16:43 | `e7143df4` | AGENTS.md refleja cierre + **tag `v0.30.0-f2`** |

**Qué se construyó**:
- `_gate_revision()`: al cerrar DONE sin `--force` exige commit_base, commits registrados (verify previo), diff no vacío, **pinning** (SHAs ancestros de HEAD — historia reescrita bloquea), árbol limpio.
- **AUTO-REVISIÓN automática**: si revisor vacío o == ejecutor, la herramienta lo marca (nunca texto libre, nunca se finge).
- `--force` = excepción auditada (`AUTORIZACIÓN EXPRESA (--force)` en historial).
- Directiva permanente `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`.

**Incidentes**:
- Bug IFS de la sesión paralela: el `for` hacía word-splitting por espacios (mensajes de commit con espacios rompían el pinning) → fix `local IFS=','` + `sha="${entry# }"; sha="${sha%% *}"`.
- `git stash/pop` perdió el bit +x de ura-udo (rc=126) → `chmod +x` restaurado.
- TASK-014 accidental por `ura-opencode --help` → cancelada con nota.

### 3.5 PLAN 0 — Infraestructura de Ingeniería para Agentes (2026-08-08, 16:54–18:09)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 16:54 | `bf505639` | Pendientes resueltos reflejados en closeout y AGENTS.md |
| 16:59 | `2e7c8768` | OpenClaw unit borrada; wrapper eliminable con seguridad |
| 17:46 | `2009ecba` | **PLAN_0.md referencia maestra (943 líneas)** + auditoría GO CON CAMBIOS (TASK-015) |
| 17:52 | `fbeac1ae` | **PLAN_0_REVISADO v1.1** — 8 cambios + autoaplicado §50 (20 preguntas) |
| 17:56 | `fc1fc20d` | Cierre auditoría aprobada + TASK-016 |
| 18:00 | `67ede0b5` | **Implementación**: docs/engineering/ (4 archivos) + AGENTS.md puntero + deploy + ura-engineering-check |
| 18:02 | `17589285` | Limpieza §52: refs CI colgantes resueltas (CI_POLICY.md + tests-ci-exclude.txt creados) |
| 18:06 | `dbca5ac0` | **Casos §44 1-6 validados** (test_engineering.sh 13/13) |
| 18:08 | `e263b911` | Closeout Plan 0 v1.0 |
| 18:09 | `2c981828` | Expediente a REVIEW + **tag `v0.31.0-plan0`** |

**Qué se construyó**:
- `docs/engineering/`: ENGINEERING_PROCESS v1.0 (10 obligaciones, clasificación, roles, trazabilidad), PLAN_TEMPLATE (11 preguntas §50), PLAN_REVIEW_TEMPLATE (ANÁLISIS + veredicto + 9 preguntas), README.
- AGENTS.md: sección "Metodología Universal de Ingeniería" como **puntero** (§38 — no duplica).
- `deploy/engineering/AGENTS.md.global` — copia de instalación reproducible.
- `scripts/pro/ura-engineering-check` — versión en cabecera + sha256sum + presencia.
- ROLE_MODEL **fusionado** en ENGINEERING_PROCESS §9 (no archivo aparte — anti-sobreingeniería).

**Auditoría §45 (aplicar la metodología al propio plan)**: se entregó el plan a OpenCode antes de implementar; se revisó la infraestructura real (config Web/Terminal, carga de reglas, UDO, ura-opencode, AGENTS.md); se detectaron duplicaciones (REGLA-PLAN), contradicciones (reglas globales no existían), y se entregó el plan revisado con 8 cambios. **Veredicto: GO CON CAMBIOS**.

### 3.6 PLAN 1 — Corrección post-implantación (2026-08-08, 18:18–18:56)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 18:18 | `0ff47466` | **Revisión post-implantación** (autoaplicación §46): 2 BLOQUEANTES + 3 NECESARIO + 2 MEJORA + 2 DESCUBRIMIENTO (TASK-017) |
| 18:21 | `5332b2f2` | **PLAN_1_MEJORAS** propuesto — GO CON CAMBIOS (TASK-018) |
| 18:34 | `ccfdde7d` | **A1/A2**: gate analisis+validacion (35/35) — TASK-019 |
| 18:35 | `347b1157` | **A3**: ura-engineering-check --env |
| 18:38 | `c0a170e9` | **A4/A5/B1/B4** + ENGINEERING_PROCESS v1.1 |
| 18:39 | `30a380c9` | **B2**: 4 planes conductuales + procedimiento |
| 18:41 | `1bf9368c` | **B2 evaluación** (3/3 defectos, 4/4 veredictos) + **B3 POSTMORTEMS** (20 incidentes) |
| 18:42 | `ca0b689b` | Copia global v1.1 (AGENTS.md.global) |
| 18:55 | `85e45d92` | Closeout PLAN 1 v1.1 |
| 18:56 | `078f4578` | Expediente REVIEW + review-pending creado + **tag `v0.31.1-plan1`** |

**Los 2 BLOQUEANTES que motivaron el plan** (detectados en la revisión post-implantación):
1. **B1**: el gate UDO no verificaba el análisis previo (verificado: `revision:` vacío en 15/16 expedientes) — la regla central dependía de la buena voluntad del LLM.
2. **B2**: no existía comprobación del entorno (el rootfs RO de ese mismo día lo demostró).

**Implementación**:
- **A1/A2**: campos `analisis:`/`validacion:` en expedientes + gate DONE los exige (con bug de orden detectado y corregido: los campos deben persistirse ANTES del gate).
- **A3**: `--env` (rootfs rw/ro, servicios críticos, secretos, disco, git).
- **A4/A5**: reinicio de Web documentado (config no hot-reload) + instalación Mac.
- **B1**: revisión diferida — `docs/udo/review-pending.md`; una fase no cierra con el lote sin revisar.
- **B2**: prueba conductual real (4 planes defectuosos evaluados por el agente).
- **B3**: POSTMORTEMS.md — 20 incidentes, causa raíz (35% ejecución sin análisis, 15% entorno).
- **B4**: proporcionalidad (plan trivial → análisis breve).

### 3.7 F4+F5 — Verificación automática + Hardening y Cierre (2026-08-08 22:59 → 2026-08-09 01:44)

| Hora | Commit | Qué se hizo |
|------|--------|-------------|
| 22:59 | `4ea71ad0` | Formato tabla review-pending |
| 23:28 | `4358ab1a` | **Auditoría F5** (GO CON CAMBIOS — TASK-020) |
| 00:01 | `d03de3a8` | **Auditoría estricta F5** — 10 hallazgos nuevos verificados |
| 00:12 | `4ed36d2d` | Consolidación tareas 016-019 DONE |
| 00:12 | `800519fe` | Inicio TASK-20260809-001 (F4+F5) |
| 00:18 | `34ac875a` | **F4 verify ampliado + F5 N1-N9** (status, Makefile, ura-chat, BLOQUEADO, pendientes/resultado) |
| 00:21 | `b5d0c6a3` | **H8 docs definitivas** (WORKFLOW/TASKS/CONFLICTS/TROUBLESHOOTING) + H9 reglas AGENTS.md |
| 00:23 | `abeef52e` | Closeout F4+F5 — **23/23 criterios** |
| 00:24 | `19833c15`, `79172822` | Cierres TASK-001/020 + lote review-pending |
| 00:52 | `6c7a7118` | Lote review-pending = 7 tareas |
| 00:59 | `af317cce` | **B2 validada por Ramón** (4/4) |
| 01:05 | `f488c7b0` | **Lote review-pending aprobado por Ramón** (7/7) |
| 01:07 | `c2331fc0` | Ruff verificado 0 nuevos — pendiente cerrado |
| 01:44 | `222e52f8` | **28 errores ruff pre-existentes resueltos** |
| 05:50 | `6513905c` | Informe de sesión |

**Los 10 hallazgos de la auditoría estricta F5** (verificados uno a uno contra el código):
- **N1 (BLOQUEANTE)**: `ura-udo status` no mostraba Owner/Última actividad/Commit/Pendiente (§5.10) → ampliado.
- **N2**: tests UDO fuera del Makefile → target `test-udo` integrado en `validate`/`validate-full`.
- **N3**: `ura-chat` con nombres erróneos (cabecera "ura-ask") → corregido.
- **N4**: gate solo exigía `validacion:` no vacío, no contrastaba con la realidad → verify NOTA heurística (§5.8-B).
- **N5**: verify no cruzaba `cambios:` con Git → coherencia F4 (§5.8-D).
- **N6**: `.agent_lock` código muerto → eliminado + .gitignore.
- **N7**: mensaje BLOQUEADO sin OWNER/SCOPE → `BLOQUEADO: ... TASK= OWNER= SCOPE=` (§5.4).
- **N8**: `pendientes:`/`resultado:` sin subcomando → `--pendientes`/`--resultado`.
- **N9**: sin distinción Web/Terminal → `--resultado_web`/`--resultado_terminal` (§5.7).
- **N10**: bloqueo por declaración (no fs watchers) → documentado en CONFLICTS.md.

**4 contradicciones internas del plan resueltas**:
- C1: §5.10 asumía status que no existía → N1.
- C2: lock huérfano vs "no automatizar" → comando explícito documentado.
- C3: detectar tests falsos sin ejecutarlos en verify → WARNING heurístico.
- C4: §5.7 doble registro → resultado_web/terminal.

**Prueba real §5.21**: la propia TASK-20260809-001 ejecutó el flujo 1-10 (crear → implementar → registrar → verify → revisar → validar → comparar con Git → pendientes → corregir → cerrar) y se cerró con el gate completo (analisis + validacion + AUTO-REVISIÓN).

**Cierre**: tag `v0.32.0-f45`, criterios §5.22 **23/23**, auditoría de seguridad limpia (permisos, secretos, shell=True, eval, path traversal), lint 100%.

---

## 4. Los 28 errores ruff pre-existentes (2026-08-09, 01:07–01:44)

**Cómo se descubrieron**: al verificar el pendiente "ruff/mypy/bandit", se ejecutó `ruff check .` de verdad (no se asumió) → 28 errores.

| Archivo | Errores | Fix |
|---------|---------|-----|
| `docs/merge_resolution/test_api.py` | 17 (S101 asserts + INP001) | per-file-ignores justificado (tests documentales, convención del proyecto) |
| `docs/merge_resolution/test_path_setup.py` | 6 (S101 + S110) | ídem |
| `mantenimiento/ura_maintenance.py` | 2 (LOG015) + 1 (F821 tras fix) | `logging.warning` → `logger.warning` + definición de logger movida antes del uso |
| `motor/core/llm/_state.py` | 1 (PLR0915, 56 statements) | `# noqa: PLR0915 — ADR-007: núcleo congelado, refactor requiere ADR` |

**Verificación**: `ruff check .` → All checks passed · `ruff format --check .` → 264 archivos OK · import del módulo tocar OK.
**Corrección de comunicación**: la primera afirmación "0 errores nuevos" era verdad pero engañosa (ocultaba 28 errores existentes). Se corrigió ejecutando y resolviendo, no solo documentando.

---

## 5. Qué se instaló — inventario completo

### Scripts nuevos (3)
| Script | Líneas aprox. | Función |
|--------|---------------|---------|
| `scripts/pro/ura-udo` | 600+ | CLI de coordinación: create/show/context/update/reserve/check/list/status/verify + gate F2.2 + A1/A2 |
| `scripts/pro/ura-engineering-check` | 220+ | Comprobación reglas (versión/checksum) + `--env` (entorno) |
| `scripts/pro/ura-chat` | 20 | Chat LLM a Ollama (nombre corregido) |

### Scripts modificados (3)
| Script | Cambio |
|--------|--------|
| `scripts/pro/ura-opencode` | Secretos saneados; contexto UDO inyectado; roles duales |
| `scripts/pro/ura-ask` | Wrapper de contexto UDO |
| `Makefile` | target `test-udo` en validate/validate-full |

### Documentación nueva (17+)
| Ruta | Contenido |
|------|-----------|
| `docs/engineering/README.md` | Índice + fuentes referenciadas |
| `docs/engineering/ENGINEERING_PROCESS.md` | Metodología v1.1 (ciclo, 10 obligaciones, clasificación, roles, trazabilidad, env, proporcionalidad) |
| `docs/engineering/PLAN_TEMPLATE.md` | 11 preguntas obligatorias del plan |
| `docs/engineering/PLAN_REVIEW_TEMPLATE.md` | ANÁLISIS DEL PLAN + veredicto + 9 preguntas |
| `docs/engineering/POSTMORTEMS.md` | 20 incidentes con causa raíz y reglas preventivas |
| `docs/udo/README.md` | Principios UDO, gate, reservas, contexto |
| `docs/udo/WORKFLOW.md` | Cómo trabajar con Web y Terminal |
| `docs/udo/TASKS.md` | Referencia rápida de comandos |
| `docs/udo/CONFLICTS.md` | Bloqueo por reserva, BLOQUEADO, paralelismo |
| `docs/udo/TROUBLESHOOTING.md` | Lock huérfano, gate, commit sin TASK, discrepancias |
| `docs/udo/review-pending.md` | Lote de revisión diferida |
| `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md` | Directiva permanente de Ramón |
| `docs/udo/AUDITORIA-F3-2026-08-08.md` | Auditoría GO/NO-GO de F3 |
| `docs/udo/CLOSEOUT-2026-08-08.md` / `CLOSEOUT-F2-2026-08-08.md` | Cierres F1/F2/F2.2 |
| `docs/udo/INFORME_SESION_2026-08-08-09.md` | Este informe |
| `docs/architecture/PLAN_0.md` (943L), `PLAN_0_AUDITORIA.md`, `PLAN_0_REVISADO.md`, `PLAN_0_CLOSEOUT.md` | Plan 0 completo |
| `docs/architecture/PLAN_0_POSTIMPLANTACION.md` | Revisión post-implantación |
| `docs/architecture/PLAN_1_MEJORAS.md`, `PLAN_1_CLOSEOUT.md` | Plan 1 |
| `docs/architecture/FASE5_AUDITORIA.md`, `FASE5_AUDITORIA_ESTRICTA.md`, `FASE5_CLOSEOUT.md` | Fase 5 |
| `deploy/engineering/AGENTS.md.global` | Copia de instalación reproducible |
| `.github/CI_POLICY.md`, `.github/tests-ci-exclude.txt` | Referencias CI que faltaban |
| `tests/udo/test_udo.sh` (35 asserts) | Suite UDO |
| `tests/engineering/test_engineering.sh` (13) + `planes/` (4) + `README.md` | Suite engineering + prueba conductual |

### Instalaciones de sistema
| Elemento | Cómo |
|----------|------|
| `~/.config/opencode/AGENTS.md` | Copia de `deploy/engineering/AGENTS.md.global` (remount rw temporal) — verificada por checksum |
| `opencode.service` | Reiniciado (00:54) para cargar la metodología v1.1 (config no hot-reload) |
| `/etc/systemd/system/ura-openclaw.service` | Borrada + daemon-reload (retirada completa OpenClaw) |
| `/usr/local/bin/opencode` (wrapper muerto) | Eliminado; aliases rotos del .bashrc eliminados; opencode real = `~/.opencode/bin/opencode` v1.17.7 |
| `/etc/ura/secrets.env` | Línea duplicada `321000` eliminada; `OPENCODE_WEB_PASS` nuevo (48 chars) |
| `.agent_lock` | Eliminado (código muerto) |

---

## 6. Cómo se instaló la metodología (proceso reproducible en 6 pasos)

1. **Fuente única**: `docs/engineering/` en el repo git (versionado, cabecera `<!-- Engineering Process v1.1 -->`).
2. **AGENTS.md del proyecto** → sección "Metodología Universal de Ingeniería" (puntero, no duplica — §38).
3. **Copia global**: `deploy/engineering/AGENTS.md.global` → `~/.config/opencode/AGENTS.md` (mecanismo nativo de opencode; Web y Terminal comparten home).
4. **Verificación**: `ura-engineering-check` (versión en cabecera + sha256sum) → RESULTADO: OK.
5. **Reinicio**: `sudo systemctl restart opencode.service` — sin esto la Web no carga la metodología (config no hot-reload; el D2 de la auditoría).
6. **En Mac**: misma copia documentada (A5) — instalación equivalente, fuente única en git.

---

## 7. Incidentes y problemas resueltos (con causa raíz)

| Incidente | Causa raíz | Solución |
|-----------|------------|----------|
| Rootfs `/` RO bloquea escrituras (2 veces) | fstab con `errors=remount-ro` + no-new-privileges (F14-F01) | Remount rw temporal para instalar; **A3 `--env` lo detecta ahora antes de trabajar** |
| F2.2 gate rompía pinning con commits de mensaje largo | Bug de word-splitting (IFS por espacios) en `for` de la sesión paralela | `local IFS=','` + tests 11c |
| ura-udo sin bit +x tras `stash/pop` (rc=126) | Manipulación git manual durante conflicto de sesiones | `chmod +x` restaurado + suite |
| TASK-014 basura creada por `ura-opencode --help` | Herramienta sin validación de input | Cancelada con nota documentada |
| `OPENCODE_WEB_PASS=***REDACTED***` duplicado en secrets.env | Valor antiguo pre-F1 + append nuevo | Línea vieja eliminada (sed); único valor de 48 chars |
| `TAILSCALE_AUTH_KEY`/`HCLOUD_TOKEN` en `.bashrc` | Secretos hardcodeados históricos | Documentado como tarea de seguridad aparte (requiere sudo + rotación) |
| Aliases rotos `opencode`/`openclaw` en .bashrc | Retirada del wrapper OpenClaw sin revisar el shell | Aliases eliminados; `opencode` → `~/.opencode/bin/opencode` v1.17.7 |
| 28 errores ruff que CI debería detectar | Lint no alineado con la realidad | Resueltos (ver §4) — 0 restantes |
| Refs CI colgantes en AGENTS.md | Documentación sin verificar contra repo | `.github/CI_POLICY.md` + `tests-ci-exclude.txt` creados |
| Web no cargaba la metodología instalada | Config no hot-reload (arranque 00:29 vs instalación 18:10) | Reinicio documentado (A4) + ejecutado |

---

## 8. Validación final (evidencia completa)

| Comprobación | Resultado | Cómo se verificó |
|--------------|-----------|------------------|
| `tests/udo/test_udo.sh` | **35 OK, 0 FAIL** | ejecución real (30 previos + 5 nuevos A1/A2) |
| `tests/engineering/test_engineering.sh` | **13 OK, 0 FAIL** | ejecución real (casos §44 1-6) |
| `ura-engineering-check` | **OK — reglas instaladas y sincronizadas** | checksum sha256 idéntico (2 copias) |
| `ura-engineering-check --env` | OK CON WARNINGS (rootfs ro detectado) | ejecución real en ASUS |
| `ruff check .` | **All checks passed** (28 → 0) | ejecución real con .venv/bin/ruff |
| `ruff format --check .` | **264 archivos OK** | ejecución real |
| pytest (subconjunto) | Sin regresiones vs baseline (692 passed/16 pre-existentes verificado con stash) | comparación con/sin cambios |
| Criterios F5 §5.22 | **23/23** | tabla en closeout |
| Lote review-pending | **7/7 aprobado por Ramón** | revisión con diffs + verificación cruzada |
| B2 (prueba conductual) | **4/4 veredictos validados por Ramón** | revisión humana de los 4 análisis |
| Gate de cierre TASK-001 | superado con analisis+validacion | prueba real del gate |
| Tags | v0.30.0-f2 → v0.31.0-plan0 → v0.31.1-plan1 → v0.32.0-f45 | git tag |

---

## 9. Decisión clave que definió todo (lección F3 → Plan 0)

El momento más importante de la sesión: **F3 se implementó prematuramente durante F2**, y la auditoría la rechazó. De ahí salieron las dos piezas que definen todo lo demás:
1. **REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md** (directiva permanente): clasificar descubrimientos, no ampliar alcance sin autorización, una fase no cierra sin mínimos.
2. **Plan 0** (metodología universal): "un plan NUNCA se ejecuta sin análisis previo" — el agente no es un ejecutor de órdenes, es un ingeniero que analiza, clasifica, propone y solo ejecuta tras aprobación.

Y el principio que lo resume todo (§9 del informe corto):
> El humano define la intención y los límites. El plan define el trabajo propuesto. El agente analiza contra la realidad. Se detecta lo que falta. Se fija el plan definitivo. Uno ejecuta, otro revisa. Git conserva la evidencia. Nada se declara terminado sin poder demostrarlo.

---

## 10. Pendientes conocidos (ninguno bloqueante)

| Pendiente | Responsable | Estado |
|-----------|-------------|--------|
| Migrar secretos de `~/.bashrc` a `/etc/ura/secrets.env` + rotar TAILSCALE_AUTH_KEY | Ramón (sudo) | Documentado (tarea de seguridad aparte, requiere rotación) |
| 16 tests Python pre-existentes fallidos (mcp/resiliencia/cli/benchmark) | investigación propia | Documentado (no regresión de la sesión; baseline idéntico) |
| Ejecutar `make validate` completo (5251 tests) | TERM/Ramón | Parcial (pytest subconjunto 692 passed; suite completa >4 min) |

---

*Informe elaborado desde evidencia: `git log` cronológico (75 commits con horas), expedientes UDO (21), closeouts (F2/PLAN_0/PLAN_1/FASE5), auditorías (F3, PLAN_0, FASE5 estricta), suites (35+13), ruff (0 errores). Nada inventado; todo comprobado.*

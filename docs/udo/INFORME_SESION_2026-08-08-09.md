# INFORME — Sesión UDO: 2026-08-08 → 2026-08-09 (dos días)

**Redactado**: 2026-08-09, desde evidencia (Git, expedientes, closeouts, auditorías)
**Ámbito**: 75 commits · 21 expedientes UDO · 4 tags · 17+ documentos nuevos
**Sistema**: URA / GX10 — capa de coordinación UDO (UDO = URA Development Orchestrator)

---

## 1. Resumen ejecutivo

En dos días se construyó de cero **la capa de coordinación, trazabilidad y verificación de URA** (proyecto "UDO", 5 fases): un sistema ligero donde el usuario habla una vez, las tareas se identifican con TASK-ID, Web programa, Terminal consulta/revisa, Git demuestra qué ocurrió y nada depende de la conversación. Además se instaló la **Metodología Universal de Ingeniería** (Plan 0) que obliga a todo agente a analizar un plan antes de ejecutarlo.

Resultado final: **F1-F5 cerradas, tag v0.32.0-f45, lint 100% limpio, 0 tareas activas, árbol limpio.**

---

## 2. Qué había antes (punto de partida)

- `c468246d` era HEAD (2026-08-08, madrugada): URA ya tenía 29 fases de motor cerradas (v0.29.0-fase29, post-F29: F1-F4 + PM v3.1), pero **sin capa de coordinación entre agentes**.
- OpenClaw (gateway MCP externo) estaba retirado del repo pero su servicio systemd seguía vivo y fallando (crash-loop).
- Dos agentes OpenCode (Web y Terminal) trabajaban sin forma de coordinarse: sin tareas, sin reservas de archivos, sin trazabilidad TASK→commit.

## 3. Qué se construyó — las 5 fases (por qué cada una)

### F1 — Base de coordinación, identidad y documentación (2026-08-08)
**Por qué**: no había forma de saber "qué se pidió, quién lo hizo, qué commit lo produjo".
- `scripts/pro/ura-udo` (bash puro): `create|show|update|list|status|verify` — expedientes `docs/udo/tasks/TASK-YYYYMMDD-NNN.md` con historial auditado.
- `docs/udo/` (README + templates) + retirada limpia de OpenClaw (código `c6d60c8c`, servicio `ura-openclaw` parado/deshabilitado).
- `ura-opencode` integrado (crea tarea → la envía a la Web → contexto inyectado).
- Tags: `v0.30.0-f2` (cierre F1+F2).

### F2 — Reserva de archivos + verificación de discrepancias (2026-08-08)
**Por qué**: Web y Terminal se pisaban; no había forma de saber si lo declarado coincidía con lo real.
- Reservas con enforcement (`reserve --add/--clear`, match exacto o prefijo `dir/`), `check` detector de conflicto.
- `verify`: discrepancias reserva↔Git (`MODIFICADOS SIN DECLARAR`, `RESERVADOS NO MODIFICADOS`).
- Modelo dual de roles por tarea (Web ejecutor / Terminal revisor) + contexto compartido (`context`, `ura-ask`).
- Endurecimiento: `--force` auditado (queda en historial como `AUTORIZACIÓN EXPRESA`), campos instrucciones/restricciones.
- Closeout F2 (§1-11) con suite `tests/udo/test_udo.sh` 30 asserts.

### F3 — Tareas, trazabilidad y relación con Git → **NO-GO** (2026-08-08)
**Por qué se paró**: la propuesta de F3 (máquina de estados de revisión CHANGES_REQUESTED/APPROVED) fue auditada críticamente (auditoría adversa §21.1-21.10, con subagente adversarial) y **rechazada**: no resolvía los 5 modos de fallo reales de la revisión y añadía ceremonia. Decisión de Ramón: NO-GO → sustituida por **F2.2** (garantías mínimas reales):
- Gate de integridad en DONE: commits registrados (verify previo), diff `commit_base..HEAD` no vacío, **pinning** (SHAs ancestros de HEAD — historia reescrita bloquea), árbol limpio.
- **AUTO-REVISIÓN automática** cuando revisor vacío o == ejecutor (la dice la herramienta, nunca se finge).
- Documentos: `AUDITORIA-F3-2026-08-08.md`, `REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md` (directiva permanente de Ramón).

### PLAN 0 — Infraestructura de Ingeniería para Agentes (2026-08-08)
**Por qué**: corregir el problema de raíz de 4 meses de errores (35% causados por "ejecución sin análisis previo").
- **Referencia maestra** `docs/architecture/PLAN_0.md` (943 líneas): un plan NUNCA se ejecuta sin análisis previo; 10 obligaciones; clasificación de descubrimientos (OBLIGATORIO/NECESARIO/MEJORA/DESCUBRIMIENTO/PENDIENTE/FUERA DE ALCANCE); mínimos; puntos críticos; NO HACER; veredicto GO/GO CON CAMBIOS/NO-GO.
- **Auditoría** (§45 del propio plan) → GO CON CAMBIOS → **Plan 0 revisado v1.1** autoaplicado (responde sus 20 preguntas).
- **Implementación**: `docs/engineering/` (ENGINEERING_PROCESS v1.0, PLAN_TEMPLATE 11 preguntas, PLAN_REVIEW_TEMPLATE + veredicto, README), AGENTS.md como puntero (§38), `deploy/engineering/AGENTS.md.global` (copia instalable), `ura-engineering-check` (versión + checksum + sincronización).
- Refs CI colgantes resueltas (`.github/CI_POLICY.md`, `tests-ci-exclude.txt` creados).
- Tags: `v0.31.0-plan0`.

### PLAN 1 — Corrección post-implantación (2026-08-08)
**Por qué**: la revisión post-implantación (autoaplicación §46) detectó 2 BLOQUEANTES: el gate no verificaba el análisis previo y no había check de entorno.
- **A1/A2**: campos `analisis:`/`validacion:` en expedientes + gate DONE los exige (la regla central queda reforzada por la herramienta, no por buena voluntad).
- **A3**: `ura-engineering-check --env` (rootfs rw/ro, servicios críticos, secretos, disco, git) — el entorno degradado se detecta ANTES de trabajar.
- **A4/A5**: reinicio de Web documentado tras instalar reglas (config no hot-reload) + instalación en Mac.
- **B1**: política de revisión diferida — tareas AUTO-REVISADAS se registran en `docs/udo/review-pending.md`; una fase no cierra con el lote sin revisar.
- **B2**: prueba conductual real — 4 planes de ejemplo (correcto/incompleto/contradictorio/fase futura) evaluados por el agente: **3/3 defectos detectados, 4/4 veredictos correctos** (validado por Ramón).
- **B3**: `POSTMORTEMS.md` — 20 incidentes de 4 meses con causa raíz (35% ejecución sin análisis; 15% entorno no verificado).
- **B4**: proporcionalidad (plan trivial → análisis breve).
- Tags: `v0.31.1-plan1`.

### F4 — Verificación automática y detección de discrepancias (2026-08-09)
**Por qué**: §5.8 exige detectar contradicciones entre declaración y realidad.
- `verify` ampliado: cruce `cambios:` vs Git (archivos reales fuera de lo declarado → WARNING) + NOTA heurística si la validación declarada menciona tests (verificar manualmente).

### F5 — Hardening, prueba real y cierre (2026-08-09)
**Por qué**: comprobar que todo funciona junto, que Web/Terminal no se pisan, que la documentación es fiable.
- Auditoría estricta del plan (2ª vuelta, 10 hallazgos nuevos verificados): **N1** status sin Owner/Última actividad (BLOQUEANTE) → `ura-udo status` ampliado (§5.10); **N2** tests UDO fuera del Makefile → target `test-udo` integrado en `validate`; **N3** `ura-chat` con nombres erróneos → corregido; **N4/N5** verify heurístico; **N6** `.agent_lock` muerto → eliminado; **N7** mensaje `BLOQUEADO TASK=... OWNER=... SCOPE=...` (§5.4); **N8/N9** `--pendientes/--resultado/--resultado_web/--resultado_terminal` (§5.7).
- Docs definitivas: `WORKFLOW.md`, `TASKS.md`, `CONFLICTS.md`, `TROUBLESHOOTING.md`.
- AGENTS.md: Reglas UDO v5 (§5.19, 8 reglas).
- Auditoría de seguridad: permisos, secretos, shell=True, eval, path traversal → **limpia**.
- **Prueba real §5.21**: la propia TASK-20260809-001 (flujo 1-10 completo, cerrada con gate).
- **Criterios §5.22: 23/23 cumplidos.**
- Tags: `v0.32.0-f45`.

---

## 4. Qué se instaló — inventario de lo nuevo

| Elemento | Qué es | Por qué |
|----------|--------|---------|
| `scripts/pro/ura-udo` | CLI de coordinación (bash, 600+ líneas, 9 subcomandos) | Corazón de UDO: tareas, reservas, gate, verify, status |
| `scripts/pro/ura-engineering-check` | Comprobación reglas + `--env` | Saber si la metodología está instalada y si el entorno está sano |
| `scripts/pro/ura-opencode` (modificado) | Puente TERM→Web | Enviar trabajo a la Web con contexto UDO |
| `scripts/pro/ura-ask` / `ura-chat` | Contexto UDO / chat Ollama | Consultar sin depender de conversación |
| `docs/engineering/` (4 archivos) | Metodología universal v1.1 | Reglas de ingeniería para cualquier agente |
| `~/.config/opencode/AGENTS.md` | Copia global instalada de la metodología | Web y Terminal la reciben (mecanismo nativo de opencode) |
| `deploy/engineering/AGENTS.md.global` | Copia de instalación reproducible | Instalar en cualquier máquina |
| `docs/udo/` (README, WORKFLOW, TASKS, CONFLICTS, TROUBLESHOOTING, review-pending) | Documentación definitiva | Operar sin manuales de cientos de páginas |
| `tests/udo/test_udo.sh` (35 asserts) + `tests/engineering/` (13 + 4 planes) | Suites de prueba | Validar que el sistema funciona de verdad |
| `Makefile` target `test-udo` | Integración de tests UDO en `make validate` | La validación completa no omite UDO |
| `.github/CI_POLICY.md`, `tests-ci-exclude.txt` | Referencias CI que faltaban | AGENTS.md apuntaba a archivos inexistentes |
| `docs/engineering/POSTMORTEMS.md` | 20 incidentes con causa raíz | Evidencia para mejorar el proceso |
| `motor/core/llm/_state.py`, `mantenimiento/ura_maintenance.py` (fixes) | 28 errores ruff pre-existentes resueltos | Lint 100% limpio |

## 5. Instalación de la metodología — cómo (reproducible)

1. **Fuente única**: `docs/engineering/` en el repo git.
2. **AGENTS.md del proyecto** → sección "Metodología Universal de Ingeniería" (puntero, no duplica).
3. **Copia global**: `deploy/engineering/AGENTS.md.global` → `~/.config/opencode/AGENTS.md` (mecanismo nativo de opencode; Web y Terminal comparten home).
4. **Verificación**: `ura-engineering-check` (versión en cabecera + sha256sum) → RESULTADO: OK.
5. **Reinicio**: `sudo systemctl restart opencode.service` (config no hot-reload — sin esto la Web no carga la metodología).
6. **En Mac**: misma copia (documentado A5).

## 6. Incidentes resueltos durante la sesión

| Incidente | Solución |
|-----------|----------|
| Rootfs `/` montado RO (recurrente, F14-F01) | Remount rw temporal para instalar; `--env` lo detecta ahora ANTES de trabajar |
| Sesión paralela implementó F2.2 con bug de IFS (word-splitting rompía pinning) | Fix `local IFS=','` + tests 11c |
| `stash/pop` perdió el bit +x de ura-udo (rc=126) | `chmod +x` restaurado + suite |
| TASK-014 accidental por `ura-opencode --help` | Cancelada con nota |
| Secretos viejos en secrets.env (321000) y .bashrc (TAILSCALE_AUTH_KEY, HCLOUD_TOKEN) | Línea duplicada eliminada; .bashrc pendiente de migración (requiere sudo, documentado) |
| Aliases rotos en .bashrc (`opencode`→wrapper inexistente) | Eliminados; `opencode` resuelve a `~/.opencode/bin/opencode` v1.17.7 |
| 28 errores ruff pre-existentes que CI debería detectar | Resueltos (ver §4) — comunicación inicial engañosa corregida |

## 7. Validación final (evidencia)

| Comprobación | Resultado |
|--------------|-----------|
| `tests/udo/test_udo.sh` | 35 OK, 0 FAIL |
| `tests/engineering/test_engineering.sh` | 13 OK, 0 FAIL |
| `ura-engineering-check` | OK — reglas instaladas y sincronizadas |
| `ura-engineering-check --env` | OK CON WARNINGS (rootfs ro detectado correctamente) |
| `ruff check .` | All checks passed (28 pre-existentes → 0) |
| `ruff format --check .` | 264 archivos OK |
| pytest (subconjunto) | Sin regresiones vs baseline |
| Criterios F5 §5.22 | 23/23 |
| Lote review-pending | 7/7 revisado por Ramón |
| B2 (prueba conductual) | 4/4 veredictos validados por Ramón |
| Tags | v0.30.0-f2 → v0.31.0-plan0 → v0.31.1-plan1 → v0.32.0-f45 |

## 8. Pendientes conocidos (ninguno bloqueante)

| Pendiente | Responsable | Estado |
|-----------|-------------|--------|
| Migrar secretos de `~/.bashrc` a `/etc/ura/secrets.env` + rotar TAILSCALE_AUTH_KEY | Ramón (sudo) | Documentado (tarea de seguridad aparte) |
| 16 tests Python pre-existentes fallidos (mcp/resiliencia/cli/benchmark) | investigación propia | Documentado (no regresión de la sesión) |

## 9. Principios que quedaron instalados (la "regla que resume todo")

1. El humano define la intención y los límites.
2. El plan define el trabajo propuesto.
3. El agente analiza el plan contra la realidad del código (veredicto GO/GO CON CAMBIOS/NO-GO).
4. Se detecta lo que falta y se proponen mejoras (clasificadas).
5. Se fija el plan definitivo.
6. Un agente ejecuta; otro revisa (o AUTO-REVISIÓN honesta + revisión diferida).
7. Git y la documentación conservan la evidencia.
8. Nada se declara terminado sin cumplir los mínimos y poder demostrarlo.

---

*Informe elaborado desde evidencia: git log (75 commits), expedientes UDO (21), closeouts (PLAN_0/PLAN_1/FASE5), auditorías (F3, PLAN_0, FASE5 estricta), suites (35+13).*

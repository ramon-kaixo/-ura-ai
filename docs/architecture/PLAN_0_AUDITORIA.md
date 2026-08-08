# Auditoría del PLAN 0 — Infraestructura de Ingeniería para Agentes

**Fecha**: 2026-08-08
**Tarea**: TASK-20260808-015
**Método**: §45 del Plan 0 — aplicar la metodología al propio Plan 0: leerlo entero, inspeccionar la infraestructura real (Web, Terminal, carga de reglas, UDO, ura-opencode, AGENTS.md), detectar duplicaciones/contradicciones/mecanismos innecesarios/seguridad/sincronización, proponer mejoras y entregar Plan 0 revisado.
**Veredicto**: **GO CON CAMBIOS** (ver §9)

---

## 1. Comprobación de la infraestructura real (checklist §45)

### 1.1 Configuración real de Web
- `opencode.service` (systemd, puerto 8081): `User=ramon`, `WorkingDirectory=/home/ramon/URA/ura_ia_1972`, `ExecStart=/home/ramon/.opencode/bin/opencode web`, `EnvironmentFile=/etc/ura/secrets.env`. **Activo**.
- Drop-ins hardening: `ProtectSystem=strict`, `ProtectHome=read-only`, `ReadWritePaths=/home/ramon/.openclaw /home/ramon/URA /home/ramon/.opencode /home/ramon/.local/share/opencode /home/ramon/.ura`. ⚠️ `/.openclaw` en ReadWritePaths — **referencia muerta** (OpenClaw retirado).
- Config global: `~/.config/opencode/opencode.json` — modelo `ollama/qwen2.5-coder:14b`, 6 modelos, MCP. ⚠️ **Bloque `mcp.openclaw` obsoleto** (resto de OpenClaw retirado, no limpiado).
- `~/.config/opencode/ura_context.json` — contexto compartido (no reglas).

### 1.2 Configuración real de Terminal
- Mismo binario (`~/.opencode/bin/opencode` v1.17.7), mismo home, misma config global. **Web y Terminal ya comparten config** (misma máquina).
- Sin unidad systemd (TUI manual). `/usr/local/bin/opencode` (wrapper OpenClaw) **ya eliminado**.
- `~/.bashrc` sin aliases rotos (limpiado). PATH: `~/.opencode/bin` y `~/.local/bin`.

### 1.3 Cómo se cargan actualmente las reglas
- **La única fuente de reglas es `AGENTS.md` en la raíz del repo** (51 KB, git-tracked), cargado vía WorkingDirectory del servicio.
- `CLAUDE.md` es symlink → `AGENTS.md`.
- **NO existen reglas globales de usuario** (`~/.config/opencode/AGENTS.md`, `rules/`, `instructions/` → no existen).
- No hay `opencode.json` en la raíz del repo; `deploy/opencode_asus_config.jsonc` es la copia de referencia de config global (instalada manualmente, sin checksum).

### 1.4 UDO (revisado)
- `scripts/pro/ura-udo` (544 líneas, bash puro): 7 estados, gate de integridad F2.2 (`_gate_revision` L:127-160, pinning SHAs L:146-152), AUTO-REVISIÓN automática (L:163-175), `--revisor`, enforcement de reservas (L:307-376), `commit_base` automático, `flock`, IDs únicos. 30 asserts en `tests/udo/test_udo.sh`.
- **UDO ya implementa** §25 (ejecución con reservas/commits/validación), §30 (contexto compartido `ura-udo context`), §31-32 (reservas/conflictos, `--force` auditado), §33 (degradación, AUTO-REVISIÓN en vez de fingir), §34 (trazabilidad completa), §35 (Git como fuente de verdad).

### 1.5 ura-opencode (revisado)
- `scripts/pro/ura-opencode` (58 líneas): crea TASK UDO, la pasa IN_PROGRESS con roles Web(ejecutor)/TERM(revisor), **propaga contexto** (bloque `===== CONTEXTO UDO (tarea) — léelo antes de trabajar =====`), envía vía `opencode run --attach`, al terminar `--estado REVIEW`.
- **ura-opencode ya implementa** §30 (transmisión de contexto entre agentes) y parte de §34.

### 1.6 AGENTS.md (revisado)
- Contiene: Regla Principal ASUS, Flujo de Trabajo Obligatorio, Regla Global de No Regresión, Regla Transversal (cierre de fases: validación, docs, baseline, tag, acta), ADR-007 (núcleo), Naming, Security, Code Style, Reglas Arquitectónicas, sección UDO completa (F1+F2+F2.2 cerradas, F3 NO-GO, tag v0.30.0-f2), Policy Exclusiones CI, CI/CD Policy.
- ⚠️ **Referencias colgantes**: `.github/tests-ci-exclude.txt` (L:675) y `.github/CI_POLICY.md` (L:683) **no existen** en el repo (solo `ci.yml`, `publish.yml`, `release.yml`).

### 1.7 Qué existe ya (inventario)
- `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md` — **directiva permanente de Ramón** con clasificación MÍNIMOS/MEJORAS/FUERA DE ALCANCE, regla de descubrimiento, regla de cierre, informe final obligatorio. **Cubre el núcleo de §15-16, §19, §26 del Plan 0.**
- `docs/udo/AUDITORIA-F3-2026-08-08.md` — precedente GO/NO-GO (F3 → NO-GO por sobreingeniería: la máquina de estados no resolvía los 5 modos de fallo reales).
- `docs/udo/CLOSEOUT-F2-2026-08-08.md` §13 — cierre formal F1-F3 + tag.
- `docs/udo/templates/task_template.md` — único template de proceso (expediente UDO).
- `docs/architecture/` — ~400 archivos: ADRs (007, 011, 028, 029...), propuestas FASE*, closeouts, GOVERNANCE.md, RC_READINESS.md, CONTRACTS_FROZEN.md, INVARIANTS.md.
- `.opencode/plans/` — 13 planes/closeouts de fases anteriores (capa11, F3_PLAN_TELEMETRIA, ROADMAP...).
- `docs/pro/sesiones/` — 29 registros diarios (memoria operativa).
- `bitacora/_template.md` — template de bitácora.

---

## 2. Qué coincide (el plan acierta)

| § Plan 0 | Estado real | Evidencia |
|----------|-------------|-----------|
| §7 Memoria = Git + docs (no conversación) | ✅ **Ya es así** | UDO: "la conversación NO es fuente de verdad"; expedientes + commits en Git |
| §25 Ejecución: plan aprobado → reservas → ejecución → commits → validación | ✅ **Ya implementado** | ura-udo (reserva, commit_base, verify, gate) |
| §27-29 Alternancia programador/revisor | ✅ **Ya implementado** | Modelo dual UDO + AUTO-REVISIÓN honesta |
| §30 Contexto entre agentes | ✅ **Ya implementado** | `ura-opencode` inyecta CONTEXTO UDO; `ura-udo context` |
| §31-32 Reservas y conflicto | ✅ **Ya implementado** | enforcement + `check` + `--force` auditado |
| §33 Degradación sin fingir revisión | ✅ **Ya implementado** | AUTO-REVISIÓN automática (F2.2) |
| §34-35 Trazabilidad y Git como fuente de verdad | ✅ **Ya implementado** | expediente + commits + pinning |
| §15 Clasificación de descubrimientos | ✅ **Directiva previa** | REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md |
| §46 Mejora continua del proceso | ✅ **Precedente** | F3 NO-GO → F2.2 (misma garantía, menos código) |

**Conclusión parcial**: el Plan 0 **describe en gran parte lo que UDO ya implementa**. La novedad real no es la maquinaria (ya existe), sino: (a) la **regla universal "analizar antes de ejecutar"** como regla de carga global para cualquier agente OpenCode; (b) la **documentación universal** (docs/engineering/); (c) la **comprobación de instalación** de las reglas; (d) el **versionado** de la metodología; (e) los **10 casos de prueba** reales.

---

## 3. Duplicaciones detectadas

| D1 | `REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md` (existente) **duplica** §15 (clasificación), §16 (mínimos), §19 (NO HACER), §26 (problemas durante ejecución) del Plan 0 | La documentación universal (§36) debe **referenciar** esa directiva, no recrearla. |
| D2 | `AGENTS.md` sección UDO (51 KB) + `docs/udo/README.md` + Plan 0 §30-35 | §38 ya ordena "AGENTS.md no duplica la metodología universal" — pero la frontera actual es borrosa. Definir: UDO = mecanismo (queda en AGENTS.md/README); Engineering Process = metodología universal (docs/engineering/). |
| D3 | `deploy/opencode_asus_config.jsonc` (referencia) vs `~/.config/opencode/opencode.json` (real) vs `~/.opencode/opencode.json` (residuo) | 3 copias de config global, **ninguna sincronización automática** (§40-41 vacíos en la práctica). |

---

## 4. Contradicciones detectadas

| C1 | §36 pide `PLAN_REVIEW_TEMPLATE.md` y §22-23 el "ANÁLISIS DEL PLAN" con veredicto GO/GO CON CAMBIOS/NO-GO | ✅ Coherente entre sí — pero **no existe plantilla hoy**; es trabajo nuevo legítimo. |
| C2 | §37 "reglas globales" vs realidad: **no existe infraestructura de reglas globales en OpenCode** (solo AGENTS.md del repo) | El plan asume que "configurar reglas globales" es trivial; en opencode la vía es AGENTS.md del proyecto + config global `~/.config/opencode/opencode.json` (que NO se lee como reglas, solo config técnica). **Falta mecanismo concreto**: o AGENTS.md global de usuario o `instructions` en config. Hay que decidirlo en implementación (el plan no lo especifica). |
| C3 | §43 "no depender de una máquina concreta" vs §39 "Terminal se utiliza para instalar" | No es contradicción real (instalación ≠ dependencia de diseño), pero conviene redactar la independencia como "la metodología vive en el repo (git), no en la máquina". |
| C4 | §41 "fuente única Web/Terminal" — **en la práctica ya comparten config** (misma máquina, mismo home, mismo binario) | El riesgo de divergencia real es: (a) el **servicio systemd** (Web) lee AGENTS.md del repo por WorkingDirectory; (b) Terminal lanzado desde cualquier cwd podría no cargarlo. **Sincronizar = garantizar que ambos carguen el mismo AGENTS.md/methodology**. |
| C5 | §50 obliga a que todo plan responda 11+9 preguntas; el propio Plan 0 **no las responde explícitamente** | Autoaplicación pendiente — ver §6 (Plan 0 revisado debe cumplirlo). |

---

## 5. Riesgos y seguridad detectados

| R1 | ⚠️ **Secretos en `.bashrc`**: `TAILSCALE_AUTH_KEY` (L:121) y `HCLOUD_TOKEN` (L:122) hardcodeados | **DESCUBRIMIENTO de seguridad** (§11). Deben migrarse a `/etc/ura/secrets.env` (600/640) y el valor de `TAILSCALE_AUTH_KEY` es un auth-key reutilizable — **rotar**. Fuera del alcance de Plan 0 (PENDIENTE/FUERA DE ALCANCE — decidir). |
| R2 | `mcp.openclaw` obsoleto en config global de opencode | NECESARIO limpiar durante implementación (resto de retirada OpenClaw). |
| R3 | `ReadWritePaths=.../.openclaw` en drop-in hardening del servicio | NECESARIO limpiar (referencia muerta). |
| R4 | `~/.opencode/opencode.json` y `~/.opencode/package.json` (plugin 1.15.12) residuos de instalación previa | MEJORA limpiar. |
| R5 | `ura_opencode_watchdog.sh` es un stub (`exit 0`) | DESCUBRIMIENTO: script muerto; documentar o retirar. |
| R6 | AGENTS.md 51 KB crece sin control; referencias colgantes (`.github/tests-ci-exclude.txt`, `.github/CI_POLICY.md` no existen) | NECESARIO: el Plan 0 §38 (AGENTS.md → solo específico de URA) **es la solución**: mover metodología universal a docs/engineering/ y dejar AGENTS.md como puntero. |
| R7 | No existe verificación automática de reglas instaladas (§40) — hoy imposible saber si Web y Terminal reciben la misma metodología | Es el **gap técnico real** del plan. |

---

## 6. Qué nos hemos dejado (hallazgos de la investigación)

| F1 | El plan asume "reglas globales de OpenCode" como si existiera ese mecanismo; **la vía real es AGENTS.md (por proyecto) + config global**. El Plan 0 debe definir explícitamente: (a) `docs/engineering/` referenciado desde AGENTS.md; (b) un **AGENTS.md global de usuario** (`~/.config/opencode/AGENTS.md`) con la metodología universal para cualquier repo futuro; (c) comprobación de sincronización. |
| F2 | **No existe PLAN_TEMPLATE ni PLAN_REVIEW_TEMPLATE** — son el entregable con más valor del plan (los 10 casos de prueba dependen de ellos). |
| F3 | §44 casos 7-10 (degradación, conflicto, alcance, mejora) **ya son probables con UDO** (tests 5-8, 11, 19 de test_udo.sh) — la implementación debe reutilizarlos, no crear casos duplicados. |
| F4 | El criterio de cierre §48 exige "Web aplica metodología" — pero **la Web está atendida por el modelo qwen2.5-coder:14b** con herramientas; la comprobación de "aplica la metodología" no puede ser automática del todo (es conducta LLM) → debe ser: reglas presentes + verificable (checksum) + evidencia en expedientes (AUTO-REVISIÓN, análisis previo registrado). |
| F5 | Versionado §42: la metodología debe versionarse **como documento git-tracked con fecha/versión en cabecera** (no hace falta más). |
| F6 | §47 (fuera de alcance) está bien — coherente con la regla anti-sobreingeniería §20 y con el NO-GO F3. |

---

## 7. Propuestas de simplificación

| S1 | **No crear un sistema de carga de reglas propio.** Usar el mecanismo nativo de opencode: AGENTS.md (proyecto) + `~/.config/opencode/AGENTS.md` (global usuario). Nada de plugins/custom loader. |
| S2 | `ROLE_MODEL.md` (§36) puede **fusionarse en ENGINEERING_PROCESS.md** (sección roles) — el modelo dual ya está documentado en UDO; un archivo aparte de 5 líneas es ceremonia. → docs/engineering/ queda con 3 archivos + README. |
| S3 | La comprobación §40: **script bash pequeño** (`scripts/pro/ura-engineering-check`) que compare: versión en cabecera de ENGINEERING_PROCESS.md, existencia de los archivos, checksum de la copia instalada vs repo. Estilo ura-udo (flock, bash puro). Sin BD. |
| S4 | Los 10 casos §44: reutilizar `tests/udo/test_udo.sh` como base para casos 7-10; los casos 1-6 (análisis de plan) son **pruebas de conducta LLM** → plantilla de revisión + veredicto, evaluables manualmente con un plan de ejemplo por caso. |
| S5 | §42 versionado: cabecera `<!-- Engineering Process vX.Y -->` + git tag al cerrar Plan 0. Nada más. |

---

## 8. Clasificación de descubrimientos (según §15 del propio Plan 0)

| Id | Descubrimiento | Clase | Decisión propuesta |
|----|----------------|-------|--------------------|
| D1-D3 | Duplicaciones con REGLA-PLAN y configs | **NECESARIO** | Referenciar, no recrear; definir frontera UDO/method |
| C1 | Templates de plan/revisión inexistentes | **OBLIGATORIO** | Crear PLAN_TEMPLATE.md + PLAN_REVIEW_TEMPLATE.md |
| C2/C4 | Mecanismo de reglas globales no definido | **OBLIGATORIO** | Definir: AGENTS.md proyecto + AGENTS.md global usuario + check |
| C5 | Plan 0 no se autoaplica §50 | **OBLIGATORIO** | El Plan 0 revisado debe responder sus 20 preguntas |
| R1 | Secretos en .bashrc | **DESCUBRIMIENTO** | Documentar; migrar a secrets.env (PENDIENTE — no es alcance Plan 0, o tarea aparte) |
| R2/R3 | Restos OpenClaw en config y drop-in | **NECESARIO** | Limpiar durante implementación |
| R4/R5 | Residuos ~/.opencode, watchdog stub | **MEJORA** | Limpiar/documentar si autorizado |
| R6 | AGENTS.md inflado + referencias colgantes | **NECESARIO** | §38 correcto: mover metodología a docs/engineering/, AGENTS.md → puntero |
| R7 | Sin verificación de instalación | **OBLIGATORIO** | script ura-engineering-check |
| F4 | "Web aplica metodología" no 100% verificable | **NECESARIO** | Criterio de cierre = reglas presentes + checksum + evidencia en expedientes |
| — | F3 NO-GO (máquina de estados) no debe repetirse | **OBLIGATORIO** (regla) | Plan 0 no construye máquina de estados de revisión; reutiliza UDO |

---

## 9. VEREDICTO

# **GO CON CAMBIOS**

El plan es sólido, bien estructurado y su núcleo (analizar antes de ejecutar, clasificar descubrimientos, mínimos, NO HACER, trazabilidad, revisión honesta) está **en gran parte ya implementado en UDO y en la directiva REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS**. Ejecutarlo tal cual duplicaría mecánica existente.

**Cambios que deben incorporarse antes de implementar:**

1. **Definir el mecanismo real de reglas globales** (§37): AGENTS.md del proyecto + AGENTS.md global de usuario + verificación. Sin plugins ni sistemas de carga propios.
2. **Documentación universal = referenciar, no duplicar** (§36): ENGINEERING_PROCESS.md cita REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md y docs/udo/README.md como fuentes; ROLE_MODEL fusionado en ENGINEERING_PROCESS.
3. **Plan 0 debe autoaplicarse §50**: el Plan 0 revisado (versión 1.1) responde las 20 preguntas.
4. **Limpiar restos**: mcp.openclaw (config global), ReadWritePaths .openclaw (drop-in), referencias colgantes AGENTS.md, residuos ~/.opencode.
5. **Comprobación de instalación** (§40): script bash `ura-engineering-check` (versión + checksum + presencia), no BD.
6. **Criterio de cierre §48 operativizado**: reglas presentes + checksum + evidencia en expedientes UDO (análisis previo, AUTO-REVISIÓN) — "Web aplica" se demuestra por registro, no por observación de conducta.
7. **Secretos del .bashrc**: documentar como descubrimiento; migración a secrets.env como tarea aparte (no dentro de Plan 0).
8. **No repetir el NO-GO F3**: no crear máquina de estados de revisión nueva; reutilizar el gate F2.2 y AUTO-REVISIÓN existentes.

**No es NO-GO** porque: no hay problema que impida ejecutar; el plan es compatible con la infraestructura real; los cambios son acotados y no alteran la intención.

---

## 10. Referencias de la auditoría

- Infraestructura real: `~/.config/opencode/opencode.json`, `~/.opencode/`, `deploy/opencode.service`, `deploy/opencode_asus_config.jsonc`, `scripts/pro/ura-opencode`, `scripts/pro/ura-udo`, `AGENTS.md`
- Existentes: `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`, `docs/udo/AUDITORIA-F3-2026-08-08.md`, `docs/udo/CLOSEOUT-F2-2026-08-08.md`, `docs/udo/README.md`, `docs/udo/templates/task_template.md`, `tests/udo/test_udo.sh`, `.opencode/plans/`
- Plan auditado: `docs/architecture/PLAN_0.md` (referencia maestra, versión original del autor)

**Auditor realizado por**: TERM (TASK-20260808-015) — auditoría adversa de infraestructura, no implementación.
**Pendiente**: decisión de Ramón sobre el Plan 0 revisado (aprobación → implementación con los 8 cambios).

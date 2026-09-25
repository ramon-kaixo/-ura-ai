# PLAN 0 — REVISADO v1.1 — Infraestructura de Ingeniería para Agentes de Programación

**Estado**: REVISADO — propuesto para aprobación (pendiente decisión Ramón)
**Fecha**: 2026-08-08
**Versión**: 1.1 (incorpora los 8 cambios de `docs/architecture/PLAN_0_AUDITORIA.md`)
**Base**: `docs/architecture/PLAN_0.md` (v1.0, referencia maestra original del autor)
**Tarea**: TASK-20260808-015
**Cómo se aplica**: el §50 del Plan 0 exige que todo plan responda las 20 preguntas — este documento las responde (ver §51). Es el primer plan autoaplicado.

---

## 0. Objetivo (sin cambios respecto a v1.0)

Crear una infraestructura de ingeniería que establezca cómo debe trabajar un agente de programación, independientemente de que sea OpenCode Web, OpenCode Terminal o, en el futuro, otra herramienta.

La infraestructura debe conseguir que, cuando se entregue un plan:
**NO pase directamente a programar.** Primero debe: entender la intención; leer todo el plan; conocer el contexto; inspeccionar el estado real del proyecto; revisar documentación y decisiones anteriores; buscar problemas, cosas que falten, contradicciones, riesgos, casos extremos; detectar trabajo prematuro; proponer mejoras; separar lo obligatorio de lo opcional; revisar qué NO debe hacerse; devolver su valoración; corregir el plan cuando sea necesario; y solo después ejecutar.

La finalidad es que el agente no sea un mero ejecutor de instrucciones, sino un ingeniero que analiza antes de actuar.

---

## 1. Cambios incorporados (respecto a v1.0)

| # | Cambio (de la auditoría) | Dónde queda en v1.1 |
|---|--------------------------|---------------------|
| 1 | Mecanismo real de reglas globales: AGENTS.md del proyecto + AGENTS.md global de usuario + verificación. Sin plugins ni loaders propios | §37, §40, §41 |
| 2 | Documentación universal referenciando (no duplicando) REGLA-PLAN-MINIMOS y UDO; ROLE_MODEL fusionado en ENGINEERING_PROCESS | §36 |
| 3 | Plan 0 autoaplicado: responde las 20 preguntas del §50 | §51 |
| 4 | Limpieza de restos: `mcp.openclaw` (config global), `ReadWritePaths=.openclaw` (drop-in), referencias colgantes de AGENTS.md, residuos `~/.opencode/` | §52 (implementación) |
| 5 | Comprobación de instalación: script bash `ura-engineering-check` (versión + checksum + presencia), sin BD | §40 |
| 6 | Criterio de cierre operativizado: reglas presentes + checksum + evidencia en expedientes UDO | §48 |
| 7 | Secretos de `.bashrc` (TAILSCALE_AUTH_KEY, HCLOUD_TOKEN) → descubrimiento; migración a `/etc/ura/secrets.env` como **tarea aparte** (fuera del alcance de implementación) | §53 (pendiente) |
| 8 | No repetir el NO-GO F3: reutilizar gate F2.2 y AUTO-REVISIÓN; NO crear máquina de estados de revisión nueva | §27-29, §33, §52 |

El resto de secciones del v1.0 (§1-§50) se mantienen en su espíritu y texto, con los ajustes que se indican a continuación.

---

## 2. Secciones ajustadas

### §7 Memoria (ajuste)
Se mantiene. La infraestructura utiliza Git + documentación + decisiones + planes + closeouts como memoria. No depende de conversaciones, memoria implícita del LLM, explicaciones verbales ni información no registrada.
**Ya implementado por UDO** (expedientes + commits + `context`). Este plan no crea memoria nueva.

### §15 Clasificación de descubrimientos (ajuste)
Se mantiene la tabla del v1.0. **Referencia obligatoria**: `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md` (directiva permanente de Ramón). La documentación universal debe citarla como fuente, no recrearla.

### §27-29 Alternancia programador/revisor (ajuste)
Se mantiene el modelo (preparador → ejecutor → revisor → corrección → validación).
**No se crea máquina de estados nueva** (lección del NO-GO F3). Se reutiliza:
- UDO: estados PLANNED → IN_PROGRESS → REVIEW → DONE (+BLOCKED/CONFLICT/CANCELLED)
- Gate de integridad F2.2 (`_gate_revision`): commits registrados, pinning de SHAs, árbol limpio
- AUTO-REVISIÓN automática cuando no hay revisor independiente
- `--force` como excepción auditada

### §33 Degradación (ajuste)
Se mantiene. Si el revisor no está disponible: NO se finge la revisión. La tarea queda PENDIENTE DE REVISIÓN o usa AUTO-REVISIÓN (marcada automáticamente por la herramienta). **Ya implementado por UDO F2.2.**

### §36 Documentación universal (CAMBIADO — cambio #2)

```
docs/engineering/
├── README.md                   → índice + enlaces a fuentes (UDO, REGLA-PLAN, AGENTS.md)
├── ENGINEERING_PROCESS.md      → el ciclo completo (v1.0, versionado en cabecera)
│                                 + sección de roles (ROLE_MODEL fusionado)
├── PLAN_TEMPLATE.md            → cómo preparar un plan (las 11 preguntas del plan)
└── PLAN_REVIEW_TEMPLATE.md     → cómo analizarlo OpenCode (ANÁLISIS DEL PLAN + veredicto GO/GO CON CAMBIOS/NO-GO + las 9 preguntas de OpenCode)
```

- **ROLE_MODEL.md se elimina**: su contenido (preparador/ejecutor/revisor, alternancia, Web/TERM, futuro 2×Terminal) es una sección de ENGINEERING_PROCESS.md. No se duplica.
- ENGINEERING_PROCESS.md **referencia** (no copia): `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`, `docs/udo/README.md`, `AGENTS.md`. Los mecanismos ya existentes (UDO, gate, AUTO-REVISIÓN) se citan con enlace, no se reimplementan.
- PLAN_TEMPLATE.md define las 11 preguntas obligatorias del plan (§50, parte plan).
- PLAN_REVIEW_TEMPLATE.md define las 9 preguntas de OpenCode + ANÁLISIS DEL PLAN (§22) + veredicto (§23).

### §37 Reglas globales de OpenCode (CAMBIADO — cambio #1)

La metodología universal se entrega a todo agente OpenCode mediante los mecanismos **nativos** de OpenCode (sin plugins, sin loader propio):

1. **`AGENTS.md` del proyecto** (raíz del repo, git-tracked): referencia a la metodología universal → "Aplicar la metodología universal de ingeniería (ver docs/engineering/ENGINEERING_PROCESS.md) y, además, estas restricciones específicas de URA."
2. **`~/.config/opencode/AGENTS.md` (global de usuario)**: contiene la metodología universal (resumen ejecutivo + enlace a la fuente en el repo) para que **cualquier** proyecto futuro de OpenCode en esta máquina la reciba. Es la copia de instalación; el repo es la fuente de verdad.
3. La regla universal contiene: análisis previo; búsqueda de omisiones/riesgos/contradicciones/casos extremos; mínimos; críticos; NO HACER; clasificación de descubrimientos; no ejecutar fases futuras; trazabilidad; revisión; honestidad sobre validaciones.

La **config global `~/.config/opencode/opencode.json` NO es el lugar** de las reglas (es configuración técnica: modelos, MCP, permisos). Solo se toca para limpiar restos (§52).

### §40 Comprobación de reglas instaladas (CAMBIADO — cambio #5)

Script bash puro **`scripts/pro/ura-engineering-check`** (estilo ura-udo: flock, sin BD, sin dependencias):

| Qué comprueba | Cómo |
|---------------|------|
| Versión instalada | Cabecera de `docs/engineering/ENGINEERING_PROCESS.md` (p.ej. `v1.0`) |
| Presencia | Existencia de los 4 archivos de docs/engineering/ + AGENTS.md global |
| Sincronización Web/Terminal | Checksum (sha256sum) de la copia global `~/.config/opencode/AGENTS.md` vs fuente del repo `docs/engineering/` (o vs archivo de referencia versionado) |
| Diferencias entre instalaciones | Comparación checksum instalado vs versionado en repo; reporta diff |

Salida: `OK` / `DESINCRONIZADO` / `FALTA` con detalle. No depende de revisar archivos manualmente.

### §41 No duplicar reglas entre Web y Terminal (ajuste)

**Hecho real de la infraestructura**: Web y Terminal ya comparten binario, home y config global (misma máquina). La única divergencia posible es el cwd de arranque: el servicio systemd (Web) fija `WorkingDirectory=/home/ramon/URA/ura_ia_1972` (carga AGENTS.md del repo); Terminal lanzado desde otro cwd podría no cargarlo.
**Solución**: la regla universal vive en `~/.config/opencode/AGENTS.md` (global) + AGENTS.md del repo. `ura-engineering-check` verifica que ambas copias coinciden con la fuente. Fuente única = repo (git).

### §42 Versionado (ajuste)

- Cabecera en ENGINEERING_PROCESS.md: `<!-- Engineering Process v1.0 -->`
- Modificaciones importantes → bump de versión + entrada en el propio archivo (changelog corto) + commit.
- Al cerrar Plan 0: tag git (propuesto: `v0.31.0-plan0`).
- Permite saber bajo qué metodología se realizó un trabajo (los expedientes UDO pueden citar la versión).

### §43 Compatibilidad futura (sin cambios)
Plan 0 no depende de modelo, Qwen, Web, Terminal, Ollama ni máquina concreta. La metodología vive en el repo (git) y se instala como AGENTS.md global; es portable por diseño (cambio #1 refuerza esto: la instalación es copiar un archivo).

### §44 Pruebas reales (ajuste)

| Caso | Cómo se prueba | Estado |
|------|----------------|--------|
| 1 — Plan correcto → ejecutable | Plan de ejemplo + PLAN_REVIEW_TEMPLATE → GO | Nuevo (template) |
| 2 — Plan incompleto → detecta falta | Plan de ejemplo incompleto → análisis detecta omisiones | Nuevo (template) |
| 3 — Plan contradictorio → señala contradicción | Plan de ejemplo contradictorio → análisis | Nuevo (template) |
| 4 — Plan con fase posterior → detecta adelanto | Plan con trabajo de otra fase → análisis | Nuevo (template) |
| 5 — Plan excesivamente complejo → simplificación | Plan de ejemplo sobreingeniería → análisis propone simplificación | Nuevo (template) |
| 6 — Plan con requisito oculto → lo detecta en el código | Plan que asume algo inexistente → inspección del código | Nuevo (template) |
| 7 — Agente ejecutor parado → degradación | **Reutilizar UDO**: AUTO-REVISIÓN, tarea queda REVIEW/PENDIENTE (test_udo.sh esc. 11d) | ✅ Ya cubierto |
| 8 — Conflicto de archivos → detectar antes de modificar | **Reutilizar UDO**: `check`/reserva (test_udo.sh esc. 5-8) | ✅ Ya cubierto |
| 9 — Cambio necesario fuera del alcance → detenerse y solicitar | **Reutilizar UDO**: regla §31-32 + `--force` auditado (test_udo.sh esc. 19) | ✅ Ya cubierto |
| 10 — Mejora opcional → distinguir de requisito | **Reutilizar** clasificación REGLA-PLAN + PLAN_REVIEW_TEMPLATE | ✅ Parcial |

Los casos 1-6 se prueban con los templates (manuales, evaluados por Ramón o por revisión cruzada); los 7-10 reutilizan `tests/udo/test_udo.sh` sin duplicar.

### §48 Criterio de cierre (CAMBIADO — cambio #6)

Plan 0 se cierra cuando se demuestra **operativamente**:

1. `docs/engineering/` existe (4 archivos) con versión en cabecera.
2. `~/.config/opencode/AGENTS.md` instalado y **checksum igual** a la fuente (verificado por `ura-engineering-check` → OK).
3. `AGENTS.md` del repo referencia la metodología (puntero, sin duplicar).
4. `ura-engineering-check` existe, es ejecutable y devuelve OK.
5. Los 10 casos de prueba están documentados y ejecutados (1-6 con templates; 7-10 con test_udo.sh).
6. Evidencia en expedientes UDO: al menos un trabajo real (p.ej. la propia implementación del Plan 0) muestra: análisis previo registrado, clasificación, veredicto y trazabilidad.
7. Auditoría final adversa (este mismo proceso aplicado al resultado) + closeout + tag.

"No cierra porque los archivos existen": cierra porque hay evidencia verificable de recepción (checksum) y de aplicación (expedientes).

---

## 3. Secciones sin cambios (referencia a v1.0)

§1 Principio rector · §2 La regla más importante (nunca ejecutar un plan sin análisis previo) · §3 Qué debe recibir OpenCode · §4-6 Obligaciones 1-3 (intención, leer plan completo, contexto) · §8-14 Obligaciones 4-10 (inspeccionar código, buscar lo que falta, contradicciones, riesgos, casos extremos, trabajo prematuro, mejoras) · §16-18 Mínimos, puntos críticos, comportamiento esperado · §19-21 NO HACER, anti-sobreingeniería, reutilización · §22-24 Análisis del plan, veredicto, el usuario decide · §25-26 Ejecución y problemas durante ejecución · §30-32 Contexto entre agentes, zonas de trabajo, reserva y conflicto (UDO) · §34-35 Trazabilidad, Git como fuente de verdad · §38 AGENTS.md = reglas específicas de URA · §39 Integración desde Terminal (instalación reproducible, sin segundo sistema de agentes) · §45 Auditoría del Plan 0 (la de este documento, completada) · §46 Mejora continua del proceso (no modificar por incidentes aislados; evidencia de valor) · §47 Lo que queda fuera (sin BD, servidores, dispatchers, paneles, colas, multiagente autónomo, memoria vectorial, gestor de proyectos, agente auditor permanente, cloud) · §49 Secuencia definitiva · §50 Regla permanente de las 20 preguntas.

---

## 4. Plan 0 autoaplicado — respuesta a las 20 preguntas del §50 (cambio #3)

### Del plan (las 11 que todo plan debe responder)

| Pregunta | Respuesta (Plan 0 v1.1) |
|----------|-------------------------|
| ¿QUÉ QUIERO CONSEGUIR? | Que todo agente de programación (Web, Terminal, futuro) analice críticamente un plan contra la realidad del código antes de ejecutar, y que eso sea verificable y reproducible. |
| ¿POR QUÉ? | Porque un agente que solo ejecuta instrucciones repite errores que un análisis previo detecta (F3 durante F2; omisiones; contradicciones; sobreingeniería; fases adelantadas). |
| ¿QUÉ CONTEXTO EXISTE? | UDO (reservas, gate F2.2, AUTO-REVISIÓN, trazabilidad) ya implementa el 70% de la maquinaria. REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md es directiva permanente. F3 fue NO-GO por sobreingeniería. No existen templates de plan/revisión ni reglas globales. |
| ¿QUÉ TIENE QUE HACER? | Crear docs/engineering/ (4 archivos, ROLE_MODEL fusionado); instalar AGENTS.md global (con copia versionada en deploy/); hacer de AGENTS.md del repo un puntero; crear `ura-engineering-check`; limpiar restos (§52); documentar y ejecutar los 10 casos de prueba; auditoría final + closeout + tag. |
| ¿QUÉ ES MÍNIMO? | (a) docs/engineering/ con ENGINEERING_PROCESS v1.0 versionado; (b) AGENTS.md global instalado y verificado por checksum; (c) AGENTS.md del repo referencia la metodología; (d) `ura-engineering-check` OK; (e) 10 casos de prueba documentados; (f) evidencia en expediente UDO; (g) auditoría final + closeout + tag. |
| ¿QUÉ ES CRÍTICO? | No duplicar mecanismos existentes (UDO, REGLA-PLAN); no crear máquina de estados de revisión (lección F3); no crear BD/servicios/plugins de carga; no tocar AGENTS.md sin mantenerlo como puntero; trazabilidad íntegra; honestidad de validaciones (AUTO-REVISIÓN); reversibilidad (borrar docs/engineering/ + AGENTS.md global + script deja URA intacta). |
| ¿CÓMO DEBE COMPORTARSE? | Tras Plan 0: cualquier agente OpenCode que reciba un plan produce análisis previo (ANÁLISIS DEL PLAN + veredicto) antes de tocar código; los expedientes UDO registran análisis, clasificación y veredicto; `ura-engineering-check` confirma la instalación de reglas en segundos; Web y Terminal aplican la misma metodología; la degradación (agente parado) queda marcada, nunca fingida. |
| ¿QUÉ NO DEBE HACER? | No crear BD, servidor, dispatcher, panel, cola, multiagente autónomo, memoria vectorial, gestor de proyectos, agente auditor permanente, infraestructura cloud. No reimplementar UDO. No crear sistema de carga de reglas propio. No tocar secretos (migración .bashrc = tarea aparte). No instalar timers de mutmut (pendiente de decisión). No modificar reglas universales sin bump de versión. |
| ¿QUÉ ESTÁ FUERA DE ALCANCE? | Migración de secretos .bashrc→secrets.env (tarea aparte documentada §53); decisión timers ura-mutmut; cualquier mejora del motor de URA; F4/F5; limpieza de residuos opcionales no listados en §52. |
| ¿CÓMO SE VALIDARÁ? | `ura-engineering-check` OK (checksum); 10 casos de prueba (1-6 con templates, 7-10 reutilizando test_udo.sh 30/30); make validate sin regresiones; auditoría final adversa (proceso §45 aplicado al resultado); revisión cruzada o AUTO-REVISIÓN documentada. |
| ¿CÓMO SE SABRÁ QUE ESTÁ TERMINADO? | Criterio de cierre §48 (7 puntos verificables) cumplido + closeout `docs/architecture/PLAN_0_CLOSEOUT.md` + tag `v0.31.0-plan0` + árbol limpio. |

### Y OpenCode añade (las 9 preguntas del análisis)

| Pregunta | Respuesta (resultado de la auditoría v1.0 → v1.1) |
|----------|----------------------------------------------------|
| ¿QUÉ FALTA? | Mecanismo de reglas globales definido (§37 — cambio #1); templates de plan/revisión (no existían); comprobación de instalación (§40 — cambio #5); autoaplicación del §50 (este §51). |
| ¿QUÉ ESTÁ MAL? | Reglas solo en AGENTS.md del repo (no globales); config global con resto `mcp.openclaw`; drop-in hardening con `ReadWritePaths=.openclaw` muerto; referencias colgantes en AGENTS.md (`.github/CI_POLICY.md`, `.github/tests-ci-exclude.txt` no existen); `~/.opencode/` con residuos; watchdog stub. |
| ¿QUÉ CONTRADICCIONES HAY? | "Reglas globales" asumidas como mecanismo existente (no lo es — se resolvió con cambio #1); Plan 0 v1.0 no se autoaplicaba §50 (resuelto en §51); la frontera AGENTS.md (51 KB) vs metodología universal era borrosa (resuelto: AGENTS.md = puntero). |
| ¿QUÉ RIESGOS EXISTEN? | Divergencia Web/Terminal por cwd (resuelto con AGENTS.md global + check); secretos en .bashrc (documentado, tarea aparte); sobreingeniería de la propia infraestructura (mitigado: regla anti-sobreingeniería §20 + cambios 1, 2, 8); AGENTS.md inflado (mitigado: puntero). |
| ¿QUÉ CASOS EXTREMOS FALTAN? | Web parada (ya cubierto: degradación UDO); Terminal sin cwd del repo (cubierto por AGENTS.md global); checksum desincronizado (cubierto por ura-engineering-check); segundo agente Terminal futuro (cubierto por instalación idéntica). |
| ¿QUÉ SE PUEDE SIMPLIFICAR? | ROLE_MODEL fusionado en ENGINEERING_PROCESS (cambio #2); comprobación = script bash simple (cambio #5); sin máquina de estados (cambio #8); casos 7-10 reutilizan test_udo.sh. |
| ¿QUÉ SE PUEDE MEJORAR? | Versionado en cabecera + changelog (cambio §42); criterio de cierre verificable (cambio #6); referenciar en vez de duplicar (cambio #2). |
| ¿QUÉ NO DEBERÍAMOS HACER? | Lo del §47 + no crear loader de reglas + no tocar secrets.env en esta fase + no instalar mutmut. |
| ¿QUÉ PERTENECE A OTRA FASE? | Migración de secretos .bashrc (tarea de seguridad aparte); F4/F5; mejoras del motor; decisión de timers. |

---

## 5. Implementación (orden propuesto — solo tras aprobación)

```
PLAN_0_REVISADO aprobado
      ↓
1. docs/engineering/ (4 archivos, v1.0, ROLE_MODEL fusionado)
2. AGENTS.md del repo → sección "Metodología universal" como puntero (§38)
3. Copia de instalación: deploy/engineering/AGENTS.md.global (versión de referencia)
   → instalar como ~/.config/opencode/AGENTS.md (reproducible, §39)
4. scripts/pro/ura-engineering-check (bash, flock, checksum)
5. Limpieza §52 (config global, drop-in hardening, refs colgantes, residuos)
6. Casos de prueba 1-6 (templates) + 7-10 (test_udo.sh)
7. Auditoría final + closeout + tag v0.31.0-plan0
```

## 6. Limpieza de restos (implementación, cambio #4 — §52)

| Resto | Dónde | Acción |
|-------|-------|--------|
| `mcp.openclaw` | `~/.config/opencode/opencode.json` L:69 | ⚠️ PENDIENTE — rootfs ro + requiere sudo. Eliminar bloque (config no versionada; editar con cuidado + backup) |
| `ReadWritePaths=.../.openclaw` | `/etc/systemd/system/opencode.service.d/hardening.conf` | ⚠️ PENDIENTE — requiere sudo Ramón. Eliminar ruta muerta |
| `.github/tests-ci-exclude.txt`, `.github/CI_POLICY.md` | AGENTS.md L:675/683 | ✅ RESUELTO — archivos creados (2026-08-08) |
| `~/.opencode/opencode.json` + `package.json` (plugin 1.15.12) | `~/.opencode/` | ⚠️ PENDIENTE — residuos de instalación previa; verificar si el binario los usa antes de borrar |
| `ura_opencode_watchdog.sh` | `deploy/` | ✅ Documentado — stub `exit 0` es desactivación deliberada; solo lo referencia plist macOS (launchd, no systemd) |

## 7. Pendientes documentados (fuera del alcance de implementación)

- §53 **Seguridad**: `TAILSCALE_AUTH_KEY` y `HCLOUD_TOKEN` hardcodeados en `~/.bashrc:121-122` → migrar a `/etc/ura/secrets.env` y **rotar** `TAILSCALE_AUTH_KEY` (auth-key reutilizable). Tarea aparte (requiere sudo).
- Decisión: timers `deploy/timers/ura-mutmut.*` (integrar o retirar).
- Referencias colgantes de CI (decisión de mantenimiento, puede resolverse en §52).

---

*Fin del Plan 0 revisado v1.1 — pendiente de aprobación de Ramón. Al aprobar, se ejecuta el orden de implementación §5. El v1.0 sigue como referencia maestra original en `docs/architecture/PLAN_0.md`.*

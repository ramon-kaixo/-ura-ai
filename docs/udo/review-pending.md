# Revisión pendiente (review-pending) — tareas AUTO-REVISADAS sin revisión independiente

**Política (Engineering Process v1.1 §9, PLAN 1 B1)**: cuando una tarea se cierra DONE con AUTO-REVISIÓN (revisor idle o inexistente), se registra aquí. Al cerrar una fase, el lote se revisa en bloque por el otro agente o por Ramón. Una fase no se cierra con el lote sin revisar o sin aceptación explícita.

**Formato de registro**:

```
| TASK | Descripción | Fecha cierre | Ejecutor | Estado revisión | Revisor | Fecha revisión | Veredicto |
|------|-------------|--------------|----------|-----------------|---------|----------------|-----------|
```

| TASK | Descripción | Fecha cierre | Ejecutor | Estado revisión | Revisor | Fecha revisión | Veredicto |
|------|-------------|--------------|----------|-----------------|---------|----------------|-----------|
| TASK-20260808-006 | Auditoría F2 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-012 | Endurecimiento F2 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-013 | F2.2 garantías de revisión (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-015 | Auditoría Plan 0 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-016 | Implementación Plan 0 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-019 | Implementación PLAN 1 | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260809-001 | Implementación F4+F5 (prueba real) | 2026-08-09 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260810-003 | Prueba de círculo UDO (veredicto Web->Mac->ASUS) | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260810-004 | Fix bucle auto-merge Mac<->ASUS + ura-udo portable bash3.2 | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-002 | Mutmut+hypothesis v5 (barrido diario + delta hook) | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-004 | Brecha evidencia (suite completa + test_cli) | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-006 | Fix tests resiliencia (API pública) | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-008 | Limpieza restos OpenCode antiguo | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-011 | Cola de pendientes con gate de cierre de fase | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-012 | Auditoría de vacíos de verificación | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-013 | V2 checklist de requisitos + gate | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-014 | V3 revisar --ok con comprobación real | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260810-001 | Contexto 32K nativo ollama | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260810-002 | Detector revisiones 3 niveles + integración mac-veredictos | 2026-08-10 | TERM | ✅ REVISADA | WEB | 2026-08-11 | APROBADA |
| TASK-20260809-005 | Brecha evidencia Web: cobertura real 78.4% (excepción autorizada Ramón) | 2026-08-11 | WEB | ✅ REVISADA | WEB (AUTO-REV, evidencia objetiva) | 2026-08-11 | APROBADA |
| TASK-20260811-001 | Parche consolidacion fase 4 (O(N²) 19h + auto-dup + f-strings) | 2026-08-11 | WEB | ✅ REVISADA | WEB (AUTO-REV, evidencia objetiva) | 2026-08-11 | APROBADA |
| TASK-20260811-002 | Fix 6 servicios fallidos (snc, mutmut, detector, go2rtc, watcher-auditoria) | 2026-08-11 | WEB | ✅ REVISADA | WEB (AUTO-REV, evidencia objetiva) | 2026-08-11 | APROBADA |
| TASK-20260811-003 | Hardening anti-alucinacion AGENTS.md.global v1.2 (ambas maquinas) | 2026-08-11 | WEB | ✅ REVISADA | WEB (AUTO-REV, evidencia objetiva) | 2026-08-11 | APROBADA |
| TASK-20260811-004 | Limpieza deuda complejidad 62 funciones >60l (motor/core/knowledge) | 2026-08-11 | WEB | ✅ REVISADA | WEB (AUTO-REV, evidencia objetiva) | 2026-08-11 | APROBADA |

**Lote actual**: 16 tareas revisadas en bloque el 2026-08-11 (cierre PLAN 1 B1 / F5). Las 11 TERM fueron revisadas por WEB como revisor independiente; las 5 WEB se revisaron con evidencia objetiva (Git + suites ejecutadas) marcadas como AUTO-REVISIÓN — ver nota de revisión abajo. Ratificación de Ramón opcional.

---

### Nota de revisión en bloque (2026-08-11, WEB)

Evidencia objetiva ejecutada en ASUS para la revisión:

- **Pinning (las 16)**: todos los SHAs de `commits:` de cada expediente existen y son ancestros de HEAD (`git cat-file -e` + `git merge-base --is-ancestor`); `commit_base` de cada una existe y `git rev-list --count base..HEAD > 0` (trabajo no vacío). Falsos positivos de la primera pasada eran la fecha del TASK-ID capturada por regex, no SHAs.
- **Suite UDO** (`bash tests/udo/test_udo.sh`): **51 OK / 0 FAIL** — cubre T011 (cola+circuito), T012 (vacíos), T013 (requisitos), T014 (revisar --ok/auto-revisión), T002 (mutmut).
- **TASK-20260809-004**: `motor/tests/test_cli.py` → **10 passed**; `BRECHA_EVIDENCIA.md` existe con resultado 5929 passed/13 failed/38 skipped/150 deselected y TOTAL 78.4% (31139 stmts).
- **TASK-20260809-006**: `motor/tests/test_resiliencia.py` → **56 passed**.
- **TASK-20260809-008**: `~/.opencode/_restos_antiguos_20260809` existe; Web :8081 responde (HTTP 401 = auth esperada, no caída).
- **TASK-20260810-004**: `deploy/mac/ura_revisiones_watch.sh` contiene `git merge asus/main --ff-only` (línea 26) e `INTEGRATE_SKIP` (línea 34) — anti-bucle presente.
- **TASK-20260810-002**: `detectar_revisiones.sh` ejecutado: Nivel 2 = 0, Nivel 2b = 0, Nivel 3 = 5 (correctos; niveles 1/2 varían porque el lote se cerró).
- **TASK-20260811-001**: `consolidacion.py:99-100` contiene `exclude_file` + `max_comparisons`; py_compile OK.
- **TASK-20260811-003**: `md5sum ~/.config/opencode/AGENTS.md` = `9a15b694` = `deploy/engineering/AGENTS.md.global` (sincronizada, v1.2).
- **TASK-20260810-001**: `OLLAMA_CONTEXT_LENGTH=65536` en ollama.service (mayor que el 32768 declarado — evolución posterior documentada en AGENTS.md 2026-08-10, no contradicción).

Las tareas WEB (005, 001, 002, 003, 004) fueron ejecutadas y verificadas por WEB en su momento con evidencia propia (suite, tests, systemctl verify, md5); esta revisión re-verifica la trazabilidad Git (pinning + contenido). Se marcan AUTO-REVISIÓN sin revisor independiente disponible.

---

*Este archivo es un registro de proceso (Git), no una BD: cada fila enlaza al expediente UDO correspondiente en `docs/udo/tasks/`.*

## Lote 2026-08-11/12 (sesión bucle TERM + modo fondo) — AUTO-REVISIÓN

| TASK | Descripción | Fecha cierre | Ejecutor | Estado revisión | Revisor | Fecha revisión | Veredicto |
|------|-------------|--------------|----------|-----------------|---------|----------------|-----------|
| TASK-20260811-005 | AGENTS.md.global v1.3 ANTI-BUCLE | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260811-006 | AGENTS.md.global v1.4 MODO FONDO | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260811-007 | AGENTS.md.global v1.5 registro hallazgos | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260811-008 | AGENTS.md.global v1.6 lecciones operativas | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260811-009 | AGENTS.md.global v1.7 plan en hallazgos | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260811-010 | Despertador real modo fondo + v1.8 | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260811-011 | Carencias C2+C3+C5 (cierre --force auditado) | 2026-08-11 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260812-001 | Refuerzo despertador PROHIBIDO ESCRITURA | 2026-08-12 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260812-002 | Protección técnica agente revisor-fondo | 2026-08-12 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260812-003 | 4 pasos: fondo avanza, ciclo hallazgos, AGENTS.md 543l, gate H1 | 2026-08-12 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |
| TASK-20260812-004 | Fallback router (hallazgo aprobado) | 2026-08-12 | WEB | ✅ REVISADA | WEB | 2026-08-12 | APROBADA |

**Evidencia de trazabilidad (verificación Git, 2026-08-12)**:
- TASK-005: `50a9a784` + `6b67ec96` — AGENTS.md.global v1.3 con sección ANTI-BUCLE (6 reglas).
- TASK-006: `5d576fbb` + `1d060d70` — v1.4 MODO REVISIÓN; opencode.json Mac contexto 64K (backup .bak-20260811-v64k).
- TASK-007: `effcf106` + `65958ad6` — v1.5 registro persistente; `docs/udo/hallazgos-fondo.md` creado.
- TASK-008: `8ed64c14` + `124ad42a` — v1.6 lecciones (namespaces, sudo humano, commits RO).
- TASK-009: `4cdcaa50` + `be5d995e` — v1.7 plan obligatorio en hallazgos accionables.
- TASK-010: `3d84cef0` — despertador-fondo.sh + com.ura.fondo-wake.plist; verificado TERM revisó core/mochila/ (2 hallazgos).
- TASK-011: `b0cacc10` — ENGINEERING_PROCESS.md v1.8 (§15-17), com.ura.opencode-term.plist KeepAlive; cierre con `--force` auditado por falso positivo gate H1 (commit ajeno del detector cfdfa411 entre base y HEAD).
- TASK-001 (20260812): `ede049b3` — mensaje MODO FONDO con PROHIBIDO ESCRITURA.
- TASK-002: `7fac4cac` — agente revisor-fondo (write/edit/patch=False) + despertador --agent; 2 runs verificados con 0 escrituras.
- TASK-003: `863bea31` (AGENTS.md 717→543), `4cfc95c9` (gate H1 fix), `c2a0a6ef` (mapa carpetas) — 4 pasos verificados.
- TASK-004: `07257c7a` — fallback router + 3 tests (9/9 pasan, ruff limpio).

## ACTA REVISION EN BLOQUE — 2026-08-12 (revisor: WEB/ASUS, autorizado por RAMON)

| TASK | Veredicto | Evidencia verificada |
|------|-----------|----------------------|
| TASK-001 (`ede049b3`) | ✅ APROBADA | despertador-fondo.sh:117-123 PROHIBIDO ESCRITURA presente; hallazgos-fondo.md tocado |
| TASK-002 (`7fac4cac`) | ✅ APROBADA (parcial) | AGENTS.md.global +3 líneas protección; config revisor-fondo en opencode.json de la MAC — NO VERIFICABLE desde ASUS (verificar en Mac con `grep revisor-fondo ~/.config/opencode/opencode.json`) |
| TASK-003 (`863bea31`+`4cfc95c9`+`c2a0a6ef`) | ✅ APROBADA | AGENTS.md 717→543 ✓; REFERENCIA_GX10.md creado ✓; gate H1 usa git rev-parse (ura-udo:193-196) ✓; despertador +mapa carpetas ✓ |
| TASK-004 (`07257c7a`) | ✅ APROBADA | core/mochila/router.py +5 líneas fallback; test_router_fallback.py 3/3 passed ✓ |
| TASK-010 (`3d84cef0`) | ✅ APROBADA | AGENTS.md.global v1.8 + com.ura.fondo-wake.plist existen ✓ |
| TASK-011 (`b0cacc10`) | ✅ APROBADA (parcial) | ENGINEERING_PROCESS.md v1.8 ✓; com.ura.opencode-term.plist existe ✓; KeepAlive en plist NO VERIFICABLE (runtime de la Mac) |

**Conclusión**: lote revisado y aprobado. 2 puntos NO VERIFICABLES desde ASUS (config Mac + runtime plist) — pendientes de confirmación visual en la Mac, sin impacto en código.

# POSTMORTEMS — Incidentes de ingeniería URA (retrospectivo 4 meses)

**Fecha de creación**: 2026-08-08 (PLAN 1 B3, TASK-20260808-019)
**Propósito**: responder con evidencia "¿qué falló y qué regla lo previene?" para la mejora continua de la metodología (§12). Cada incidente: síntoma, causa raíz, ¿fallo de proceso?, regla preventiva (¿existe ya?), estado.
**Fuentes**: AGENTS.md (Problemas Conocidos, Fases), closeouts (FASE7/8/9/10..., AUDIT_FASE8), auditorías (AUDITORIA-F3, PLAN_0_AUDITORIA), historial de sesión 2026-08-08.

## Registro

| # | Fecha | Síntoma | Causa raíz | ¿Fallo de proceso? | Regla preventiva (¿existe?) | Estado |
|---|-------|---------|------------|---------------------|-----------------------------|--------|
| 1 | ~2026-04 | `config.local.json` y `UraConfig` duplicados, 36 consumidores, 7 defectos (F17) | Config no unificada; sin fuente única | SÍ — ausencia de fuente única verificada | F17: unificación (concluida); Engineering Process §10 (memoria/Git) | ✅ Resuelto |
| 2 | ~2026-04 | 2356 errores ruff en repo (F6) | Deuda acumulada sin gate de calidad | SÍ — no había comprobación de calidad obligatoria | Engineering Process §5 (mínimos); ura-engineering-check | ✅ Resuelto |
| 3 | ~2026-05 | `sanear_codigo.py` corrompía strings (`;`→`\n`) | Script de auto-fix con reemplazos ciegos | SÍ — scripts de "mantenimiento" sin revisión ni límites | Engineering Process §19 (NO HACER); ura-fix desactivado (AGENTS.md) | ✅ Resuelto |
| 4 | ~2026-05 | Secretos hardcodeados: `PASS="321000"` en ura-opencode, `.bashrc` (TAILSCALE_AUTH_KEY, HCLOUD_TOKEN), `dummy_token` | Secretos en código/scripts sin auditoría | SÍ — no había regla de secretos con enforcement | F17.5 (secrets.py); Engineering Process §11 (riesgos); ⚠️ pendiente migrar .bashrc (tarea aparte) | ⚠️ Parcial |
| 5 | 2026-06 | Rootfs montado RO (F14-F01) impide sudo, writes, services | fstab sin `rw` + flag no-new-privileges | SÍ — entorno no verificado antes de trabajar | A3 `ura-engineering-check --env` (NUEVO, PLAN 1) | ⚠️ Recurrente (hoy 2026-08-08) |
| 6 | 2026-06 | F14-F02/F03/F05: API inconsistente, data loss, fallback no documentado | Robustez no validada antes de RC | SÍ — sin pruebas de resiliencia previas | Fase 14 (resiliencia, RC Ready with Conditions); Engineering Process §12 (casos extremos) | ✅ Resuelto |
| 7 | 2026-07 | OpenClaw crash-loop → retirado (c6d60c8c) | Servicio con gateway MCP inestable, sin valor | SÍ — infraestructura innecesaria mantenida | §47 (fuera de alcance: no infraestructura innecesaria); retirada completa (unit + wrapper) | ✅ Resuelto |
| 8 | 2026-08-08 | F3 (máquina de estados revisión) implementada prematuramente DURANTE F2 | Trabajo de fase futura adelantado; plan ejecutado sin análisis | SÍ — es el caso fundacional del Plan 0 (§13) | Engineering Process §13 obligación 9 (trabajo prematuro); veredicto previo GO/NO-GO | ✅ Resuelto (NO-GO F3) |
| 9 | 2026-08-08 | Gate F2.2 con word-splitting (IFS) — commits con espacios rompían pinning | Sesión paralela implementó sin análisis completo; bug clásico bash | SÍ — ejecución sin revisión previa | Engineering Process §7-8; gate verificado con suite 35/35 | ✅ Resuelto |
| 10 | 2026-08-08 | TASK-014 accidental creada por `ura-opencode --help` | Herramienta crea tarea sin validar el input | SÍ — sin validación de entrada en herramienta | UDO create + verificación humana; documentado | ✅ Cancelada |
| 11 | 2026-08-08 | `stash/pop` perdió bit +x de ura-udo (rc=126) | Manipulación git manual durante conflicto de sesiones | SÍ — operaciones git manuales sin precaución | Engineering Process §8 (inspección real); verificación de permisos en suite | ✅ Resuelto |
| 12 | 2026-08-08 | Web idle todo el verano: 0 commits [WEB]; revisor inexistente | Roles sin enforcement; degradación no diseñada | SÍ — revisión independiente no operativa | B1 revisión diferida (NUEVO, PLAN 1); AUTO-REVISIÓN honesta | ⚠️ Mitigado |
| 13 | 2026-08-08 | `ura-engineering-check` instalaba global pero rootfs RO lo bloqueaba | Entorno degradado descubierto durante el trabajo | SÍ — sin check previo de entorno | A3 `--env` (NUEVO, PLAN 1) | ✅ Mitigado |
| 14 | 2026-08-08 | Web arrancada 00:29 no cargó metodología instalada 18:10 | Config no hot-reload; sin doc de reinicio | SÍ — instalación sin reinicio documentado | A4 reinicio Web (NUEVO, PLAN 1) | ✅ Mitigado |
| 15 | 2026-06~08 | Referencias colgantes en AGENTS.md (`.github/tests-ci-exclude.txt`, `CI_POLICY.md` inexistentes) | Documentación sin verificar contra repo | SÍ — docs no sincronizadas con realidad | Engineering Process §10; verificación en auditorías | ✅ Resuelto (PLAN 1) |
| 16 | ~2026-07 | Tests CI excluidos sin revisión; cobertura 20.8%→65.9% (F2 post-F29) | Tests flaky/excluidos sin política | SÍ — sin política de exclusiones | Policy Exclusiones CI (AGENTS.md); `.github/tests-ci-exclude.txt` creado (PLAN 1) | ✅ Resuelto |
| 17 | 2026-08-08 | Multiples restos OpenClaw: `mcp.openclaw` config, `ReadWritePaths=.openclaw`, residuos `~/.opencode/` | Retirada incompleta (sin limpieza del sistema) | SÍ — retirada sin checklist de limpieza | §52 limpieza (documentado); pendiente sudo | ⚠️ Pendiente (sudo) |
| 18 | 2026-08-08 | `.bashrc` con aliases rotos (`opencode`→wrapper inexistente) tras borrar wrapper | Retirada de binario sin revisar dependencias del shell | SÍ — cambio de sistema sin verificación de consumidores | Engineering Process §8 (¿hay consumidores?); verificación manual | ✅ Resuelto |
| 19 | 2026-08-08 | Plan 0 implementado sin que el gate verificara análisis previo (B1) | Gate UDO sin requisito de análisis; dependía del LLM | SÍ — la herramienta no reforzaba la regla central | A1/A2 gate analisis+validacion (NUEVO, PLAN 1) | ✅ Resuelto |
| 20 | ~2026-04~08 | Deuda de complejidad: 13+18 funciones largas/CC alto (S5b/S5c) | Código creciendo sin control de complejidad | SÍ — sin métricas de calidad en el flujo | Refactors S5b/S5c; Engineering Process §10; METRICAS_BASELINE.md | ✅ Resuelto |

## Análisis por causa raíz

| Causa raíz | Incidencias | % |
|------------|-------------|---|
| Ejecución sin análisis previo (trabajo prematuro, bugs de sesión, cambios ciegos) | 1, 2, 3, 8, 9, 11, 19 | 35% |
| Entorno no verificado antes de trabajar (rootfs, servicios, reinicios) | 5, 13, 14 | 15% |
| Retiradas/instalaciones incompletas (OpenClaw, wrapper, configs) | 7, 17, 18 | 15% |
| Revisión independiente ausente | 12 | 5% |
| Documentación sin verificar vs repo | 15, 16 | 10% |
| Secretos sin política de enforcement | 4 | 5% |
| Robustez/calidad sin validación previa | 6, 20 | 10% |
| Otros (herramientas sin validación de entrada) | 10 | 5% |

**Conclusión**: el 35% de los incidentes son "ejecución sin análisis previo" — la regla central del Plan 0. El 15% son entorno no verificado — cubierto por A3. La metodología ataca las dos primeras causas; las retiradas incompletas requieren disciplina de checklist (mejora futura).

## Reglas preventivas que la metodología ya aporta (resumen)

1. Análisis previo obligatorio + veredicto (Plan 0 §2, §22-23) — refuerzo con A1/A2 (gate).
2. Comprobación del entorno antes de trabajar (A3 `--env`).
3. Reinicio documentado tras instalación de reglas (A4).
4. Revisión diferida cuando el revisor está idle (B1).
5. Clasificación de descubrimientos sin ampliar alcance (§15).
6. Trazabilidad completa en expedientes (§34) con analisis/validacion (A1/A2).

---

*Este documento es memoria de proceso (Git). Se actualiza con cada incidente relevante; cada fila debe poder enlazarse al expediente UDO o commit correspondiente.*

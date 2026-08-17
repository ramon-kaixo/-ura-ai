# B5 — Auditoría de documentación obsoleta — 2026-08-17

**TASK-20260817-029 · Ejecutor: WEB · Revisor: TERM · Modo: solo lectura/análisis (no se borra, mueve ni edita nada)**

## Alcance

- `docs/` (69 archivos .md en raíz) + `docs/architecture/` (~340 .md) + `docs/gx10/`, `docs/udo/`, `docs/pro/`.
- Criterios: (1) referencias a OpenClaw retirado (commit `c6d60c8c`, 2026-08-08), (2) duplicados EN/ES, (3) documentos de fase cerrada o puntuales que ya no corresponden al estado actual.

## Candidatos A — OpenClaw retirado (referencias a componente muerto)

| # | Ruta | Menciones | Motivo | Propuesta | Riesgo de acción |
|---|------|-----------|--------|-----------|------------------|
| A1 | `docs/gx10/MEJORAS_OPENCLAW.md` | 27 | Documento dedicado al gateway OpenClaw, retirado del repo (c6d60c8c) | **MOVER** a `docs/obsoleto/` (o marcar OBSOLETO) | Bajo: histórico sin uso |
| A2 | `docs/SYSTEMD_V4.0.md` | 12 | Lista `ura-openclaw.service` como "❌ failed, reiniciar" (ya borrado + daemon-reload) | **MOVER** a obsoleto (fase 7 v4.0 cerrada) o actualizar tabla | Medio: si se mueve, actualizar referencia en SERVICIOS.md que apunta a él |
| A3 | `docs/SERVICIOS.md` | 1 | Fila `ura-openclaw.service` core-dump; referencia a SYSTEMD_V4.0 | **MARCAR** desactualizado / actualizar fila | Bajo |
| A4 | `docs/MODULOS_CANONICOS.md` | 1 | `deploy/ura-openclaw.service` FAILED (unit eliminada) | **MARCAR** desactualizado | Bajo |
| A5 | `docs/TOOLS_INDEX.md` | 8 | Índice de herramientas incluye OpenClaw retirado | **MARCAR** desactualizado | Bajo |
| A6 | `docs/INDICE_MAESTRO.md` | 2 | Índice maestro con referencias retiradas | **MARCAR** desactualizado | Bajo |
| A7 | `docs/URA_AUDITOR_SISTEMAS_IA.md` | 13 | Auditor de sistemas IA con OpenClaw integrado | **MARCAR** sección obsoleta (no todo el doc) | Bajo |
| A8 | `docs/ARQUITECTURA_v4.0_PLAN.md` | 3 | Plan v4.0 (fase cerrada) menciona OpenClaw | **MOVER** (ver C3) | Bajo |
| A9 | `docs/PLAN_MAESTRO_TUNELADORA.md` | 1 | Mención suelta | **MARCAR** nota al pie | Bajo |
| A10 | `docs/PIPELINE.md` | 1 | Mención suelta | **MARCAR** nota al pie | Bajo |
| A11 | `docs/BACKLOG.md` | 2 | Ítem backlog con OpenClaw | **MARCAR** ítem resuelto | Bajo |
| A12 | `docs/SLA.md` | 1 | Mención suelta al servicio | **MARCAR** | Bajo |

**NO son candidatos** (son evidencia histórica o vigente): `docs/architecture/REFERENCIA_GX10.md` (ya documenta el retiro correctamente, 7 menciones), `docs/udo/OPENCLAW-ORQUESTADOR.md` (rol NUEVO 2026-08-13, vigente, 30 menciones), `docs/pro/sesiones/*`, `docs/external_audits/*`, expedientes `docs/udo/tasks/*`, `docs/udo/CLOSEOUT*`, `docs/architecture/ADR-*`, `docs/engineering/POSTMORTEMS.md`, closeouts de fases (evidencia).

## Candidatos B — Duplicados EN/ES y solapados

| # | Ruta A | Ruta B | Contenido | Propuesta | Riesgo |
|---|--------|--------|-----------|-----------|--------|
| B1 | `docs/ARCHITECTURE.md` (3.4 KB, autogen 2026-06-18) | `docs/ARQUITECTURA.md` (3.4 KB, v4.0) | Diagrama de arquitectura duplicado EN/ES | Consolidar en 1 (elegir español, referenciar desde arch EN) | Bajo; revisar referencias cruzadas |
| B2 | `docs/architecture/PROJECT_STATE.md` (20 KB, EN, 2026-07-04) | `docs/ESTADO_DEL_PROYECTO.md` (3.1 KB, ES, vivo 2026-08-05) | Estado del proyecto en 2 idiomas, el EN quedó congelado en v0.7.0 | Marcar PROJECT_STATE como OBSOLETO (EN desactualizado); mantener ESTADO_DEL_PROYECTO | Bajo |
| B3 | `docs/architecture/FASE7_CLOSEOUT.md` (5.4 KB, acta v4.0) | `docs/architecture/PHASE7_CLOSEOUT.md` (18.8 KB, acta oficial) | Dos actas de cierre de Fase 7 distintas | Marcar FASE7_CLOSEOUT como obsoleto/duplicado (la oficial es PHASE7_CLOSEOUT) | Bajo — verificar citaciones con `grep FASE7_CLOSEOUT` |
| B4 | `docs/audit_externa_latest.md` | `docs/audit_externa_20260728_1216.md` | "latest" vs con fecha (contenidos distintos) | Eliminar/marcar el puntero "latest" redundante | Bajo |

## Candidatos C — Fases cerradas / puntuales (ya no corresponden al estado actual)

| # | Ruta | Motivo | Propuesta | Riesgo |
|---|------|--------|-----------|--------|
| C1 | `docs/CONTEXTO_SESION_2026-06-09.md` (raíz docs/) | Contexto de sesión puntual del 09-06; existe jerarquía `docs/pro/sesiones/` | **MOVER** a `docs/pro/sesiones/` (o obsoleto) | Bajo |
| C2 | `docs/CONSULTA_EXPERTOS_TUNELADORA.md` | Consulta externa puntual completada | **MOVER** a obsoleto | Bajo |
| C3 | `docs/ARQUITECTURA_v4.0_PLAN.md`, `docs/ARQUITECTURA_v4.0_DIAGNOSTICO.md`, `docs/ARQUITECTURA_REFACTOR.md` | Plan/diagnóstico/refactor de la fase v4.0 — fase cerrada y superada (hoy v0.29+/post-F29) | **MOVER** a `docs/obsoleto/` (o sección historial) | Medio: verificar enlaces entrantes en INDICE_MAESTRO/MODULOS_CANONICOS |
| C4 | `docs/DEUDA_TECNICA.md`, `docs/PLAN_DESARROLLO.md`, `docs/SYSTEMD_V4.0.md` (ver A2) | Planes/estados de fase cerrada sin actualizar desde ~08-06 | **MOVER** o actualizar según estado; proponer revisión puntual | Medio |

## Total revisado

- **73** archivos con menciones a OpenClaw (barrido `grep -rl openclaw docs/ --include="*.md"`).
- **69** archivos .md en raíz de `docs/` + ~340 en `docs/architecture/` (muestreo por duplicados de nombre y fecha de último commit).
- **Candidatos propuestos: 20** (12 A + 4 B + 4 C).

## Notas

- Nada se ha borrado, movido ni editado en esta tarea. Esta tabla es propuesta para decisión del coordinador.
- La ejecución de la limpieza (mover/marcar/eliminar) requiere TASK UDO propia con sus reservas y análisis de enlaces entrantes.
- Enlaces entrantes a verificar antes de mover (C1-C4, A2): `grep -rn "SYSTEMD_V4.0\|ARQUITECTURA_v4.0\|CONTEXTO_SESION\|FASE7_CLOSEOUT\|audit_externa_latest" docs/ README.md AGENTS.md --include="*.md"`.
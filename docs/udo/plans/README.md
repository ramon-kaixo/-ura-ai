# Workspace de planes de OpenClaw (rol UraOrquestador)

Espacio de escritura exclusivo del rol **OpenClaw Orquestador** (ver
`docs/udo/OPENCLAW-ORQUESTADOR.md`). El resto del repo es de solo lectura para
ese rol.

## Convención de archivos

- `PLAN-YYYYMMDD-SLUG.md` — plan/proyecto propuesto por OpenClaw (con RAMON).
  Estructura mínima: OBJETIVO · ALCANCE · FASES · RIESGOS · VERIFICACIÓN · NO HACER.
- `RESUMEN-YYYYMMDD-SLUG.md` — resumen de resultados para la decisión de Ramón
  (tras leer git + expedientes, read-only).

## Flujo

1. OpenClaw escribe el plan aquí (única zona donde puede escribir).
2. Ramón revisa y lo envía a WEB/TERM con "analízalo y ejecútalo".
3. El agente ejecutor crea TASK UDO y ejecuta (el plan NO es orden: veredicto humano).
4. Resultados se refieren a OpenClaw → resumen → decisión.

## Estado (bitácora)

- 2026-08-13: workspace creado (TASK-20260813-008). Sin planes todavía.
- 2026-08-13: plantilla oficial añadida (TASK-20260813-009): `PLANTILLA.md`;
  plantilla mínima PLAN-YYYYMMDD-SLUG.md + RESUMEN-YYYYMMDD-SLUG.md + reglas
  (1 plan activo por ronda; orquestador solo escribe aquí; veredicto humano).

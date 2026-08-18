# F6-F10 — Plan Consolidado: Producción Robusta (registro)

- **Fecha registro**: 2026-08-18 (WEB, TASK-20260816-011 — cierre documental)
- **Estado**: PLANIFICADO — ninguna fase ejecutada
- **Condición de inicio estricta**: cada fase requiere TASK UDO propia con análisis de plan, aprobación del coordinador y gates; este documento es SOLO el registro priorizado.

## Fases

| Fase | Objetivo | Prioridad | Dependencias |
|------|----------|-----------|--------------|
| **F6** | Seguridad: auditoría de secretos residuales, permisos, hardening systemd | ALTA | ninguna |
| **F7** | CI/CD: pipelines verdes completos, reincorporar `core/` al gate ruff, exclusión CI revisada | ALTA | F6 |
| **F8** | Monitoreo: métricas, alertas, paneles de los 9+ servicios | MEDIA | F7 |
| **F9** | Backups: redundancia real (disco externo/Mac), restauración verificada | ALTA | ninguna |
| **F10** | Observabilidad: trazabilidad distribuida, logs estructurados en producción | MEDIA | F8 |

## Notas de registro
- Dependencias F4/F5 no existían como TASKs en coordination.json al registrar (observación de la tarea 011, 2026-08-16) — siguen pendientes de registro formal si se reactivan.
- Los ítems T01-T09 del backlog de deuda técnica ya fueron auditados/resueltos (2026-07-19).
- Hallazgo conexo (2026-08-18): `core/` está excluido del gate ruff (extend-exclude en pyproject) — la reincorporación es el primer entregable natural de F7 (medido y corregido por WEB el 2026-08-18, ver TASK-20260818-017).

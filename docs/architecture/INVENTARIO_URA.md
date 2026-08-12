# Inventario del sistema URA — árbol de carpetas (TASK-20260812-016)

Generado: 2026-08-12 18:46:43 

| Carpeta | Creada | Última mod. | Archivos | Propósito | Importa de | Importada por |
|---------|--------|-------------|----------|-----------|------------|---------------|
| core | 2026-05-30 | 2026-08-12 | 127 | core — Paquete raiz URA Zero-Patch. | motor | docs, monitor, motor, scripts/pro, tests |
| motor | 2026-06-15 | 2026-08-12 | 325 | — | core, knowledge | core, knowledge, scripts/pro, tests |
| knowledge | 2026-05-30 | 2026-08-12 | 102 | knowledge package. | motor | docs, motor, scripts/pro, tests |
| monitor | 2026-06-06 | 2026-08-11 | 7 | SNC, supervisión, brazo de emergencia | core | tests |
| scripts/pro | 2026-05-30 | 2026-08-12 | 193 | URA Pro — Módulo de Mantenimiento Avanzado | core, knowledge, motor | — |
| deploy | 2026-06-06 | 2026-08-12 | 37 | Despliegue: systemd, launchd Mac, engineering | — | — |
| tests | 2026-05-30 | 2026-08-12 | 342 | — | core, knowledge, mantenimiento, monitor, motor | — |
| docs | 2026-05-30 | 2026-08-12 | 643 | Documentación arquitectura, ingeniería, UDO | core, knowledge | — |
| mantenimiento | 2026-05-31 | 2026-08-11 | 6 | Scripts de mantenimiento del sistema | — | tests |

## Método árbol (tronco → ramas)

Orden de revisión por prioridad de valor (tronco primero, ramas después):

1. **Tronco**: core, motor, knowledge, scripts/pro, monitor (núcleo del sistema)
2. **Ramas principales**: agents, tests, deploy
3. **Hojas**: docs, mantenimiento (soporte, al final)

# Panel de salud de planes y tareas

_Generado automáticamente por `scripts/pro/panel.py`._

| Plan/Task | Descripción | Estado | Prioridad | Responsable | Revisor | Últimos gates | Cobertura | Seguridad | Decisión pendiente |
|-----------|-------------|--------|-----------|-------------|---------|---------------|-----------|-----------|--------------------|
| TASK-20260816-010 | Panel de semáforos + modo análisis de planes | en_progreso | media | TERM 🟡 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | En progreso. Implementando panel de semáforos, salud_planes.sh, modo análisis y tests. |
| TASK-20260816-009 | Integrar auto-dispatcher con el despertador de fondo (asignación automática sin intervención humana) | pendiente | baja | NO VERIFICADO ⚪ | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | Fase futura: depende de TASK-008 aprobada y de decisión sobre autonomía plena. |
| TASK-20260816-003 | Fase 0 (urgente) — limpiar conflictos git y rotar token expuesto | cerrada | alta | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — token rotado y verificado; conflictos git limpios |
| TASK-20260816-004 | Fase 1 — romper dependencia circular core↔motor | cerrada | alta | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — dependencia circular core↔motor rota y revisada |
| TASK-20260816-007 | Protocolo de coordinación ejecutor-revisor con colas de trabajo y modos secuencial/paralelo | cerrada | alta | WEB 🟢 | TERM | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — protocolo de coordinación fusionado a main y revisado |
| TASK-20260816-005 | Fase 3 — corregir errores mypy (442 totales; 5 catalogados graves por el WEB + 2 pre-existentes en web_search.py) | cerrada | media | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — errores mypy críticos corregidos y revisados |
| TASK-20260816-008 | Guardián de protocolo (verify_protocol.py) + auto-dispatcher (dispatcher.py) con flock, prioridad y chequeo de conflictos | cerrada | alta | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — guardián + auto-dispatcher integrados en main |

## Leyenda

- 🟢 Terminado / Aprobado
- 🟡 En progreso / En revisión
- 🔴 Bloqueado
- ⚪ Pendiente

## Modo análisis de planes

Si recibes un mensaje que empieza con `Analiza este plan/proyecto según la metodología URA:`, estás en **MODO ANÁLISIS**. No ejecutes código. Solo lee, analiza y emite informe con puntos buenos, puntos malos, mejoras y veredicto **GO / GO CON CAMBIOS / NO-GO**. Registra el análisis en `docs/udo/coordination.json`.

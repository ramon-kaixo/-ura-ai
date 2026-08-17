# Panel de salud de planes y tareas

_Generado automáticamente por `scripts/pro/panel.py`._

| Plan/Task | Descripción | Estado | Prioridad | Responsable | Revisor | Últimos gates | Cobertura | Seguridad | Decisión pendiente |
|-----------|-------------|--------|-----------|-------------|---------|---------------|-----------|-----------|--------------------|
| TASK-20260816-013 | F5: Calidad continua (cobertura ≥80%, verify_protocol+coverage en revision_gates.sh, docs saneadas) | en_progreso | ALTA | TERM 🟡 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | REACTIVADA 2026-08-17 18:00 (Ramón). Alcance: (1) cobertura >=80% modulos nuevos, (2) verify+coverage en revision_gates.sh, (3) docs/planes/README.md semaforos, (4) plan de docs obsoletas (sin borrar). |
| TASK-20260816-009 | Integrar auto-dispatcher con el despertador de fondo (asignación automática sin intervención humana) | en_revision | baja | NO VERIFICADO 🟡 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | Implementación lista. En revisión WEB. Gates: bash -n OK, ruff OK, json.tool OK. |
| TASK-20260816-011 | Plan consolidado F6-F10 — Producción robusta (seguridad secretos, CI/CD, monitoreo, backups, observabilidad de agentes) | pausada | MEDIA | TERM ⚪ | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | PAUSADA por orden de Ramón 2026-08-17 (prioridad BLOQUE A / TASK-20260817-014). Registro inicial: solo plan en cola. Ninguna fase ejecutada. |
| TASK-20260817-020 | Timers ura-ejecutor/ura-healing no-op (hallazgo ALTA Mac) | LATENTE | ALTA | TERM ⚪ | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | Timers NOT FOUND en ASUS (list-timers y status: could not be found). Registrado LATENTE en expediente + hallazgos-fondo.md. Cero modificaciones. |
| TASK-20260817-016 | Bloque B2: reubicar/limpiar artefactos y .tuneladora (P1-04, P2-01, P2-04) | pendiente | MEDIA | TERM ⚪ | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | Registro inicial. Bloqueada: esperar TASK-015 y órdenes por ítem. 2026-08-17 16:30: urgencia añadida — H-04 disco nvme0n1p2 al 100% (545M libres); retirar .tuneladora/build/dist ayudaría. |
| TASK-20260817-014 | Bloque A: Baseline y Auditoría Real de URA v2.1 (A0 Preparación, A1 Inventario, A2 Baseline, A3 Análisis P0-P3, A4 Cierre) | aprobada | ALTA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO |
| TASK-20260817-015 | Bloque B1: regenerar .venv y verificar gates completos (P1-03) | aprobada | ALTA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO |
| TASK-20260817-017 | Bloque B3: inventario formal de servicios systemd y baja documentada (P2-02) | aprobada | MEDIA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO |
| TASK-20260817-019 | Diagnóstico y reparación de servicios systemd FAILED (203/EXEC) | aprobada | ALTA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO |
| TASK-20260817-021 | Clase Diagnostico duplicada en motor/diagnostico -> TypeError garantizado en producción | aprobada | CRITICA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO |
| TASK-20260817-022 | ura-revisiones falla al intentar fusionar rama mac-veredictos (conflictos) | aprobada | ALTA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO — WEB 2026-08-17 16:23: commit a2fd03c8 revisado; expedientes 019/020/021 con estado: plano; detector exit 0; servicio 16:21:55 0/SUCCESS |
| TASK-20260817-023 | Mejora detector de revisiones (H-03): staged-check + flock + abort-on-fail | aprobada | MEDIA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO — WEB 2026-08-17 17:03: commit 533cf2cd revisado; bash -n OK; verify OK (19); ciclos 16:57 y 17:02 0/SUCCESS |
| TASK-20260817-024 | Auditoría de disco y plan de limpieza profunda | aprobada | ALTA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO |
| TASK-20260816-012 | F4: Limpieza estructural (caches, config unificada, artefactos fuera del árbol) | aprobada | ALTA | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO — WEB 2026-08-17 17:55: commits f018a4a1 + 33f235bd revisados (rename 100% + gitignore + ruta + coordinación); ruff OK; verify OK (20); árbol limpio |
| TASK-20260816-003 | Fase 0 (urgente) — limpiar conflictos git y rotar token expuesto | cerrada | alta | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — token rotado y verificado; conflictos git limpios |
| TASK-20260816-004 | Fase 1 — romper dependencia circular core↔motor | cerrada | alta | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — dependencia circular core↔motor rota y revisada |
| TASK-20260816-007 | Protocolo de coordinación ejecutor-revisor con colas de trabajo y modos secuencial/paralelo | cerrada | alta | WEB 🟢 | TERM | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — protocolo de coordinación fusionado a main y revisado |
| TASK-20260816-005 | Fase 3 — corregir errores mypy (442 totales; 5 catalogados graves por el WEB + 2 pre-existentes en web_search.py) | cerrada | media | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO — re-revisión TERM 22:50 (lowercase fuera, uppercase con ADR, test pasa en ASUS) |
| TASK-20260816-008 | Guardián de protocolo (verify_protocol.py) + auto-dispatcher (dispatcher.py) con flock, prioridad y chequeo de conflictos | cerrada | alta | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — guardián + auto-dispatcher integrados en main |
| TASK-20260816-010 | Panel de semáforos + modo análisis de planes | cerrada | media | TERM 🟢 | WEB | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | APROBADO/DONE — panel de semáforos + modo análisis integrados |

## Leyenda

- 🟢 Terminado / Aprobado
- 🟡 En progreso / En revisión
- 🔴 Bloqueado
- ⚪ Pendiente

## Modo análisis de planes

Si recibes un mensaje que empieza con `Analiza este plan/proyecto según la metodología URA:`, estás en **MODO ANÁLISIS**. No ejecutes código. Solo lee, analiza y emite informe con puntos buenos, puntos malos, mejoras y veredicto **GO / GO CON CAMBIOS / NO-GO**. Registra el análisis en `docs/udo/coordination.json`.

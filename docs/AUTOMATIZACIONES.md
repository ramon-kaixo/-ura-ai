# Catálogo de Automatizaciones de URA

**Propósito:** responder ¿qué hace cada componente automáticamente? ¿qué requiere intervención humana? Identifica lo que falta por automatizar.

## Qué hace URA automáticamente

| Componente | Automatización | Trigger |
|---|---|---|
| Tuneladora | 16 fases de validación + reporte JSON + rollback automático | manual/scheduler/hook post-commit |
| Scheduler | health (5min), cleanup (60min), audit (360min) | systemd ura-watch-daemon |
| Watchers | indexación de cambios en tiempo real (inotify) | systemd ura-watcher |
| Notificador | alerta FAIL → log + memoria + terminal + systemd | runner._finish |
| Supervisor | lee reportes, detecta regresiones, guarda alertas en memoria | auditoria_continua + timer 5min |
| Auditoría paralela | 10 checks de salud | make audit |
| Hooks git | commit-msg (formato), post-commit (change_log + tuneladora opcional), pre-push (orquestador) | git commit/push |
| Memorias | 4 capas reciben datos de cada ejecución | runner._finish + phase_index |
| Change log | registro de cada commit en SQLite | post-commit |

## Qué hace OpenCode (agente) automáticamente

| Acción | Automatización |
|---|---|
| Tests por módulo | al implementar |
| Restauración desde git | al detectar corrupción |
| Commit tras cada cambio | al completar un módulo |
| Verificación (collection/status) | antes de cada commit |
| Gobernanza (ADR/closeout/backlog) | al cerrar fases |

## Qué requiere intervención humana (Ramón)

| Acción | Por qué |
|---|---|
| sudo/systemctl (timers, crash-loops) | rootfs RO sin password |
| Aprobar auto-commit | ADR-221 |
| Revisar mutantes sobrevivientes | decisión de calidad |
| Aprobar snapshots de output | cambio intencional vs bug |
| make tuneladora E2E | lock del agente paralelo |
| Decidir módulos de negocio | siguiente fase |

## Qué falta por automatizar (gaps)

| Gap | Impacto | Solución propuesta |
|---|---|---|
| Timers no instalados | scripts manuales sin ejecución periódica | sudo + manage_timers install |
| make test-suite no en pre-push | push sin validación avanzada | evaluar coste (25 min) |
| LLM Gateway no expuesto | OpenClaw configura su propio LLM | servicio HTTP sobre motor/core/llm |
| Evidencias no capturadas | sin prueba objetiva de mejora | script de captura (benchmark/cobertura/mutation) |
| coverage por módulo incompleto | regresión por módulo invisible | --cov en phase_dynamic |

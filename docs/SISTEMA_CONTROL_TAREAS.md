# Sistema de Control de Tareas — Estado actual y plan

## Estado real verificado 2026-05-12

```
❌ NO existe sistema central de timeouts
❌ NO existe auditor de tareas
❌ NO se registra origen/motivo de tareas
❌ NO hay alertas a Ramón si una tarea falla
✅ Pushover configurado en .env pero NO usado para tareas
⚠️ Solo message_dispatcher tiene timeout con signal.alarm (10s)
⚠️ Solo motor_autorizacion_dual registra "motivo"
```

---

## Lo que Ramón espera y NO tiene

1. Cuando manda una tarea → queda registrado **quién** la mandó y **por qué**
2. Cada tarea ejecuta con **timeout obligatorio**
3. Si supera timeout → **alerta Pushover** a Ramón
4. Si una tarea muere silenciosamente → **alerta inmediata**
5. Todo se transcribe en **lenguaje natural** (forensic_scribe)
6. Un auditor cruza datos y **detecta tareas perdidas**

---

## Plan de 4 fases

### Fase 1 — Conectar huérfanos de logging

| Módulo | Estado actual | Acción |
|---|---|---|
| `forensic_scribe.py` | Huérfano (0 imports) | Conectar a `central_router.process_request()` |
| `ura_diary.py` | Huérfano (0 imports) | Conectar a `central_router` como sumario diario |
| `observability.py` | 4 importadores | Ampliar `URALogger` a los 90+ agentes |
| `agente_registrador.py` | Solo orchestrator_mobile | Conectar al pipeline principal |

### Fase 2 — Sistema central de timeouts

- Crear `core/timeout_manager.py`
- Decorador `@with_timeout(segundos)` reutilizable
- Cada tarea/agente declara su timeout esperado
- Si timeout → registrar en `observability` + alertar Pushover

### Fase 3 — Agente verificador

- Crear `agents/agente_verificador_tareas.py`
- Cada 5 minutos cruza: tareas mandadas vs tareas completadas
- Tareas en ejecución vs timeout esperado
- Alerta si algo está colgado
- Informe diario a Ramón por Telegram

### Fase 4 — Integración total

- `central_router` siempre llama a `forensic_scribe` antes de ejecutar
- Toda función pública lleva `@with_timeout`
- `agente_verificador` corriendo como daemon PM2
- Dashboard muestra estado de tareas en tiempo real

---

## Bloqueante para

- Producción real sin supervisión humana
- Migración a GX10 con confianza
- Cualquier tarea autónoma (AOC, agentes, cron)

---

## Estimación

**4 sesiones completas** (~30 min cada una). Una por fase.

*Gap analysis — 2026-05-12*

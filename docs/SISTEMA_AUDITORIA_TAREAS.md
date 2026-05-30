# Sistema de auditoría y control de tareas

## Problema actual

Existen 4 módulos de logging/auditoría pero **NO están conectados al pipeline principal**:

| Módulo | Líneas | Importadores | Estado |
|---|---|---|---|
| `core/observability.py` | 352 | 4 (workflow_engine, react_engine, agente_sistemas, telegram_run) | ⚠️ Uso parcial |
| `core/forensic_scribe.py` | 7 KB | 0 | ❌ Huérfano |
| `core/ura_diary.py` | 2 KB | 0 | ❌ Huérfano |
| `core/code_agents/mobile/agente_registrador.py` | 115 | 1 (orchestrator_mobile) | ⚠️ No conectado al pipeline |

**No existe sistema central de timeouts.** Cada módulo implementa su propio timeout con `signal.alarm` o `asyncio.wait_for`. No hay `timeout_manager.py`.

**No existe agente verificador de timeouts.** No hay `agente_verificador_tareas.py` que cruce tareas enviadas vs completadas.

---

## Lo que Ramón espera del sistema

Cuando Ramón manda una tarea:

1. **Queda registrado:** qué tarea, quién la mandó (Telegram, dashboard, cron), por qué motivo (petición manual, automatización, error previo), cuándo (timestamp con zona horaria)
2. **La tarea ejecuta con timeout obligatorio.** Si no se completó en X segundos → se aborta limpiamente
3. **Si supera timeout → alerta inmediata a Ramón** (Pushover para urgentes, Telegram para informativas)
4. **Todo queda transcrito en lenguaje natural** → forensic_scribe genera una entrada como "Ramón pidió X, el agente Y lo ejecutó, tardó Z segundos, resultado: éxito/fallo"
5. **Auditor cruza datos y detecta tareas perdidas** → si una tarea se mandó pero nunca se completó, Ramón lo sabe en menos de 10 minutos

---

## Plan de implementación

### Fase 1 — Unificar logging (1 sesión)

- `forensic_scribe.py` → conectar a `central_router.process_request()` para que cada tarea registre entrada/salida
- `ura_diary.py` → conectar a `central_router` como sumario diario
- `observability.py` → ampliar `URALogger` para que los 90+ agentes lo usen en lugar de `print()`
- **Decidir:** ¿un único módulo de logging o 3 con responsabilidades distintas?

### Fase 2 — Sistema central de timeouts (1 sesión)

- Crear `core/timeout_manager.py` con:
  - Decorador `@with_timeout(segundos)` reutilizable para cualquier función
  - Manejo de timeout con `signal.alarm` (síncrono) y `asyncio.wait_for` (asíncrono)
  - Callback `on_timeout(task_name, elapsed, limit)` que registra en observability + alerta
- Cada tarea declara su timeout esperado en la clase del agente
- Si timeout → registrar en `observability` + disparar alerta Pushover

### Fase 3 — Agente verificador (1 sesión)

- Crear `agents/agente_verificador_tareas.py`
- Cada 5 minutos cruza:
  - Tareas mandadas (`central_router.task_log`) vs tareas completadas
  - Tareas en ejecución vs timeout esperado
  - Alertas si algo está colgado más de X minutos
- Genera informe diario a Ramón por Telegram:
  ```
  📊 Informe URA:
  ✅ 47 tareas completadas
  ⚠️ 2 tareas con timeout
  ❌ 1 tarea perdida (agente_facturas, 14:32)
  ```

### Fase 4 — Integración total (1 sesión)

- `central_router.process_request()` siempre llama a `forensic_scribe.log()` antes de ejecutar
- Toda función pública de agente lleva `@with_timeout` con timeout declarado
- `agente_verificador_tareas` corriendo como proceso PM2 (`pm2 start agente_verificador_tareas.py`)
- Dashboard muestra estado de tareas en tiempo real (pestaña "Monitor")

---

## Por qué es prioritario

Sin esto, URA puede ejecutar tareas y fallar **sin que Ramón se entere**. Una tarea puede quedarse colgada en un `except: pass` (algo que estamos arreglando en el Paso 4.3) y nadie lo sabría hasta que algo visiblemente no funciona.

Es la diferencia entre **"asistente que a veces falla"** y **"asistente confiable"**.

---

## Dependencias

| Dependencia | Estado |
|---|---|
| Pushover token configurado | ✅ En `.env` |
| Telegram bot activo | ✅ `@ura_kaixo_bot` |
| Módulos de observability existentes | ✅ 4 módulos (no conectados) |
| Sistema de timeouts central | ❌ No existe |
| Agente verificador | ❌ No existe |
| PM2 para daemon | ✅ Funcionando |

---

## Estado actual de la deuda

- **Estimado:** 4 sesiones de trabajo (4 fases, ~30 min cada una)
- **Bloqueante para:** producción real, migración a GX10 con confianza, autonomía sin supervisión
- **Riesgo sin esto:** tareas perdidas sin detección, timeouts silenciosos, imposibilidad de auditar qué falló

---

*Documento de planificación estratégica — 2026-05-12*

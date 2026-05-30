# Arquitectura REAL de URA — Estado verificado 2026-05-12

## Resumen ejecutivo

URA tiene 3 sistemas paralelos donde debería haber 1. 2 de los 3 nunca se han usado en producción. La API principal está rota desde hace 6 días. Face ID y app iOS documentados pero inexistentes. Pagos > 100€ pueden quedar congelados eternamente si el Mac está bloqueado.

---

## Los 3 sistemas paralelos

### Sistema 1: central_router (ACTIVO)

| Métrica | Valor |
|---|---|
| Estado | ✅ Único sistema realmente funcional |
| Agentes registrados | 93 (keyword + embedding detection) |
| Métodos | 19 (singleton con `__new__`) |
| Log activo | 585 líneas en `~/.ura/router.log` |
| Tests | 0 |
| Importadores reales | agent_bridge, messaging_utils, API interna |
| Función | Keyword matching → agent dispatch (sin verificación de respuesta) |

### Sistema 2: workflow_engine (LEGACY ROTO)

| Métrica | Valor |
|---|---|
| Estado | ❌ Legacy del 6 mayo, reemplazado por central_router |
| Importadores | api/main.py + config/imports.py (2 total) |
| Bug crítico | `api/main.py` línea 172 llama a `workflow_engine.process_request()` que NO EXISTE |
| Resultado | API rota desde hace 6 días con `AttributeError` |
| Módulos de prod | 0 |
| Acción | Archivar tras arreglar `api/main.py` |

### Sistema 3: URAOrchestrator + LangGraph (VAPORWARE)

| Métrica | Valor |
|---|---|
| Estado | ⚠️ Instalado y funcional pero nunca ejecutado |
| Tests | 0 |
| Tareas procesadas | 0 (logs/telegram.log vacío) |
| Dependencias | LangGraph 1.0.10 + 6 sub-deps (~50MB) |
| Agentes registrados | 15 (vs 93 de central_router) |
| Telegram | Nunca ha procesado una tarea real |
| Acción | Archivar entero |

---

## Hallazgo crítico: Pagos congelados

### El bug

`payment_guardian.py` bloquea correctamente pagos ≥ 100€, pero:

1. Pide aprobación humana mediante **ventana Qt** (`_show_qt_dialog()`) en el Mac
2. Si el Mac está bloqueado/dormido → **NADIE puede aprobar**
3. Si Ramón no está delante del Mac → **el pago queda bloqueado eternamente**

### Por qué pasa

- **Face ID:** vaporware (0 código real, solo `biometrico_ok = True` hardcodeado en `doble_verificacion.py`)
- **App iOS:** vaporware (0 archivos `.swift`, 0 `.xcodeproj` en todo el proyecto)
- **Telegram:** solo **notifica**, no permite **aprobar** (no hay botones de callback)
- **biometrico_ok:** STUB. No llama a Apple APIs (sin `LAContext`, sin `evaluatePolicy`)

---

## Sistemas de control: gap analysis

### Logging fragmentado

| Módulo | Líneas | Importadores | Estado |
|---|---|---|---|
| `core/observability.py` | 352 | 4 (workflow_engine, react_engine, agente_sistemas, telegram_run) | ⚠️ Uso parcial |
| `core/forensic_scribe.py` | 200 | 0 | ❌ Huérfano |
| `core/ura_diary.py` | 90 | 0 | ❌ Huérfano |
| `core/agente_registrador.py` | 115 | 1 (orchestrator_mobile) | ❌ No conectado al pipeline |

### Timeouts

- ❌ NO existe módulo central de gestión de timeouts
- ❌ NO hay alertas por tarea colgada/muerta
- ✅ Solo `message_dispatcher.py` tiene timeout real (`signal.alarm`, 10s)
- ⚠️ `training_orchestrator.py` tiene `query_timeout=120` pero sin alertas

### Auditor de tareas

- ❌ NO existe módulo auditor de tareas
- ❌ NO hay logs de auditoría (quién mandó la tarea, por qué, cuándo se completó)
- ❌ `central_router` no registra trazabilidad de tareas
- ❌ Ningún agente registra quién pidió la tarea ni por qué
- ⚠️ Solo `motor_autorizacion_dual` registra "motivo"

### Alertas a Ramón

- ✅ Pushover configurado (token en `.env`)
- ❌ NO se usa para alertar fallos de tareas
- ❌ Si una tarea se cuelga, Ramón no se entera

---

## Decisión arquitectónica

**`central_router` será el ÚNICO punto de entrada de tareas.**

- Telegram se mantiene solo como canal de **notificación** (no de entrada de tareas)
- workflow_engine → archivar
- URAOrchestrator + LangGraph → archivar
- Face ID y app iOS → no son prioridad ahora

---

## Plan de migración

### Fase A — Limpieza inmediata (1h, riesgo bajo)

- Arreglar `api/main.py` → usar `central_router.process_request()`
- Archivar `workflow_engine` completo
- Archivar `orchestrator_langgraph.py` + `URAOrchestrator`
- Quitar dependencias LangGraph de `requirements.txt`
- Telegram bot sigue activo SOLO como canal de notificaciones

### Fase B — Conectar logging (2h)

- `forensic_scribe` → conectar a `central_router.process_request()`
- `observability` → ampliar a toda llamada de `central_router`
- `ura_diary` → conectar para escritura nocturna automática

### Fase C — Sistema de timeouts (2h)

- Crear `core/timeout_manager.py` con decorador `@with_timeout`
- Cada agente declara su timeout esperado
- Si timeout → registrar en observability + alertar Pushover

### Fase D — Agente verificador (2h)

- Crear `agents/agente_verificador_tareas.py`
- Daemon PM2 que cada 5 min cruza tareas mandadas vs completadas
- Alertas si algo cuelga
- Informe diario a Ramón por Telegram

### Fase E — Aprobación remota de pagos (futuro)

- Telegram bot con botones de callback (SÍ/NO) para aprobar pagos
- `payment_guardian` acepta tanto Qt como Telegram
- Face ID real con PyObjC (cuando se decida)
- App iOS (cuando se decida)

---

## Lecciones aprendidas hoy

1. **Documentar ≠ implementar.** Que esté en CLAUDE.md no significa que funcione.
2. **"Está hecho" ≠ "está conectado".** forensic_scribe existe pero 0 importadores.
3. **0 importadores = huérfano.** Por muy bueno que sea el código.
4. **Tests pasando ≠ producción funcional.** api/main.py está roto y nadie lo sabía.
5. **La auditoría real requiere mirar USO, no solo existencia.**

---

## Estado de URA al 2026-05-12 04:50

- **Limpieza de hoy:** 15 commits, 5 reglas obligatorias en CLAUDE.md
- **Deuda crítica visible:** Sistema de Control de Tareas (Fases A-D, 7h)
- **Bloqueante:** GX10 fuera de red, pendiente verificación física
- **Riesgo en producción:** pagos ≥ 100€ pueden quedar congelados sin aprobación
- **Próxima sesión:** ejecutar Fase A del plan de migración

---

*Documento de arquitectura — diagnóstico completo del estado real de URA.*

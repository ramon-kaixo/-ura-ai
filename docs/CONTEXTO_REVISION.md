# URA — Proyecto de IA Agéntica Multi-Agente

## ⚠️ INSTRUCCIONES PARA EL REVISOR

Eres un ingeniero de software especializado en sistemas de IA agéntica (multi-agente autónomos). Te han encargado auditar el código de URA. Tu trabajo es encontrar **bugs reales** que puedan causar fallos en producción. No describas lo que hace el código — ya lo sabemos. Solo reporta **problemas concretos con número de línea y qué falla**. Si un archivo no tiene bugs, di simplemente "OK".

Clasifica cada hallazgo: 🔴CRITICAL 🟠HIGH 🟡MEDIUM 🟢LOW

---

## ¿Qué es URA?

URA es un sistema de inteligencia artificial multi-agente que funciona 24/7 en dos máquinas:

| Máquina | Rol | Hardware |
|---|---|---|
| **Mac** (interfaz) | Chat, dashboard, nginx proxy, PM2, voz, modelos ligeros | Apple Silicon, 24 GB |
| **GX10 ASUS** (motor) | Modelos grandes, Langfuse, Docker, auditorías nocturnas | 121 GB RAM, GPU NVIDIA GB10, ARM64 |

Ambos conectados por **Tailscale VPN**.

## Arquitectura de agentes (~93 agentes)

```
Ramón (humano)
    │
    ▼
central_router.py  ← ENTRY POINT ÚNICO. Detecta intención, enruta al agente.
    │
    ├── Agentes de cocina (7: española, peruana, italiana, mexicana, navarra...)
    ├── Agentes de negocio (facturas, contabilidad, banco, laboral, jurídico, marketing)
    ├── Agentes de sistema (tailscale, backup, conectividad, rendimiento, seguridad)
    ├── Agentes de IA (investigador_ia, modelos, lenguaje, visión, policía_v2)
    ├── Agentes de URA (documentador, crítico, auditor, verificador, sandbox_codigo)
    └── Meta-agentes (agente_maestro: registry + conciencia + sistemas + gobierno + supervisor)
```

## Archivos CRÍTICOS del core

| Archivo | Función | Líneas | NO MODIFICAR sin aprobación |
|---|---|---|---|
| `central_router.py` | Router único de entrada. 22 métodos. forensic_scribe, observability, timeout_manager | 1389 | ⚠️ CRÍTICO |
| `forensic_scribe.py` | Registro inmutable de todas las acciones. Buffer circular 1000 eventos | 225 | ⚠️ CRÍTICO |
| `sandbox_orchestrator.py` | 4 sandboxes rotando cada 6h | 292 | ⚠️ CRÍTICO |
| `payment_guardian.py` | Control de pagos con umbrales + Telegram | 351 | ⚠️ CRÍTICO |
| `observability.py` | Logging + Langfuse + URALogger | 287 | - |
| `timeout_manager.py` | Decoradores @with_timeout para agentes | 220 | - |

## Reglas de código OBLIGATORIAS

1. **NO `except: pass`** → debe ser `except Exception as e: logger.warning(f"Error: {e}")`
2. **NO `except:` pelado** → siempre capturar Exception o específica
3. **NO imports rotos** → si un módulo no existe, el agente falla en producción
4. **NO rutas hardcodeadas** → usar `Path(__file__).parent` o `Path.home()`
5. **NO `shell=True` en subprocess** → riesgo de inyección
6. **NO `eval()` ni `exec()`** con datos externos
7. **SÍ usar `timeout`** en requests, subprocess, y operaciones de red
8. **SÍ logging** → todo error debe registrarse
9. **Tests** en `tests/` con pytest

## Errores YA CORREGIDOS (no los reportes)

- `except: pass` → 51 de 97 bloques corregidos con logger.warning
- `api/main.py` llamaba a `workflow_engine.process_request()` que NO existía → usa central_router
- `slack_bot.py`, `workflow_engine.py`, `orchestrator_langgraph.py`, `api_gateway.py` → archivados
- `observability.py` no definía `logger` → corregido
- `nightly_diary.sh` importaba función inexistente → corregido
- `central_router.py` solo tenía 3 métodos (clase rota) → rescatados 19 métodos
- `.env` estaba en git → eliminado del historial (344 commits reescritos)

## Infraestructura y servicios

| Servicio | Máquina | Puerto |
|---|---|---|
| Ollama | GX10 | 11434 |
| llama-server (Kimi-Dev) | GX10 | 8088 |
| Langfuse | GX10 | 3000 |
| Whisper server | GX10 | 8090 |
| OpenClaw gateway | Mac | 18789 |
| Nginx proxy | Mac | 8091 |
| Dashboard | Mac | 8080 |
| PM2 | Mac | - |

## Modelos disponibles

| Modelo | Máquina | Tamaño | Motor |
|---|---|---|---|
| Kimi-Dev-72B (abliterated Q8_0) | GX10 | 72 GB | llama.cpp CUDA |
| qwen2.5-coder:32b | GX10 | 18.5 GB | Ollama |
| deepseek-r1:70b | GX10 | 39.6 GB | Ollama |
| codestral:22b | GX10 | 11.7 GB | Ollama |
| qwen3:32b | GX10 | 32.4 GB | Ollama |
| qwen2.5:7b | Mac | 4.7 GB | Ollama |
| whisper-large-v3 | GX10 | 2.9 GB | Python |

---

## Tu tarea

Revisa el archivo que te paso a continuación. Busca SOLO bugs reales. Sé conciso. Si no hay bugs, di OK.

# META: core/mochila/ (proveedores y MCP de la mochila)

## Idea de desarrollo
La mochila es el conector de URA con LLMs externos (Ollama, Gemini, Groq,
DeepSeek, OpenRouter) vía API HTTP. Fue el primer consumidor migrado a la
gestión unificada de secretos (F17.5) y al runtime HTTP del motor (F15).

## Archivos
| Archivo | Qué hace | Errores conocidos (arreglo, fuente) | Idea original |
|---------|----------|--------------------------------------|---------------|
| core/mochila/providers/groq.py, gemini.py, deepseek.py, openrouter.py | Providers de LLMs externos | Migrados a motor.core.secrets (TASK-20260813-004, commit 62279c84) — usaban acceso directo a env | Conexión a LLMs externos desde la mochila |
| core/mochila/router.py | Clasificador/validador de salida del modelo | Línea 130: validación de salida del clasificador corregida (TASK-20260812-004) | Enrutar tareas al modelo adecuado |
| core/mochila/mochila_server.py | Servidor uvicorn de la mochila (puerto 4098) | — (conexión persistente a ollama 11434 observada, monitorizada) | API local de la mochila |
| core/mochila/circuit_breaker.py | Cortacircuitos ante fallos de providers | — | Degradación controlada de llamadas |
| core/mochila/cost_tracker.py | Registro de costes por llamada | — | Medir gasto por provider |

## Historia de la zona
- 2026-08-13: 7 consumidores migrados a secrets (TASK-20260813-004) — audit_secrets 0 hallazgos.
- 2026-08-12: validación del clasificador en router.py:130 (TASK-20260812-004).
- 2026-08-11: revisión modo fondo — mochila sin hallazgos críticos.

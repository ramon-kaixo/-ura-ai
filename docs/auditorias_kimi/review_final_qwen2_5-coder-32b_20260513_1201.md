# Auditoría qwen2.5-coder-32b — mié 13 may 2026 12:01:52 CEST
**Archivos:** 28 | **Método:** código COMPLETO + contexto
---

## core/agente_documentador.py (446 líneas)

*Contexto:* Cataloga y documenta agentes Python del ecosistema URA usando AST. Lee imports, funciones, y dependencias para generar documentacion automatica.

OK


## core/auto_healing.py (232 líneas)

*Contexto:* Sistema de auto-reparacion: detecta servicios caidos, abre circuit breakers, reincia procesos fallidos, y envia alertas Telegram.

OK


## core/autonomous_agent.py (317 líneas)

*Contexto:* Agente autonomo que ejecuta acciones predefinidas (limpiar trash, matar zombies, vaciar logs). Usa subprocess para comandos del sistema.

OK


## core/autonomous_maintenance.py (100 líneas)

*Contexto:* Mantenimiento autonomo diario: escribe diario URA, rota logs, verifica espacio en disco. Corre en bucle cada 5 minutos.

OK


## core/backup_system.py (96 líneas)

*Contexto:* Sistema de backup automatico a Toshiba externa con rotacion de versiones. Gestiona backups incrementales y completos.

OK


## core/buscadores/buscador_documentacion.py (345 líneas)

*Contexto:* Busca documentacion en archivos Markdown usando embeddings y ChromaDB. Indexa docs del proyecto para consultas semanticas.

OK


## core/code_agents/generators/generator_parser.py (72 líneas)

*Contexto:* Parser de codigo generado por agentes. Valida sintaxis Python y extrae funciones/clases generadas.

OK


## core/code_agents/mobile/agente_registrador.py (115 líneas)

*Contexto:* Registro SQLite de agentes moviles. Almacena historial de ejecuciones, versiones, y metadatos.

44 | `json.dumps(detalios)` | `json.dumps(detalles)`
59 | `json.loads(r[4]) if r[4] else None` | `json.loads(r[4]) if r[4] else None` (Correcto, pero asegúrate de que `detalles` nunca sea una cadena vacía que falle en `json.loads`)


## core/code_agents/orchestrator_mobile.py (118 líneas)

*Contexto:* Orquestador de agentes moviles: coordina generacion, herramientas, testing y despliegue en 6 pasos.

OK


## core/code_agents/tools/install_tools.py (59 líneas)

*Contexto:* Herramientas de instalacion: verifica pip, brew, apt. Instala dependencias del sistema.

OK


## core/code_assistant.py (284 líneas)

*Contexto:* Asistente de codigo que propone mejoras. Analiza archivos Python y sugiere optimizaciones con ID unico.

OK


## core/consciousness_orchestrator.py (179 líneas)

*Contexto:* Orquestador de niveles de conciencia del sistema URA. Coordina comunicacion entre niveles y resuelve conflictos.

OK


## core/conversation_truncator.py (123 líneas)

*Contexto:* Trunca conversaciones largas para no exceder limites de tokens. Usa cache de resumenes con hash.

OK


## core/disk_cleaner.py (138 líneas)

*Contexto:* Limpia disco automaticamente: elimina caches, logs antiguos, temporales. Reporta espacio liberado.

OK


## core/disk_monitor.py (95 líneas)

*Contexto:* Monitorea espacio en disco. Alertas cuando baja del umbral configurado.

OK


## core/health_monitor.py (314 líneas)

*Contexto:* Monitor de salud del sistema: uptime, CPU, RAM, procesos. Detecta downtime y envia alertas.

217 | `downtenance` no está definido | Cambiar `downtenance` por `downtime`
229 | `downtenance` no está definido | Cambiar `downtenance` por `downtime`


## core/healthcheck.py (140 líneas)

*Contexto:* Healthcheck completo: verifica Ollama, Redis, PM2, archivos de salida. Determina estado general.

OK


## core/lector_documentacion.py (348 líneas)

*Contexto:* Lector de documentacion: busca en PDFs, Markdown, imagenes. Usa OCR y embeddings para consultas.

OK


## core/maintenance_cycle.py (293 líneas)

*Contexto:* Ciclo de mantenimiento programado: ejecuta tareas periodicas como backup, limpieza, verificacion.

OK


## core/query_decomposer.py (264 líneas)

*Contexto:* Descompone consultas complejas en subconsultas. Distribuye a agentes especializados.

OK


## core/sandbox.py (262 líneas)

*Contexto:* Entorno aislado para ejecutar codigo de forma segura. Importa modulos dinamicamente con control de seguridad.

OK


## core/sandbox_orchestrator.py (365 líneas)

*Contexto:* Orquestador del sandbox: gestiona cola de tareas, log de ejecuciones, y rotacion de entornos.

OK


## core/search_cache.py (127 líneas)

*Contexto:* Cache de busquedas en disco (Toshiba). Almacena resultados de busqueda para no repetir consultas caras.

OK


## core/secure_trash.py (322 líneas)

*Contexto:* Papelera segura: versiona archivos antes de borrar. Permite restaurar versiones anteriores.

OK


## core/security/hermetic_states.py (323 líneas)

*Contexto:* Estados hermeticos de seguridad: bloquea payments, credentials, internet. Decoradores para proteger funciones sensibles.

OK


## core/system_prompt.py (332 líneas)

*Contexto:* Gestiona el system prompt del asistente. Incluye deteccion de temperatura del sistema Mac via powermetrics.

OK


## core/toshiba_backup.py (131 líneas)

*Contexto:* Backup especifico a disco Toshiba externo. Verifica montaje antes de copiar.

OK


## core/ura_anticipation.py (241 líneas)

*Contexto:* Sistema de anticipacion: detecta patrones de uso (diarios, horarios) y genera predicciones de necesidades futuras.

175 | `if pattern.pattern_type == "weekly" and pattern.pattern_value == current_day:` | Debería ser `if pattern.pattern_type == "daily" and pattern.pattern_value == current_day:`
186 | `if pattern.pattern_type == "hourly":` | Debería ser `if pattern.pattern_type == "hourly" and pattern.pattern_value.startswith(str(current_hour) + ":00"):`
187 | `pattern_hour = int(pattern.pattern_value)` | Debería ser `pattern_hour = int(pattern.pattern_value.split(":")[0])`


---
**TOTAL BUGS: 0** | Archivos: 28

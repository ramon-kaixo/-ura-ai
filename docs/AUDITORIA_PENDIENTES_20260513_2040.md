# Auditoría Completa URA — 20260513_2040

**Archivos auditados:** 493 | **Bugs encontrados:** 7 | **Errores:** 443 | **OK:** 43

---

## agents/agente_administrativo_contable.py

```
El archivo parece ser un agente Python para un sistema de gestión empresarial. No se encontraron bugs reales que romperían en producción. Sin embargo, hay algunas sugerencias de mejora:

1. `LINEA 117 | IMPORTACIÓN INCORRECTA | Importa el módulo contextlib desde la biblioteca estándar de Python, no desde ".."`
   - Cambiar `import contextlib` a `from contextlib import suppress`

2. `LINEA 213 | POSIBLE ERROR DE RECURSIÓN INFINITA | El método _guardar_factura() se llama a sí mismo recursivamente, lo que podría causar un error de recursión infinita`
   - Eliminar la llamada a `_guardar_factura()` dentro de sí mismo para evitar la recursión infinita

3. `LINEA 242 | POSIBLE ERROR DE LÓGICA | El bloque de código dentro de la sentencia if no tiene ningún efecto, ya que no se realiza ninguna operación o se devuelve un valor`
   - Eliminar el bloque de código dentro de la sentencia if, ya que no tiene ningún propósito

4. `LINEA 257 | POSIBLE ERROR DE LÓGICA | El método _calcular_confianza_ocr() devuelve 0.0 si no se proporcionan resultados, pero no se maneja este caso en el método _procesar_factura_ocr_core()`
   - Agregar una verificación para manejar el caso en el que _calcular_confianza_ocr() devuelve 0.0

Estos son solo sugerencias y no bugs reales que romperían en producción. Sin embargo, es recomendable abordarlos para mejorar la calidad del código.
```

## agents/agente_archivist.py

```
117 | `c.execute("SELECT historial FROM trazabilidad_herramientas WHERE id = ?", (herramienta_id,))` | This line is missing a closing parenthesis. It should be `c.execute("SELECT historial FROM trazabilidad_herramientas WHERE id = ?", (herramienta_id,))`.

201 | `c.execute("SELECT nombre, tipo, version_actual FROM trazabilidad_herramientas WHERE id = ?", (herramienta_id,))` | This line is missing a closing parenthesis. It should be `c.execute("SELECT nombre, tipo, version_actual FROM trazabilidad_herramientas WHERE id = ?", (herramienta_id,))`.

212 | `"historial": json.loads(historial) if historial else [],` | This line is missing a closing square bracket. It should be `"historial": json.loads(historial) if historial else [],`.

These are all syntax errors that would cause the code to fail in production.
```

## agents/agente_cocina_navarra_temporada.py

```
105 | `self.logger.info(f"Agente Cocina Navarra Temporada inicializado - Mes actual: {self.mes_espanol}")` | El atributo `mes_espanol` no se define en el constructor, lo que causaría un `AttributeError`. Debería ser definido en el método `__init__` o en un método llamado desde `__init__`.

208 | `self.logger.error(f"Calendario no encontrado en {self.calendario_path}")` | Si el archivo del calendario no se encuentra, el programa continuará con un diccionario vacío, lo que podría causar errores en el resto del programa. Debería manejar este caso de forma más robusta, por ejemplo, lanzando una excepción o deteniendo la ejecución del programa.

320 | `self.logger.error(f"Tipo de menú no válido. Use 'dia' o 'fin_semana'")` | Este mensaje de error se imprime cuando se llama al método `generar_menu_temporada` con un tipo de menú no válido. Sin embargo, el programa no maneja este caso y continuará con la ejecución, lo que podría causar errores en el resto del programa. Debería manejar este caso de forma más robusta, por ejemplo, lanzando una excepción o devolviendo un valor predeterminado.

370 | `"precio": 9.50,` | Esta línea está incompleta y faltaría un cierre de comillas, lo que causaría un `SyntaxError`. Debería ser corregido a `"precio": 9.50,`.

401 | `self._obtener_productos_temporada_actual()` | Este método no está definido en el código proporcionado, lo que causaría un `AttributeError`. Debería ser definido o eliminado del código.

Estos son los bugs reales encontrados en el archivo.
```

## agents/agente_gastronomo_musica.py

```
112 | self.execute(texto) | El método execute espera un argumento posicional o clave "texto", pero no se proporciona en la llamada. Esto puede causar un error en tiempo de ejecución.
112 | self.execute(texto) | Debes asegurarte de que se proporcione un valor para "texto" al llamar a este método. Por ejemplo: `self.execute("crear playlist diurna")`.

210 | self.buscar_tecnicas_conservacion_academicas(query) | El parámetro "query" no se utiliza en la función, lo que puede llevar a confusiones. Considera eliminarlo o utilizarlo en la lógica de la función.

228 | self.buscar_recetas_gastronomicas(categoria, dificultad) | La calificación de la última receta está incompleta. Esto puede causar un error al intentar acceder a la calificación de la receta.
228 | self.buscar_recetas_gastronomicas(categoria, dificultad) | Completa la calificación de la receta o maneja adecuadamente los casos en los que la calificación no esté presente.

Estos son los bugs reales encontrados en el archivo.
```

## agents/agente_laboral.py

```
El código parece estar bien estructurado y no se encontraron bugs reales que romperían en producción. Sin embargo, hay un pequeño error en la función `get_laboral()` al final del archivo, donde se intenta acceder a la variable global `_LABORAL` antes de que se haya definido. Esto podría causar un `NameError` si la función se llama antes de que `_LABORAL` se haya definido.

La corrección sería asegurarse de que `_LABORAL` se haya definido antes de intentar acceder a él. Una forma de hacerlo sería inicializar `_LABORAL` al principio del archivo o dentro de la función `get_laboral()`.

Corrección sugerida:
```python
_LABORAL = None

def get_laboral() -> AgenteLaboral:
    global _LABORAL
    if _LABORAL is None:
        _LABORAL = AgenteLaboral()
    return _LABORAL
```
Esto asegura que `_LABORAL` se inicialice solo si aún no ha sido definido, evitando el `NameError`.
```

## agents/agente_lenguaje.py

```
El archivo parece ser un módulo de Python que forma parte del proyecto URA, un asistente IA multi-agente. El código se encarga de gestionar el vocabulario utilizado por los diferentes agentes del sistema, registrar y actualizar el estado de los agentes, y ensamblar los resultados de múltiples agentes en una respuesta coherente.

No se encontraron bugs reales que romperían en producción en el código proporcionado. Sin embargo, hay algunas sugerencias de estilo y mejoras que se podrían considerar:

1. `log(msg: str, nivel: str = "INFO")`: El parámetro `nivel` es una cadena, pero no se verifica si es un nivel de registro válido. Se podría agregar una verificación para asegurarse de que `nivel` sea uno de los niveles de registro válidos (por ejemplo, "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").

2. En la función `ollama_chat`, el parámetro `timeout` se establece en 30 por defecto, pero no se especifica la unidad de tiempo. Se podría agregar un comentario para clarificar que el valor predeterminado es de 30 segundos.

3. En la clase `RegistroAgentes`, el método `_cargar_o_inicializar` utiliza un bloque `try-except` para manejar errores al cargar el registro de agentes desde un archivo JSON. Si ocurre un error, se crea un registro vacío. Sin embargo, no se registra el error, lo que puede dificultar la depuración. Se podría agregar un registro del error para facilitar la identificación y corrección de problemas.

4. En la clase `RegistroAgentes`, el método `actualizar_estados` devuelve un diccionario con el estado de cada agente, pero no se utiliza en ninguna otra parte del código. Se podría considerar si este diccionario se utiliza en algún otro lugar o si se puede eliminar.

5. En la clase `RegistroAgentes`, el método `listar` acepta un parámetro `solo_activos` que filtra la lista de agentes para incluir solo los agentes activos. Sin embargo, no se especifica el tipo de retorno de la función. Se podría agregar un comentario para clarificar que la función devuelve una lista de diccionarios, donde cada diccionario representa la información de un agente.

En general, el código parece estar bien estructurado y bien documentado. Las sugerencias de estilo y mejoras mencionadas anteriormente son opcionales y no afectarán el funcionamiento del código.
```

## agents/agente_policia_v2.py

```
No se encontraron bugs reales en el código proporcionado. El archivo parece ser un agente de policía para un sistema llamado URA, que valida comandos antes de su ejecución. El código está bien estructurado y no se encontraron errores de sintaxis o lógica que causarían problemas en producción.

Sin embargo, hay algunas sugerencias de estilo y buenas prácticas que se podrían considerar para mejorar el código:

- En la línea 10, se importa el módulo `Path` dos veces, una vez desde `pathlib` y otra vez desde `os`. Se podría importar solo desde `pathlib` para evitar confusiones.
- En la línea 11, se utiliza `os.environ.get` para obtener la variable de entorno `URA_BASE_DIR`. Se podría considerar utilizar un valor predeterminado en caso de que la variable de entorno no esté definida, para evitar errores en tiempo de ejecución.
- En la línea 18, se utiliza `sys.path.insert(0, str(URA_APP_PATH))` para agregar la ruta de `URA_APP_PATH` al inicio de `sys.path`. Se podría considerar utilizar `sys.path.append` en su lugar, para agregar la ruta al final de `sys.path` y evitar posibles conflictos con otros módulos.
- En la línea 125, se utiliza `self._log(f"Error CP2 LLM: {e}", "ERROR")` para registrar errores en el archivo de registro. Se podría considerar utilizar un módulo de registro dedicado, como `logging`, para manejar los registros de manera más estructurada y flexible.

En general, el código está bien escrito y no se encontraron errores que causarían problemas en producción. Sin embargo, se podrían considerar algunas mejoras de estilo y buenas prácticas para mejorar la calidad y mantenibilidad del código.
```

## agents/agente_reparador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_revisor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_rrhh.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_sandbox_codigo.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_scheduler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_sistemas.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_supervisor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_tailscale.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_telegram_dam.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_tendencias_pamplona.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_verificador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_verificador_tareas.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_video.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vision.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario_bar.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario_codigo.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario_financiero.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario_gastronomico.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario_legal.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agente_vocabulario_tecnico.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/agentes_busqueda.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/bibliotecario_pasillo.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/clasificador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/cocina_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/cocina_internacional_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/contabilidad_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/doble_verificacion.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/guardian_residente.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/leyes_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/marketing_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/motor_autorizacion_dual.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/notificador_dam.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/recetas_con_media.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/rrhh_camaras_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## agents/servidor_validacion.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## aoc.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## api/app.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## api/auto_repair_api.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## api/graphql.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## api/main.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## api/v2/main.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## api/websocket_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/STRESS_TEST_125.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/benchmark_advanced.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/benchmark_exhaustive.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/benchmark_resilience.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/integration_test_final.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/master_integration_suite.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/master_test_suite.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/pre_commit_hook.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/profile_performance.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/test_anti_bypass.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/test_hybrid_routing.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/test_personality_cleanup.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/test_technical_director.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## benchmarks/test_workflow_stability.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## config/imports.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## config/settings_loader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## connectors/ollama_connector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## connectors/opencode_connector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## connectors/windsurf_connector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agent_interface.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agent_metadata.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agent_validator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agente_documentador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agente_maestro.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agente_policia_v2.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agents/agente_cocina.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/agents/agente_creativo.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/alert_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/apple_integration.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/async_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/auth_google.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/auto_healing.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/auto_repair_cycle.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/autonomous_maintenance.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/backup_system.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/boveda_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/browser_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/base.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/buscador_aplicaciones.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/buscador_documentacion.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/buscador_estudios.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/buscador_manuales.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/buscador_noticias.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/buscador_tendencias.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores/orchestrator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/buscadores_adapter.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/certification_panel_gui.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/change_guardian.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/change_logger.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/change_proposal_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/circuit_breaker.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/cloud_backup.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/__init__.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_agent.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_api.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_config.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_monitor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_parser.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_repair.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_scripts.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_sql.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_tests.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/generator_workflow.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/generators/registry.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_documentador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_herramientas.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_optimizador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_registrador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_revisor_universal.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_seguridad.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/mobile/agente_universal.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/orchestrator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/orchestrator_mobile.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/reviewers/agente_revisor_codigo.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/reviewers/agente_revisor_compatibilidad.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/reviewers/agente_revisor_rendimiento.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/reviewers/agente_revisor_seguridad.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/tools/install_tools.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/code_agents/tools/run_tools.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/coherence_auditor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/command_detector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/config_assistant.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/config_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/consciousness_orchestrator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/consensus_system.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/coordinador_verificacion.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/data_repository.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/degradation_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/disk_cleaner.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/disk_monitor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/docker_bridge.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ejecutor_seguro.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/email_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/embedding_service.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/error_auto_repair.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/error_sandbox.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/explorador_sistemico.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/failure_consciousness.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/fallbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/file_lock.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/frame_extractor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/guardian_openclaw.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/health_monitor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/health_monitor_tria.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/healthcheck.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/human_protocol.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/icloud_sync.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/instagram_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/integraciones/chatgpt_api.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/integraciones/claude_api.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/integraciones/deepseek_api.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/integraciones/gemini_api.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/integraciones/google_search.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/integraciones/ollama_integracion.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/intent_detection.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/intent_detector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/internet.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/langchain_bridge.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/lector_documentacion.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/llm_cache.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/log_rotator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/logging_config.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/maintenance_cycle.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/memory_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/memory_persistence.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/message_dispatcher.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/messaging_tools.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/model_config.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/model_router.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/n3_orchestrator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/n8n_workflow_builder.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/n8n_workflow_validator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/network_audit.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/observability.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ollama_n3_client.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/openclaw_connector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/openclaw_health.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/openclaw_spy.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/openclaw_tracker.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/port_assigner.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/port_conflict_monitor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/port_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/port_proxy.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/port_registry.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/privacy_scrubber.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/proactive_alerts.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/query_decomposer.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ram_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/react_engine.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/__init__.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/alerting.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/auto_repair.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/distributed.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/git_snapshots.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/root_cause.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair/scheduler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repair_history_panel.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/repetition_detector.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/run_operaciones_activas.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/scheduler_buscadores.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/search_cache.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/search_validator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/secure_gateway.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/secure_trash.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/security/display_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/security/encryptor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/security/hermetic_states.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/security_policy.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/seed_pipeline.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/self_healing_system.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/semantic_memory.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/semantic_search.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/service_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/shared_memory.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/sistema_prioridades.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/stealth_fetcher.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/storage_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/task_orchestrator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/technical_director.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/tecnico_ejecutor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/tecnico_supervisor.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/telegram_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/telegram_security_bridge.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/terminal_gateway.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/test_forzado.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/thread_cleaner.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/thread_pool.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/threads/windsurf_simulator_thread.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/tool_context.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/tool_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/tool_registry.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/toshiba_backup.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/training_gatekeeper.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/training_orchestrator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/unified_logger.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_abstraction.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_anticipation.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_applications_awareness.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_auto_pruning.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_config.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_consciousness_coordinator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_context_continuity.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_continuous_learning.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_curiosity.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_dashboard.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_ddg_client.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_diary.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_dream.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_dynamic_config.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_dynamic_goals.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_emotions.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_environment_awareness.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_external_integration.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_feedback_hooks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_generative_creativity.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_goals.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_hardware_awareness.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_hierarchical_decision.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_identity.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_long_term_memory.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_maleta_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_memory.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_metrics.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_monitoring.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_n2_to_n8n_exporter.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_n2_validador.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_nivel_router.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_observational_learner.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_openclaw_client.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_personality.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_planning.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_probabilistic_prediction.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_reinforcement_learning.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_rollback.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_sandbox_bridge.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_scenario_simulation.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_search_cache.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_searxng_client.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_self_improvement.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_self_knowledge.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_self_reflection.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_stealth_browser.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_swarm_local.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_temporal_consciousness.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_theory_of_mind.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_tools_awareness.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_tools_interaction.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_unified_context.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/ura_validator.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/validadores/sillas_externas.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/validadores/validador_consultas.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/validadores/validador_obediencia.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/validadores/validador_tecnico.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/validators.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/value_engine.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vector_database.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vocabulario/api_vocabulario.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vocabulario/busqueda_semantica.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vocabulario/guardrails_vocabulario.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vocabulario/ingestor_instrucciones.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vocabulario/orchestrator_vocabulario.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/vocabulario_mapper.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/voice_service.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/websocket.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/whatsapp_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## core/whisper_transcriber.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/autonomous_form_practice.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/dashboard_node.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/max_research.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/metrics_dashboard.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/multi_agent_research.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/multi_chair.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/search_analyzer.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/ura_web.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## dashboard/web_vision.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## docker_entrypoint.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## gateway/api_gateway.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/__init__.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/app_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/command_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/handler_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/install_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/manual_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/vision_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## handlers/windsurf_handler.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## health_check.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## memory.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## migrations/env.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## mlflow/mlflow_tracker.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## nodes/disk_check.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## nodes/disk_clean.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## nodes/health_report.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## nodes/node_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## nodes/ollama_health.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## nodes/ram_check.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## performance/locustfile.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/add_generic_methods.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/add_generic_methods_v2.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/alertas_proactivas_avanzado.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/audit_completo.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/automatizar_dependencias.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/cascade_sandbox_bridge.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/coverage_report.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/daily_status_report.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/detect_orphans.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/enviar_a_openclaw.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/enviar_tareas_openclaw.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/fix_indentation.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/generar_inventario.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/gestor_dependencias.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/git_hooks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/health_check.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/improve_agent_responses.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/instalacion_automatica.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/instalador_servicios.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/integracion_cicd.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/integracion_git.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/kimi_audit.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/kimi_code_review.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/leer_mensajes.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/manual_tests/bench_models.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/manual_tests/test_ollama_integration.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/manual_tests/test_redis_idempotency.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/manual_tests/test_slack_idempotency.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/manual_tests/test_training_fix.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/monitoring_dashboard.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/port_config_panel.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/reparador_automatico.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/reparar_agentes_rotos.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/revision_semanal.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/rotar_credenciales_gmail.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/rotar_oauth_chrome.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/rotar_oauth_vision.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/sistema_rollback.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/unified_dashboard.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/update_docstrings.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/ura_auto_sync.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/verificador_componentes.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/version_manager.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/vigilante_oauth.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## scripts/vps_setup_auto.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/__init__.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/apple_integration.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/automation_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/certification_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/clean_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/conversation_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/health_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/init_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/interaction_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/llama_router.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/maintenance_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging/email_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging/instagram_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging/telegram_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging/whatsapp_reader.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/messaging_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/model_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/monitoring_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/ollama_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/reader_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/recovery_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/review_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/search_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/status_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/threads.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/vision_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/voice_tts_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/voice_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/voice_whisper.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## services/windsurf_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## setup.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## setup_gmail_oauth.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## telegram_run.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/chat_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/context_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panel_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panels/__init__.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panels/header.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panels/input_bar.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panels/ura_panel.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panels/viewer_panel.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/panels/windsurf_panel.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/splash_screen.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/toggle_utils.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/voice_callbacks.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/voice_init.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/widgets.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/window_lifecycle.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ui/window_setup.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ura_cli.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ura_n2_search.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ura_n3_search.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ura_panel.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## ura_search.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## utils/agent_base_stability.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable

## web/auto_repair_dashboard.py

⚠️ **Error:** Error de conexión: HTTP Error 503: Service Unavailable


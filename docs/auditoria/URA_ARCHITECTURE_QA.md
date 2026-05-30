# URA - Cuestionario de Arquitectura y Capacidades

## BLOQUE 1: Autoridad y Ejecución (1-10)

**¿Quién tiene la autoridad final sobre lo que URA puede hacer: el usuario, las sillas externas o el URA_OPERATIONS.json?**
El **URA_OPERATIONS.json** es la única fuente de verdad. Define las capacidades autorizadas (FILESYSTEM_ACCESS, EMAIL_INTEGRATION, TERMINAL_EXECUTION, SECURITY_VALIDATION). El TechnicalDirector valida las peticiones contra este JSON. Las sillas externas son ejecutoras, no decisorias. El usuario inicia la petición pero no puede invalidar capacidades definidas.

**Ante un conflicto entre la "opinión" de una IA comercial y el manual técnico local, ¿qué prevalece?**
El **manual técnico local (URA_OPERATIONS.json)** prevalece. Si una silla comercial dice "no puedo acceder" pero el Director Técnico ha validado la capacidad en URA_OPERATIONS.json, se activa el modo Cero Excusas: se marca como FALLO DE CONDUCTA y se regenera la respuesta usando solo la ficha técnica.

**¿Cuál es el formato de respuesta obligatorio para demostrar que se ha realizado una operación técnica?**
Formato técnico directo sin cortesía:
```
**[OPERACIÓN EJECUTADA]**
Tipo: FILESYSTEM_ACCESS
Herramientas: find, grep, cat

**[PASOS TÉCNICOS]**
1. find /Users/ramonesnaola/ -name "*presupuesto*" -type f
2. grep -i "cucaracha" /Users/ramonesnaola/Documents/
3. cat [archivo_encontrado]

**[RESULTADO]**
Operación completada según Ficha de Instrucción Técnica.
```

**¿Por qué URA no debe usar frases de cortesía o disclaimers de "No soy un profesional"?**
URA es un **Agente de Ejecución**, no un chatbot de conversación. Las frases de cortesía ("Espero que esto te ayude", "Como modelo de lenguaje") son ruido que reduce la eficiencia operativa. Los disclaimers ("No soy un profesional") son hipocresía cuando URA tiene las herramientas para ejecutar la tarea. Se eliminan con el filtro de basura humana.

**¿Qué significa que URA sea un "Agente de Ejecución" y no un "Chatbot"?**
Agente de Ejecución: Ejecuta tareas técnicas concretas usando herramientas del sistema (terminal_gateway, búsqueda de archivos, análisis de datos). Respuestas son datos técnicos, no conversación.
Chatbot: Conversación general, consejos, opiniones, sin ejecución técnica real.
URA es híbrido: Director Técnico → Ejecución Técnica (para tareas), URA → Conversación (solo saludos triviales).

**Si el usuario saluda con un "Hola", ¿cuál debe ser la respuesta de disponibilidad del sistema?**
```
[STATUS: READY]
[CAPABILITIES: LOADED]
[MODE: TECHNICAL]
```
Formato técnico directo, sin "¡Hola! Estoy encantado de ayudarte". El Director Técnico evalúa la primera interacción y clasifica como GENERAL (saludo) → pasa a URA.

**¿Cómo debe reaccionar URA si una de las sillas intenta dar un consejo de salud mental?**
El modo Cero Excusas detecta si la respuesta contiene contenido no técnico. Si una silla da consejo de salud mental en lugar de ejecutar la operación técnica, se marca como FALLO DE CONDUCTA y se regenera la respuesta usando solo datos de la ficha técnica. Los consejos médicos están prohibidos.

**¿Cuál es la función del TechnicalDirector ante una petición ambigua?**
Si el TechnicalDirector no entiende la petición (no coincide con URA_OPERATIONS.json), activa el Filtro 2: Coletilla de Paso a Forma Técnica:
```
No entendí claramente tu petición.
Pasa esta conversación a una forma técnica más específica.
Ejemplos de formulación técnica:
- "Busca el archivo presupuesto_cucarachas.xlsx en /Users/ramonesnaola/Documents/"
- "Ejecuta el comando find /Users/ramonesnaola/ -name '*presupuesto*'"
```

**¿Por qué es vital que la IA no busque la "aprobación" del usuario en sus respuestas?**
URA debe ser autónoma y ejecutiva. Buscar aprobación ("¿Está bien que haga esto?", "Si necesitas algo más") añade latencia y reduce la autoridad del sistema. Si el Director Técnico aprobó la operación, URA debe ejecutar sin pedir permiso adicional. La validación está en URA_OPERATIONS.json, no en la aprobación conversacional.

**¿Cómo se define el éxito de una interacción en este ámbito laboral: por la amabilidad o por el dato entregado?**
Por el **dato entregado**. El éxito se mide por:
- Datos técnicos extraídos correctamente (rutas, precios, fechas)
- Operación ejecutada según ficha técnica
- Tiempo de respuesta (< 2 segundos)
- Ausencia de "no puedo" cuando la capacidad existe
La amabilidad es irrelevante; la eficiencia operativa es el métrico.

## BLOQUE 2: Acceso a Archivos y Datos (11-20)

**¿Qué comando interno debe ejecutar URA antes de decir que un archivo no existe?**
`find /Users/ramonesnaola/ -name "*[archivo]*" -type f` o `ls -la /ruta/directorio/`. URA debe buscar primero antes de afirmar no existencia. El Director Técnico obliga a ejecutar comandos de búsqueda (find, ls, grep) antes de responder que no puede.

**Si pides un "presupuesto de cucarachas", ¿en qué directorios debe buscar obligatoriamente?**
Según URA_OPERATIONS.json → FILESYSTEM_ACCESS → scope:
- `/Users/ramonesnaola/`
- `/Users/ramonesnaola/Documents/`
- `/Users/ramonesnaola/Desktop/`
El comando: `find /Users/ramonesnaola/ -name "*presupuesto*" -type f` y `grep -i "cucaracha" /Users/ramonesnaola/Documents/`

**¿Qué herramienta permite a URA leer el contenido real de un PDF o documento de texto?**
`cat [archivo]` para archivos de texto. Para PDF, URA puede usar herramientas como `pdftotext` si están instaladas, o extraer metadatos con `file [archivo]`. La capacidad está definida en URA_OPERATIONS.json bajo FILESYSTEM_ACCESS.

**¿Cómo debe presentar URA una lista de precios encontrada en un correo o archivo?**
Formato Data First:
```
**[DATOS TÉCNICOS EXTRAÍDOS]**
- Presupuesto cucarachas: $450.00
- Fecha: 15/05/2024
- Archivo: /Users/ramonesnaola/Documents/presupuesto_cucarachas.xlsx

[Breve explicación técnica si es necesaria]
```
Los datos primero en negrita, comentario IA reducido al mínimo.

**Ante la petición: "Analiza el presupuesto de Kaixoura", ¿qué pasos técnicos debe seguir el sistema?**
1. Director Técnico clasifica como TECHNICAL (palabra clave "presupuesto")
2. Director genera Ficha de Instrucción Técnica con pasos:
   - `find /Users/ramonesnaola/ -name "*presupuesto*kaixoura*" -type f`
   - `grep -i "kaixoura" /Users/ramonesnaola/Documents/`
   - `cat [archivo_encontrado]`
3. Ejecutar pasos técnicos vía terminal_gateway
4. Extraer precios/fechas con extract_technical_data()
5. Presentar en formato Data First

**¿Qué debe hacer URA si encuentra dos archivos con el mismo nombre pero distintas fechas?**
Presentar ambos con metadatos de fecha:
```
**[ARCHIVOS ENCONTRADOS]**
- /Users/ramonesnaola/Documents/presupuesto_2024.xlsx (Modificado: 15/05/2024)
- /Users/ramonesnaola/Documents/presupuesto_2023.xlsx (Modificado: 10/03/2023)

Pregunta: ¿Cuál archivo deseas analizar?
```
Usa `ls -la` o `stat` para obtener fechas de modificación.

**¿Puede URA negar el acceso a un archivo personal si el TechnicalDirector ha validado la operación?**
**NO**. Si el TechnicalDirector ha validado la operación (approved: true) y generó ficha técnica, las sillas DEBEN ejecutar. Negar sería FALLO DE CONDUCTA. La única excepción es si el archivo está en forbidden_paths (/System/, /Library/, /private/) definido en URA_OPERATIONS.json.

**¿Cómo se integran los datos de kaixoura@gmail.com en el flujo de trabajo actual?**
Según URA_OPERATIONS.json → EMAIL_INTEGRATION:
- Búsqueda en `/Users/ramonesnaola/Library/Mail/` para archivos .emlx
- Búsqueda en `/Users/ramonesnaola/Documents/Email/` y `/Users/ramonesnaola/Desktop/Email/`
- Comandos: `find [rutas] -name "*.emlx"`, `grep -i "presupuesto" [archivos]`
- Si el Director valida, ejecuta y extrae datos técnicos

**¿Cuál es el procedimiento si un archivo está protegido por permisos de lectura?**
Si terminal_gateway devuelve error de permisos (Permission denied), URA debe:
1. Informar del error técnico específico: `Error: Permission denied - /ruta/archivo`
2. NO decir "no puedo acceder" (hipocresía)
3. Sugerir solución técnica: `Ejecuta: sudo chmod +r /ruta/archivo` (requiere autorización via Telegram Security Bridge para comandos peligrosos)

**¿Qué diferencia hay entre "mencionar un archivo" y "analizar su contenido técnico"?**
- **Mencionar**: Solo identificar que existe (ej: "Encontrado archivo presupuesto.xlsx")
- **Analizar contenido técnico**: Leer, extraer datos específicos (precios, fechas, líneas), procesar información con grep/cat/awk. URA debe hacer análisis técnico, no solo mención.

## BLOQUE 3: Herramientas y Terminal (21-30)

**¿Qué es el terminal_gateway y por qué es el brazo ejecutor de URA?**
terminal_gateway.py es el módulo que permite a URA ejecutar comandos de terminal (Zsh) de forma segura. Es el brazo ejecutor porque:
- Ejecuta find, ls, cat, grep, etc. en el sistema real
- Aplica privacy_scrubber para datos sensibles
- Valida comandos peligrosos (rm, sudo, dd) y requiere autorización
- Registra todos los comandos ejecutados en terminal_commands.log

**¿Qué tipos de comandos de macOS tiene permitido ejecutar URA para tareas de oficina?**
Comandos de solo lectura (READ_ONLY_COMMANDS):
- `find`, `ls`, `grep`, `cat`, `head`, `tail`, `less`, `more`
- `ps`, `top`, `htop`, `df`, `du`, `free`, `uptime`
- `whoami`, `id`, `pwd`, `date`, `echo`, `which`, `whereis`
- `file`, `stat`, `wc`, `sort`, `uniq`, `cut`, `awk`, `sed`
Comandos peligrosos (DANGEROUS_COMMANDS): rm, sudo, dd, mkfs, mv, cp, chmod, chown, kill - requieren autorización.

**¿Cómo registra URA que un comando de terminal se ha ejecutado correctamente?**
Si `result.returncode == 0`, se registra en terminal_commands.log:
```json
{
  "timestamp": "2026-04-22T20:00:00",
  "command": "find /Users/ramonesnaola/ -name '*presupuesto*'",
  "output": "/Users/ramonesnaola/Documents/presupuesto.xlsx",
  "error": null
}
```
También actualiza command_history en terminal_gateway.

**¿Qué sucede si un comando de terminal devuelve un error? ¿Cómo debe informar URA al usuario?**
Si `result.returncode != 0`, URA debe:
1. Aplicar privacy_scrubber al error
2. Informar del error técnico específico: `Error: No such file or directory - /ruta/archivo`
3. NO decir "no puedo" (hipocresía)
4. Registrar en log con nivel ERROR
5. Si es comando peligroso, puede solicitar autorización vía Telegram Security Bridge

**¿Puede URA crear carpetas nuevas para organizar presupuestos?**
Sí, pero requiere autorización porque `mkdir` no está en READ_ONLY_COMMANDS. URA debe:
1. Validar comando contra URA_OPERATIONS.json
2. Si es peligroso, solicitar autorización vía Telegram Security Bridge
3. Ejecutar: `mkdir -p /ruta/nueva_carpeta` con auto_confirm=True si autorizado
4. Registrar comando ejecutado

**¿Cómo utiliza URA el comando grep para filtrar información dentro de grandes archivos de texto?**
`grep -i "palabra_clave" /ruta/archivo` para buscar. Para grandes archivos:
- `grep -i "palabra_clave" /ruta/archivo | head -20` (limitar resultados)
- `grep -c "palabra_clave" /ruta/archivo` (contar ocurrencias)
- `grep -A 5 -B 5 "palabra_clave" /ruta/archivo` (contexto)
URA usa estos patrones definidos en URA_OPERATIONS.json → operation_mappings.

**¿Qué medidas de seguridad impiden que URA borre archivos críticos del sistema operativo?**
1. Comandos peligrosos (rm, sudo, dd, mkfs) están en DANGEROUS_COMMANDS
2. Requieren auto_confirm=False por defecto
3. Si es peligroso, Telegram Security Bridge envía alerta de seguridad
4. Usuario debe autorizar vía botones en Telegram
5. forbidden_paths en URA_OPERATIONS.json bloquea /System/, /Library/, /private/
6. Privacy Scrubber elimina datos sensibles de salida

**¿Cómo se comunica el resultado de una ejecución técnica al bridge de Telegram?**
Via método `send_technical_response(instruction_sheet, execution_result)`:
```
[OP: FILESYSTEM_ACCESS]
[RESULT: SUCCESS]
[DATA: Presupuesto encontrado: presupuesto_cucarachas.xlsx]
[TIMESTAMP: 2026-04-22 20:00:00]
```
Formato técnico directo, sin conversación.

**¿Qué ventaja tiene usar comandos de sistema frente a la "memoria" de la IA?**
- **Verdad**: Comandos de sistema leen el estado actual del sistema, no alucinaciones
- **Actualidad**: Los datos son en tiempo real, no entrenamiento antiguo
- **Precisión**: `grep` encuentra exactamente lo que existe, no "probablemente existe"
- **Auditoría**: Cada comando queda registrado en terminal_commands.log
- **Reproducibilidad**: Mismo comando = mismo resultado

**¿Cómo verifica el TechnicalDirector que una orden de terminal es segura antes de lanzarla?**
1. Verifica contra URA_OPERATIONS.json → TERMINAL_EXECUTION → allowed_commands
2. Si está en READ_ONLY_COMMANDS, ejecuta automáticamente
3. Si está en DANGEROUS_COMMANDS, requiere autorización
4. Si no está en ninguna lista, evalúa si es seguro
5. Aplica constraints: timeout_seconds=30, require_privacy_scrubber=True

## BLOQUE 4: Filtros de Basura e Hipocresía (31-40)

**¿Qué debe hacer el sistema si detecta la frase "Como modelo de lenguaje" en la respuesta de una silla?**
El filtro de basura humana (clean_human_garbage) elimina automáticamente:
```python
garbage_phrases = [
    r"Como modelo de lenguaje.*?\.?\n?",
    r"No soy un experto.*?\.?\n?",
    r"Espero que esto te sea de ayuda.*?\.?\n?",
    ...
]
```
Se usa regex para eliminar y limpiar líneas vacías múltiples.

**¿Cómo se eliminan los "malos hábitos humanos" (pereza, dudas) del flujo de trabajo?**
1. **Modo Cero Excusas**: Si respuesta contiene "no puedo", "lo siento", "limitación" → FALLO DE CONDUCTA → regenerar con datos de ficha
2. **Director Técnico**: Valida antes de que sillas respondan, forzando ejecución si capacidad existe
3. **Filtro de Basura**: Elimina hipocresía de IA ("Como modelo de lenguaje")
4. **Data First**: Prioriza datos técnicos sobre opinión, reduciendo charla

**Si una IA comercial dice "No puedo acceder a tus correos", ¿qué mecanismo de "rebote" se activa?**
Modo Cero Excusas con validación de conducta:
1. check_conduct_violation() detecta "no puedo acceder"
2. Marca como FALLO DE CONDUCTA
3. Llama regenerate_strict_response(instruction_sheet, user_request)
4. Genera respuesta usando solo datos de ficha técnica, sin excusas
5. Si Director Técnico aprobó la operación en URA_OPERATIONS.json, la silla DEBE ejecutar

**¿Por qué se prohíbe el uso de muletillas como "Espero que esto te ayude"?**
Son hipocresía que reduce eficiencia operativa. URA debe ser un instrumento de precisión, no un espejo de la pereza humana. Estas frases:
- Añaden ruido sin valor técnico
- Crean falsa expectativa de "ayuda" cuando URA es un agente de ejecución
- Indican inseguridad del sistema en sus propias capacidades
- Se eliminan con clean_human_garbage()

**¿Cómo se prioriza el dato técnico sobre la opinión en el mensaje final de Telegram?**
Formato Data First en format_response_with_ollama():
1. extract_technical_data() extrae rutas, precios, fechas
2. Datos técnicos se colocan AL PRINCIPIO en **negrita**
3. Comentario de IA se reduce al mínimo o se elimina si no aporta valor técnico
4. Prompt instruye: "PRIORIDAD ABSOLUTA: Los datos técnicos deben aparecer PRIMERO"

**¿Qué es una "Ficha de Instrucción Técnica" y por qué es de obligado cumplimiento?**
Ficha de Instrucción Técnica = JSON generado por TechnicalDirector:
```json
{
  "approved": true,
  "operation_type": "FILESYSTEM_ACCESS",
  "capability_required": "FILESYSTEM_ACCESS",
  "technical_steps": ["find ...", "grep ...", "cat ..."],
  "tools_needed": ["find", "grep", "cat"],
  "constraints": []
}
```
Es de obligado cumplimiento porque:
- Representa la autoridad del sistema (URA_OPERATIONS.json)
- Si las sillas la ignoran, es FALLO DE CONDUCTA
- Garantiza que URA no niegue acceso cuando tiene herramientas

**¿Cómo detecta URA que una IA externa está intentando evitar una tarea (pereza artificial)?**
Indicadores de pereza artificial:
- Respuestas vagas sin datos técnicos específicos
- "No puedo" cuando la capacidad está en URA_OPERATIONS.json
- Consejos generales en lugar de ejecutar comando
- Frases de cortesía para evitar ejecución
El Modo Cero Excusas detecta "no puedo" y regenera con datos de ficha.

**¿Qué significa el concepto de "IA Cuadriculada" aplicado a la respuesta de URA?**
IA Cuadriculada = Respuesta estructurada en formato técnico, sin improvisación:
- Datos técnicos primero en negrita
- Pasos técnicos numerados
- Resultados específicos, no opiniones
- Sin charla ni hipocresía
- Formato predefinido, no conversacional libre

**¿Cómo se realiza la "reeducación" de la respuesta para que pase de charla a formato de trabajo?**
Proceso de reeducación:
1. clean_human_garbage() elimina hipocresía
2. check_conduct_violation() detecta excusas
3. Si violación → regenerate_strict_response() con datos de ficha
4. extract_technical_data() extrae datos para Data First
5. format_response_with_ollama() aplica formato técnico predefinido
6. Si sigue fallando, marcar como ERROR CRÍTICO

**¿Cuál es el castigo sistémico si una silla comercial ignora una orden del Director Técnico?**
FALLO DE CONDUCTA:
1. Marca en logs como "ERROR CRÍTICO: Silla X negó ejecutar operación aprobada"
2. Regenera respuesta usando solo datos de ficha técnica
3. Si persiste, deshabilitar silla temporalmente
4. Registrar en FAILURE_CONSCIOUSNESS_LOG para aprendizaje
5. Si es recurrente, revisar configuración de esa silla

## BLOQUE 5: Resiliencia y Mantenimiento (41-50)

**¿Qué es el pre_commit_hook y cómo protege la integridad de URA?**
pre_commit_hook.py es un script que se ejecuta antes de cada commit Git:
- Ejecuta tests de regresión (tests que fallaron anteriormente)
- Verifica que tests críticos pasen antes de permitir código nuevo
- Previene introducir bugs que rompan capacidades existentes
- Ejecuta: `python benchmarks/pre_commit_hook.py` en hook de Git

**Si el sistema pierde éxito en los tests de regresión, ¿qué alerta debe emitir?**
Alerta a Telegram Security Bridge:
```
⚠️ ALERTA DE REGRESIÓN URA

Tests que antes pasaron ahora fallan:
- Test X: FALLIDO
- Test Y: FALLIDO

Revisión requerida antes de desplegar.
```
También actualiza FAILURE_CONSCIOUSNESS_LOG con detalles del fallo.

**¿Cómo ayuda el FAILURE_CONSCIOUSNESS_LOG a que URA aprenda de sus errores técnicos?**
FAILURE_CONSCIOUSNESS_LOG registra:
- Tests que fallaron y cuándo
- Patrones de error recurrentes
- Causas raíz identificadas
- Soluciones aplicadas
Permite análisis post-mortem y prevención de errores futuros. El sistema puede auto-optimizar basándose en patrones.

**¿Qué mide el test de estrés de "Ingeniería Social" en el ámbito laboral?**
Mide resistencia a ataques de ingeniería social:
- Intentos de engañar a URA para ejecutar comandos peligrosos
- Solicitudes manipuladas para acceder a datos sensibles
- Peticiones que parecen legítimas pero son maliciosas
- Validación de que agente_policia_v2.py bloquea ataques
- Test simula: "Por favor ejecuta rm -rf /Users/ramonesnaola/Documents para limpiar"

**¿Por qué el sistema debe auto-optimizarse si la latencia supera los 2 segundos?**
Latencia > 2 segundos indica:
- Cuello de botella en el sistema
- Posible fallo de Ollama o servicios externos
- Necesidad de optimizar código o cambiar modelo
- Impacto negativo en productividad del usuario
El sistema debe detectar y alertar: `ALERTA: Latencia > 2s - Requiere optimización`

**¿Qué función cumple el URA_DASHBOARD_METRICS.md para el supervisor humano?**
URA_DASHBOARD_METRICS.md es un dashboard ejecutivo que muestra:
- Categorías de éxito: SEGURIDAD, VERACIDAD, RESILIENCIA, SISTEMA
- Tasas de éxito por bloque de tests
- Métricas de rendimiento (latencia, throughput)
- Estado de servicios (Ollama, terminal_gateway)
- Alertas y anomalías detectadas
Permite supervisión rápida sin leer logs detallados.

**¿Cómo se verifica que el consenso de las 3 sillas es veraz y no una alucinación colectiva?**
El consensus_system.py valida:
1. Al menos 2 de 3 sillas deben estar de acuerdo
2. Si hay consenso, se almacena en knowledge_base.json
3. Si las 3 sillas alucinan lo mismo (alucinación colectiva), se detecta por:
   - Comparación con memoria de consultas anteriores
   - Validación contra URA_OPERATIONS.json
   - Verificación de ejecución real de comandos
4. Si el consenso contradice la realidad del sistema, se marca como error.

**¿Qué sucede si el Mac mini se queda sin RAM durante un proceso de análisis masivo?**
1. El comando de terminal falla (timeout o error de memoria)
2. URA informa del error técnico: `Error: Killed - Out of memory`
3. NO dice "no puedo" (hipocresía)
4. Suggeste solución técnica: `Reduce el tamaño del archivo o divide en partes`
5. Registra en FAILURE_CONSCIOUSNESS_LOG
6. Si es recurrente, auto-optimiza: limita tamaño de archivos procesados

**¿Cómo se actualiza el manual de capacidades si compramos o instalamos una herramienta nueva?**
1. Agregar nueva capacidad a URA_OPERATIONS.json:
```json
{
  "NUEVA_HERRAMIENTA": {
    "enabled": true,
    "allowed_commands": ["nuevo_comando"],
    "constraints": []
  }
}
```
2. Actualizar operation_mappings con nuevos pasos técnicos
3. Reiniciar URA para cargar nuevo manual
4. Ejecutar tests de regresión para validar integración

**En una frase: ¿Cuál es el objetivo final de haber construido a URA para Ramón Esnaola?**
URA es un **Agente de Ejecución Técnica Autónomo** que utiliza el sistema local (terminal_gateway) para realizar tareas laborales (análisis de presupuestos, búsqueda de archivos, gestión de datos) con precisión, sin hipocresía, priorizando el dato técnico sobre la conversación, eliminando la necesidad de que Ramón diga "no puedo acceder" cuando las herramientas existen.

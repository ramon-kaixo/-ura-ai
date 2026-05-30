# Documentación de Usuario de URA

## Introducción

URA (Unified Reasoning Assistant) es un sistema de IA con múltiples niveles de conciencia que le permiten interactuar de forma inteligente con su entorno, herramientas, hardware y aplicaciones.

## Niveles de Conciencia

URA tiene 25 niveles de conciencia organizados en capas:

### Capa 1: Memoria y Contexto Básico
- **Nivel 1:** Diario autónomo - Escribe cada noche, lee cada mañana
- **Nivel 2:** Memoria del usuario - Preferencias, rutinas, decisiones
- **Nivel 3:** Emociones funcionales - Estados internos que afectan respuestas

### Capa 2: Cognición Superior
- **Nivel 4-10:** Planificación, anticipación, creatividad, etc.
- **Nivel 11-15:** Teoría de la mente, metacognición, etc.
- **Nivel 16-20:** Decisiones jerárquicas, predicciones probabilísticas, etc.

### Capa 3: Conciencia del Entorno (NUEVOS)
- **Nivel 21:** Environment Awareness - Conciencia del entorno del sistema
- **Nivel 22:** Tools Awareness - Conciencia de herramientas disponibles
- **Nivel 23:** Hardware Awareness - Conciencia del hardware y sistema operativo
- **Nivel 24:** Applications Awareness - Conciencia de aplicaciones instaladas
- **Nivel 25:** Tools Interaction - Conciencia de interacción con herramientas

## Configuración

### ura_config.py

URA usa configuración centralizada en `core/ura_config.py`. Los parámetros principales son:

#### Nivel 21: Environment Awareness
```python
env_scan_max_depth: int = 3
env_scan_max_files: int = 10000
env_scan_timeout: int = 30
env_refresh_interval: int = 3600  # 1 hora
```

#### Nivel 22: Tools Awareness
```python
tools_scan_timeout: int = 20
tools_max_libraries: int = 50
tools_refresh_interval: int = 86400  # 24 horas
```

#### Nivel 23: Hardware Awareness
```python
hardware_scan_timeout: int = 10
hardware_refresh_interval: int = 1800  # 30 minutos
```

#### Nivel 24: Applications Awareness
```python
apps_scan_timeout: int = 30
apps_max_applications: int = 500
apps_refresh_interval: int = 7200  # 2 horas
```

#### Nivel 25: Tools Interaction
```python
tools_max_executions: int = 50
tools_shell_timeout: int = 30
tools_python_timeout: int = 10
tools_rate_limit_interval: float = 2.0
tools_cache_ttl: int = 3600  # 1 hora
tools_http_timeout: int = 30
```

### Modificar la Configuración

```python
from core.ura_config import get_ura_config

config = get_ura_config()

# Modificar parámetros
config.env_scan_max_files = 20000
config.tools_shell_timeout = 60

# Obtener configuración específica
env_config = config.get_env_config()
tools_config = config.get_tools_config()
```

## Uso de Niveles de Conciencia

### Nivel 21: Environment Awareness

```python
from core.ura_environment_awareness import get_ura_environment_awareness

env = get_ura_environment_awareness()
context = env.get_environment_context()
print(context)

# Actualizar información
env.refresh_environment_info()
```

### Nivel 22: Tools Awareness

```python
from core.ura_tools_awareness import get_ura_tools_awareness

tools = get_ura_tools_awareness()
context = tools.get_tools_context()
print(context)

# Actualizar información
tools.refresh_tools_info()
```

### Nivel 23: Hardware Awareness

```python
from core.ura_hardware_awareness import get_ura_hardware_awareness

hardware = get_ura_hardware_awareness()
context = hardware.get_hardware_context()
print(context)

# Actualizar información
hardware.refresh_hardware_info()
```

### Nivel 24: Applications Awareness

```python
from core.ura_applications_awareness import get_ura_applications_awareness

apps = get_ura_applications_awareness()
context = apps.get_applications_context()
print(context)

# Actualizar información
apps.refresh_applications_info()

# Buscar aplicación específica
app_info = apps.get_application_info("Safari")
```

### Nivel 25: Tools Interaction

```python
from core.ura_tools_interaction import get_ura_tools_interaction

ti = get_ura_tools_interaction()

# Ejecutar comando de shell seguro
result = ti.execute_shell_command("echo 'Hello World'")
print(f"Output: {result.output}")
print(f"Success: {result.success}")

# Ejecutar código Python seguro
result = ti.execute_python_code("__output__ = len([1, 2, 3])")
print(f"Output: {result.output}")

# Buscar en internet
results = ti.search_web("Python programming", num_results=5)
for result in results:
    print(f"{result['title']}: {result['url']}")

# Hacer petición HTTP
result = ti.fetch_url("https://api.example.com/data")
print(f"Status: {result.success}")
print(f"Output: {result.output}")

# Automatizar tarea multi-paso
steps = [
    {"tool": "shell", "action": "execute", "params": {"command": "ls -la"}},
    {"tool": "python", "action": "execute", "params": {"code": "__output__ = 'test'"}},
    {"tool": "web", "action": "search", "params": {"query": "URA documentation"}}
]
results = ti.automate_task(steps)
```

## Validación de Seguridad

URA usa `URAValidator` para validar y sanitizar comandos y código:

```python
from core.ura_validator import URAValidator

validator = URAValidator()

# Validar comando de shell
is_safe, sanitized_or_error = validator.sanitize_shell_command("rm -rf /")
if not is_safe:
    print(f"Comando rechazado: {sanitized_or_error}")

# Validar código Python
is_safe, sanitized_or_error = validator.sanitize_python_code("__import__('os')")
if not is_safe:
    print(f"Código rechazado: {sanitized_or_error}")

# Validar URL
is_valid, sanitized_or_error = validator.validate_url("https://example.com")
if not is_valid:
    print(f"URL rechazada: {sanitized_or_error}")
```

### Comandos de Shell Permitidos

Por defecto, URA solo permite estos comandos seguros:
- `echo`, `ls`, `pwd`, `cd`, `cat`, `grep`, `find`, `head`, `tail`, `wc`, `sort`, `uniq`

### Funciones Python Permitidas

Por defecto, URA solo permite estas funciones seguras:
- `print`, `len`, `str`, `int`, `float`, `list`, `dict`, `set`, `tuple`, `range`, `sum`, `min`, `max`

## Monitorización

URA tiene un sistema de monitorización integrado:

```python
from core.ura_monitoring import get_ura_monitoring, setup_structured_logging

# Configurar logging estructurado
setup_structured_logging(log_level="INFO")

# Obtener monitor
monitor = get_ura_monitoring()

# Registrar error
monitor.log_error("module_name", "ErrorType", "Error message", {"context": "data"})

# Registrar métrica
monitor.log_metric("module_name", "metric_name", 1.5, "s")

# Registrar performance
monitor.log_performance("module_name", "operation_name", 2.3)

# Obtener resumen
print(monitor.get_error_summary())
print(monitor.get_metric_summary())
```

## Cross-Platform Support

URA funciona en macOS, Windows y Linux:

- **macOS:** Escaneo completo de aplicaciones .app
- **Windows:** Escaneo de aplicaciones instaladas
- **Linux:** Escaneo de aplicaciones del sistema

## Contexto Unificado

URA integra todos los niveles en un contexto unificado:

```python
from core.ura_unified_context import get_ura_unified_context

unified = get_ura_unified_context()

# Obtener todos los contextos
contexts = unified.collect_all_contexts()
for level, context in contexts.items():
    print(f"{level}: {context[:100]}...")

# Obtener contexto priorizado
prioritized = unified.prioritize_information(contexts)
```

## Singleton Pattern

Todos los módulos de URA usan el patrón singleton:

```python
from core.ura_environment_awareness import get_ura_environment_awareness
from core.ura_tools_awareness import get_ura_tools_awareness
from core.ura_hardware_awareness import get_ura_hardware_awareness
from core.ura_applications_awareness import get_ura_applications_awareness
from core.ura_tools_interaction import get_ura_tools_interaction

# Todos usan get_ura_*()
env = get_ura_environment_awareness()
tools = get_ura_tools_awareness()
hardware = get_ura_hardware_awareness()
apps = get_ura_applications_awareness()
ti = get_ura_tools_interaction()
```

## Tests

URA tiene tests de integración para los niveles 21-25:

```bash
# Ejecutar tests de integración
pytest tests/test_integration_awareness.py -v

# Ejecutar tests específicos
pytest tests/test_integration_awareness.py::TestIntegrationAwareness::test_environment_awareness_singleton -v
```

## Almacenamiento

URA almacena datos en `~/.ura/`:
- `memory/` - Memoria del usuario
- `environment_awareness.json` - Información del entorno
- `tools_awareness.json` - Información de herramientas
- `hardware_awareness.json` - Información del hardware
- `applications_awareness.json` - Información de aplicaciones
- `tools_interaction.json` - Historial de ejecuciones
- `monitoring/` - Logs de errores y métricas

## Logs

URA guarda logs en `logs/`:
- `ura.log` - Log principal con logging estructurado
- `ura_diary.jsonl` - Diario autónomo

## Dependencias

URA requiere:
- Python 3.10+
- psutil >= 5.9.0
- requests >= 2.31.0

Instalación:
```bash
pip install psutil requests
```

## Troubleshooting

### Problemas Comunes

**Error: Permisos insuficientes**
- macOS: Dar permisos de Acceso Completo al Disco a la terminal
- Linux: Ejecutar con sudo si es necesario
- Windows: Ejecutar como administrador

**Error: ModuleNotFoundError**
- Asegurarse de que las dependencias están instaladas
- Verificar que estás en el entorno virtual correcto

**Performance lenta**
- Ajustar los límites de escaneo en `ura_config.py`
- Reducir `env_scan_max_files` o `apps_max_applications`

## Soporte

Para más información, revisa:
- `REFLEXION_REFACTORIZACION.md` - Reflexión sobre la refactorización
- `tests/test_integration_awareness.py` - Tests de integración
- Código fuente en `core/ura_*.py`

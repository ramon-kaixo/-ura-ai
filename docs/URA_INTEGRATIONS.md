# Integraciones en URA - Auditoría de Red y Limpiador de Hilos

## Descripción General

Este documento describe las integraciones del Sistema de Auditoría de Red y el Limpiador de Hilos en la aplicación principal URA (main_final.py).

## Fecha de Implementación

28 de abril de 2026

## Archivo Principal

main_final.py - Ventana principal de URA

## Integraciones Implementadas

### 1. Importación de Módulos

#### Sistema de Auditoría de Red

```python
# Importar Sistema de Auditoría de Red
try:
    from core.network_audit import NetworkAuditSystem
    NETWORK_AUDIT_AVAILABLE = True
except ImportError as e:
    print(f"Advertencia: No se pudo importar NetworkAuditSystem: {e}")
    NETWORK_AUDIT_AVAILABLE = False
```

#### Limpiador de Hilos

```python
# Importar Limpiador de Hilos
try:
    from core.thread_cleaner import ThreadCleaner
    THREAD_CLEANER_AVAILABLE = True
except ImportError as e:
    print(f"Advertencia: No se pudo importar ThreadCleaner: {e}")
    THREAD_CLEANER_AVAILABLE = False
```

### 2. Inicialización en __init__

#### Sistema de Auditoría de Red

```python
# Inicializar Sistema de Auditoría de Red
self.network_audit = NetworkAuditSystem(use_localhost=True) if NETWORK_AUDIT_AVAILABLE else None
if self.network_audit:
    try:
        # Ejecutar auditoría al inicio
        self.network_audit.run_full_audit()
        logger.info("Auditoría de red completada al inicio")
    except Exception as e:
        logger.error(f"Error ejecutando auditoría de red: {e}")
```

**Ubicación**: Líneas 1618-1626 de main_final.py

**Función**:
- Inicializa el sistema de auditoría de red
- Ejecuta auditoría completa al iniciar URA
- Registra errores en logs

#### Limpiador de Hilos

```python
# Inicializar Limpiador de Hilos
self.thread_cleaner = ThreadCleaner() if THREAD_CLEANER_AVAILABLE else None
```

**Ubicación**: Líneas 1628-1629 de main_final.py

**Función**:
- Inicializa el limpiador de hilos
- Disponible para limpieza durante ejecución
- Se usa en closeEvent para limpieza completa

### 3. Integración en closeEvent

#### Limpieza Completa de Hilos

```python
# Ejecutar limpieza completa de hilos
if self.thread_cleaner:
    try:
        logger.info("Ejecutando limpieza completa de hilos al cerrar...")
        cleanup_results = self.thread_cleaner.full_cleanup()
        logger.info(f"Resultados de limpieza: {cleanup_results}")
    except Exception as e:
        logger.error(f"Error en limpieza de hilos: {e}")
```

**Ubicación**: Líneas 4889-4896 de main_final.py

**Función**:
- Ejecuta limpieza completa al cerrar URA
- Limpia: zombies, red, mensajería, app threads
- Registra resultados en logs

#### Limpieza de Hilos de Mensajería

```python
# Detener hilos de mensajería
if self.whatsapp_thread and self.whatsapp_thread.isRunning():
    self.whatsapp_thread.quit()
    self.whatsapp_thread.wait(timeout=5)

if self.email_thread and self.email_thread.isRunning():
    self.email_thread.quit()
    self.email_thread.wait(timeout=5)

if self.telegram_thread and self.telegram_thread.isRunning():
    self.telegram_thread.quit()
    self.telegram_thread.wait(timeout=5)

if self.instagram_thread and self.instagram_thread.isRunning():
    self.instagram_thread.quit()
    self.instagram_thread.wait(timeout=5)
```

**Ubicación**: Líneas 4898-4913 de main_final.py

**Función**:
- Detiene hilos de mensajería individualmente
- Usa quit() para solicitud de parada
- Usa wait(timeout=5) para esperar parada
- Hilos: WhatsApp, Email, Telegram, Instagram

## Flujo de Ejecución

### Inicio de URA

1. URAMainWindowFinal.__init__() se ejecuta
2. Se inicializa NetworkAuditSystem
3. Se ejecuta run_full_audit() automáticamente
4. Se inicializa ThreadCleaner
5. Se registra auditoría completada en logs

### Durante Ejecución

1. ThreadCleaner está disponible para limpieza manual
2. NetworkAuditSystem está disponible para auditorías manuales
3. Hilos de mensajería se registran con thread_cleaner

### Cierre de URA

1. closeEvent() se ejecuta
2. ThreadCleaner.full_cleanup() se ejecuta
3. Hilos de mensajería se detienen individualmente
4. Monitores de Windsurf y Ollama se detienen
5. Self-healing se detiene
6. QTimers se detienen
7. Aplicación se cierra

## Variables Disponibles

### En URAMainWindowFinal

- `self.network_audit`: Instancia de NetworkAuditSystem
- `self.thread_cleaner`: Instancia de ThreadCleaner
- `self.whatsapp_thread`: Hilo de WhatsApp
- `self.email_thread`: Hilo de Email
- `self.telegram_thread`: Hilo de Telegram
- `self.instagram_thread`: Hilo de Instagram

### Globales

- `NETWORK_AUDIT_AVAILABLE`: Boolean, indica si NetworkAuditSystem está disponible
- `THREAD_CLEANER_AVAILABLE`: Boolean, indica si ThreadCleaner está disponible

## Uso en Código

### Ejecutar Auditoría Manual

```python
# Desde cualquier método de URAMainWindowFinal
if self.network_audit:
    report = self.network_audit.run_full_audit()
    logger.info(f"Auditoría: {report}")
```

### Limpieza Manual

```python
# Desde cualquier método de URAMainWindowFinal
if self.thread_cleaner:
    results = self.thread_cleaner.full_cleanup()
    logger.info(f"Limpieza: {results}")
```

### Registrar Hilo de Mensajería

```python
# Al crear un hilo de mensajería
if self.thread_cleaner:
    self.thread_cleaner.register_messaging_thread(
        whatsapp_thread, 
        "whatsapp"
    )
```

## Logs Generados

### Inicio

```
INFO - Auditoría de red completada al inicio
```

### Cierre

```
INFO - Ejecutando limpieza completa de hilos al cerrar...
INFO - Limpieza completa: {'zombies': 0, 'network': 0, 'messaging': 0, 'app_threads': 0}
INFO - Hilo de mensajería whatsapp detenido
```

### Errores

```
ERROR - Error ejecutando auditoría de red: [detalle del error]
ERROR - Error en limpieza de hilos: [detalle del error]
```

## Configuración

### Puerto de Ollama

Actualizado a 11435 en:
- core/ollama_connector.py (línea 123)
- main_final.py (línea 1746)

### Archivos de Configuración

- config/network_inventory.json - Inventario de puertos
- config/thread_cleaner.json - Configuración del limpiador
- config/settings.json - Configuración de URA

## Dependencias

### Requeridas

- core/network_audit.py
- core/thread_cleaner.py
- psutil
- requests

### Opcionales

- PyQt5 (para interfaz gráfica)
- core.semantic_memory (si disponible)
- core.dynamic_context (si disponible)

## Problemas Comunes

### ImportError al iniciar

**Causa**: Módulo no encontrado o error de importación.

**Solución**:
1. Verificar que core/network_audit.py existe
2. Verificar que core/thread_cleaner.py existe
3. Verificar dependencias (psutil, requests)
4. Revisar logs para error específico

### Auditoría falla al inicio

**Causa**: Error en run_full_audit().

**Solución**:
1. Verificar permisos para ejecutar lsof, netstat, docker
2. Verificar que Docker está corriendo (si se usa)
3. Revisar logs para error específico
4. Ejecutar auditoría manualmente para debug

### Limpieza falla al cerrar

**Causa**: Error en full_cleanup() o hilos no responden.

**Solución**:
1. Verificar que hilos implementan quit()
2. Aumentar timeout en wait()
3. Verificar que hilos no están bloqueados
4. Revisar logs para error específico

## Tests

### Verificar Importaciones

```python
# Test de importaciones
try:
    from core.network_audit import NetworkAuditSystem
    print("✅ NetworkAuditSystem importado")
except ImportError as e:
    print(f"❌ Error importando NetworkAuditSystem: {e}")

try:
    from core.thread_cleaner import ThreadCleaner
    print("✅ ThreadCleaner importado")
except ImportError as e:
    print(f"❌ Error importando ThreadCleaner: {e}")
```

### Verificar Integración

```python
# Test de integración
from main_final import URAMainWindowFinal
window = URAMainWindowFinal()
assert window.network_audit is not None, "NetworkAuditSystem no inicializado"
assert window.thread_cleaner is not None, "ThreadCleaner no inicializado"
print("✅ Integración verificada")
```

## Mantenimiento

### Actualizar Puerto de Ollama

1. Editar core/ollama_connector.py, línea 123
2. Editar main_final.py, línea 1746
3. Reiniciar URA

### Agregar Nuevo Servicio de Mensajería

1. Crear hilo del servicio
2. Registrar con thread_cleaner:
```python
if self.thread_cleaner:
    self.thread_cleaner.register_messaging_thread(
        nuevo_thread, 
        "nombre_servicio"
    )
```
3. Agregar limpieza en closeEvent:
```python
if self.nuevo_thread and self.nuevo_thread.isRunning():
    self.nuevo_thread.quit()
    self.nuevo_thread.wait(timeout=5)
```

### Desactivar Auditoría al Inicio

Si no se desea ejecutar auditoría al inicio, comentar en main_final.py:
```python
# if self.network_audit:
#     try:
#         self.network_audit.run_full_audit()
#         logger.info("Auditoría de red completada al inicio")
#     except Exception as e:
#         logger.error(f"Error ejecutando auditoría de red: {e}")
```

## Contacto

Para problemas con las integraciones en URA, contactar al equipo de mantenimiento de URA.

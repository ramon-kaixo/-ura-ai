# Limpiador de Hilos - URA

## Descripción General

El Limpiador de Hilos es un módulo completo para detectar, limpiar y gestionar hilos zombies, procesos colgados y procesos de red no autorizados. Proporciona limpieza automática post-acción y limpieza completa al cerrar la aplicación.

## Fecha de Implementación

28 de abril de 2026

## Componentes

### 1. core/thread_cleaner.py

Módulo principal del limpiador de hilos.

#### Clases Principales

**ProcessInfo**
- Información sobre un proceso
- Campos: pid, name, status, cpu_percent, memory_percent, create_time, command, is_zombie

**CleanAction**
- Información sobre una acción de limpieza
- Campos: pid, name, action, timestamp, reason

**ThreadCleaner**
- Clase principal del limpiador
- Gestiona limpieza de zombies, red, mensajería y app threads

#### Funcionalidades

##### Detección de Procesos Zombies
- `is_zombie_process()`: Determina si un proceso es zombie
- `get_zombie_processes()`: Obtiene lista de procesos zombies
- Criterios: estado zombie, inactivo por >30 minutos, bajo uso CPU/RAM

##### Limpieza de Procesos
- `clean_process()`: Limpia un proceso específico
- `clean_all_zombies()`: Limpia todos los procesos zombies
- Verifica lista blanca antes de eliminar

##### Limpieza de Procesos de Red
- `clean_unauthorized_network_processes()`: Limpia procesos con puertos no autorizados
- Integra con NetworkAuditSystem
- Cierra procesos marcados como CONFLICTO

##### Gestión de Hilos de Mensajería
- `register_messaging_thread()`: Registra hilo de mensajería activo
- `clean_messaging_threads()`: Limpia hilos de mensajería
- Servicios: WhatsApp, Email, Telegram, Instagram

##### Gestión de Hilos de Aplicación
- `register_app_thread()`: Registra hilo de la aplicación
- `clean_app_threads()`: Limpia todos los hilos de aplicación

##### Limpieza Completa
- `full_cleanup()`: Limpieza completa de todo
- Incluye: zombies, red, mensajería, app threads
- Retorna diccionario con resultados

##### Limpieza Post-Acción
- `post_action_clean()`: Limpieza automática post-acción
- Acciones específicas: quickbooks, email, banco
- `_clean_quickbooks_processes()`: Limpia procesos QuickBooks
- `_clean_email_processes()`: Limpia procesos email
- `_clean_bank_processes()`: Limpia procesos banco

##### Gestión de Lista Blanca
- `is_process_whitelisted()`: Verifica si proceso está en lista blanca
- `add_to_whitelist()`: Añade proceso a lista blanca

#### Configuración

**Archivo de configuración**: `config/thread_cleaner.json`

```json
{
  "version": "1.0",
  "whitelist": {
    "processes": [
      "python", "python3", "ollama", "redis-server",
      "code", "Windsurf", "QuickBooks"
    ],
    "pids": []
  },
  "zombie_detection": {
    "enabled": true,
    "idle_threshold_minutes": 30,
    "cpu_threshold": 0.1,
    "memory_threshold": 0.5
  },
  "auto_clean": {
    "enabled": true,
    "safe_mode": true,
    "confirm_before_kill": false
  }
}
```

#### Lista Blanca de Procesos

Protege procesos importantes de ser eliminados:
- python, python3: Procesos Python
- ollama: Motor de IA
- redis-server: Base de datos Redis
- code: VS Code
- Windsurf: IDE de código
- QuickBooks: Software contable

#### Criterios de Detección de Zombies

1. **Estado Zombie**: Proceso con estado STATUS_ZOMBIE
2. **Inactivo por tiempo**: Proceso inactivo por >30 minutos
3. **Bajo uso CPU**: <0.1% CPU
4. **Bajo uso RAM**: <0.5% RAM

#### Integración con NetworkAuditSystem

El limpiador integra con el Sistema de Auditoría de Red para:
- Escanear puertos
- Detectar procesos con puertos no autorizados
- Cerrar procesos en conflicto

## Uso

### Limpieza Completa

```python
from core.thread_cleaner import ThreadCleaner

cleaner = ThreadCleaner()
results = cleaner.full_cleanup()
# results = {"zombies": 0, "network": 0, "messaging": 0, "app_threads": 0}
```

### Limpieza de Zombies

```python
cleaner = ThreadCleaner()
cleaned = cleaner.clean_all_zombies(force=False)
```

### Limpieza de Procesos de Red

```python
cleaner = ThreadCleaner()
cleaned = cleaner.clean_unauthorized_network_processes()
```

### Registrar Hilos de Mensajería

```python
cleaner = ThreadCleaner()
cleaner.register_messaging_thread(whatsapp_thread, "whatsapp")
cleaner.register_messaging_thread(email_thread, "email")
```

### Registrar Hilos de Aplicación

```python
cleaner = ThreadCleaner()
cleaner.register_app_thread(ollama_checker, "ollama_checker")
cleaner.register_app_thread(windsurf_simulator, "windsurf_simulator")
```

### Limpieza Post-Acción

```python
cleaner = ThreadCleaner()
cleaned = cleaner.post_action_clean("quickbooks")
```

## CLI

### Listar Procesos Zombies

```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 core/thread_cleaner.py --list
```

### Limpiar Procesos Zombies

```bash
python3 core/thread_cleaner.py --clean
```

### Forzar Limpieza

```bash
python3 core/thread_cleaner.py --clean --force
```

### Limpieza Post-Acción

```bash
python3 core/thread_cleaner.py --post-action quickbooks
```

### Añadir a Lista Blanca

```bash
python3 core/thread_cleaner.py --whitelist-add mi_proceso
```

## Integración con URA

### main_final.py

El limpiador se integra en el inicio y cierre de URA:

**Inicio:**
```python
# Inicializar Limpiador de Hilos
self.thread_cleaner = ThreadCleaner() if THREAD_CLEANER_AVAILABLE else None
```

**Cierre (closeEvent):**
```python
# Ejecutar limpieza completa de hilos
if self.thread_cleaner:
    try:
        logger.info("Ejecutando limpieza completa de hilos al cerrar...")
        cleanup_results = self.thread_cleaner.full_cleanup()
        logger.info(f"Resultados de limpieza: {cleanup_results}")
    except Exception as e:
        logger.error(f"Error en limpieza de hilos: {e}")

# Detener hilos de mensajería
if self.whatsapp_thread and self.whatsapp_thread.isRunning():
    self.whatsapp_thread.quit()
    self.whatsapp_thread.wait(timeout=5)
# ... (email, telegram, instagram)
```

## Archivos Generados

### config/thread_cleaner.json

Configuración del limpiador:
- Lista blanca de procesos
- Configuración de detección de zombies
- Configuración de limpieza automática

## Dependencias

- psutil: Para gestión de procesos
- json: Para persistencia
- logging: Para logs
- core.network_audit: Para auditoría de red

## Logs

El sistema genera logs detallados:
- Detección de procesos zombies
- Acciones de limpieza
- Errores y excepciones
- Resultados de limpieza completa

## Seguridad

- Modo seguro por defecto (safe_mode)
- Lista blanca de procesos protegidos
- Confirmación antes de eliminar (opcional)
- No elimina procesos en lista blanca
- Timeout de 5 segundos para detener hilos

## Mantenimiento

### Agregar Proceso a Lista Blanca

**Método 1: CLI**
```bash
python3 core/thread_cleaner.py --whitelist-add nombre_proceso
```

**Método 2: Código**
```python
cleaner = ThreadCleaner()
cleaner.add_to_whitelist(name="nombre_proceso")
```

**Método 3: Manual**
Editar `config/thread_cleaner.json`:
```json
{
  "whitelist": {
    "processes": ["nombre_proceso", "otro_proceso"]
  }
}
```

### Ajustar Criterios de Detección

Editar `config/thread_cleaner.json`:
```json
{
  "zombie_detection": {
    "idle_threshold_minutes": 60,  // Cambiar a 60 minutos
    "cpu_threshold": 0.5,         // Cambiar a 0.5%
    "memory_threshold": 1.0       // Cambiar a 1.0%
  }
}
```

### Ver Log de Limpieza

```python
cleaner = ThreadCleaner()
log = cleaner.get_clean_log()
for action in log:
    print(f"{action.timestamp}: {action.action} - {action.name}")
```

## Problemas Comunes

### Proceso protegido no se elimina

**Causa**: El proceso está en la lista blanca.

**Solución**:
1. Verificar si debe ser eliminado
2. Eliminar de lista blanca si es necesario
3. Usar `--force` para ignorar lista blanca

### Hilos no se detienen

**Causa**: Hilos no responden a `quit()`.

**Solución**:
1. Verificar que los hilos implementen `quit()`
2. Aumentar timeout en `wait()`
3. Usar `terminate()` como último recurso

### Limpieza de red no funciona

**Causa**: NetworkAuditSystem no disponible.

**Solución**:
1. Verificar que `core/network_audit.py` existe
2. Verificar dependencias (requests)
3. Revisar logs para errores específicos

## Métricas

El limpiador proporciona métricas detalladas:
- Cantidad de procesos zombies eliminados
- Cantidad de procesos de red limpiados
- Cantidad de hilos de mensajería detenidos
- Cantidad de hilos de aplicación detenidos

## Contacto

Para problemas con el Limpiador de Hilos, contactar al equipo de mantenimiento de URA.

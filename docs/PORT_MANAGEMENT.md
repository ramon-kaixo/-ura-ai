# Sistema de Gestión de Puertos y Conflictos - Documentación

## Resumen

Sistema completo para evitar conflictos de APIs, puertos y direcciones en URA. Incluye gestión centralizada de puertos, locks para archivos compartidos, detección de conflictos en tiempo real y monitorización.

## Componentes

### 1. Port Manager (`core/port_manager.py`)

Gestor centralizado de puertos que:
- Verifica disponibilidad de puertos
- Asigna puertos automáticamente si están ocupados
- Resuelve conflictos según configuración
- Mantiene historial de uso de puertos
- Proporciona estadísticas de uso

**Uso:**
```python
from core.port_manager import get_port_manager

manager = get_port_manager()
port = manager.get_port_for_service("ura_api_auto_repair")
```

### 2. File Lock (`core/file_lock.py`)

Sistema de locks para archivos compartidos JSON que:
- Evita conflictos de escritura concurrente
- Usa locks tipo fcntl para Unix
- Proporciona acceso seguro a archivos JSON
- Instancias predefinidas para archivos comunes

**Uso:**
```python
from core.file_lock import SafeJSONFile, get_safe_repair_history

safe_file = SafeJSONFile("data/repair_history.json")
safe_file.write({"key": "value"})
data = safe_file.read()
```

### 3. Port Conflict Monitor (`core/port_conflict_monitor.py`)

Monitor de conflictos en tiempo real que:
- Detecta conflictos de puertos continuamente
- Alerta sobre nuevos conflictos
- Configurable con intervalo de verificación
- Callback personalizable para alertas

**Uso:**
```python
from core.port_conflict_monitor import get_conflict_monitor

monitor = get_conflict_monitor(check_interval=30)

def alert_callback(conflicts):
    print(f"Conflictos detectados: {conflicts}")

monitor.set_alert_callback(alert_callback)
monitor.start()
```

### 4. Configuración (`config/ports_config.json`)

Configuración centralizada que define:
- Puertos reservados por servicio
- Rango de puertos para asignación automática
- Estrategias de resolución de conflictos
- Comportamiento al inicio

**Estrategias de resolución:**
- `skip`: No hacer nada si el puerto está ocupado
- `kill`: Matar el proceso usando el puerto
- `assign_new`: Asignar un nuevo puerto automáticamente

## Integración con APIs Existentes

### API Auto-Repair (`api/auto_repair_api.py`)

Actualizada para usar port_manager:
```python
from core.port_manager import get_port_manager

port_manager = get_port_manager()
port = port_manager.get_port_for_service("ura_api_auto_repair")
app.run(host='0.0.0.0', port=port)
```

### Dashboard Web (`web/auto_repair_dashboard.py`)

Actualizado para usar port_manager:
```python
from core.port_manager import get_port_manager

port_manager = get_port_manager()
port = port_manager.get_port_for_service("ura_dashboard_web")
app.run(host='0.0.0.0', port=port)
```

## Puertos Reservados

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| ura_api | 5000 | API principal de URA |
| ura_api_v2 | 5001 | API v2 de URA |
| ura_api_auto_repair | 5002 | API de auto-reparación |
| ura_dashboard_web | 5003 | Dashboard web |
| prometheus | 9090 | Prometheus |
| prometheus_metrics | 9091 | Métricas Prometheus |
| grafana | 3000 | Grafana |
| ollama | 11434 | Ollama |
| redis | 6379 | Redis |

## Tests

Ejecutar tests del sistema:
```bash
python tests/test_port_manager.py
```

## Funcionalidades Avanzadas

### 1. Historial de Puertos

El sistema mantiene un historial de uso de puertos en `data/port_history.json`:
- Último uso de cada puerto
- Contador de veces usado
- Reuso automático de puertos históricos

### 2. Detección de Conflictos

Detecta conflictos automáticamente:
- Verifica todos los puertos reservados
- Identifica procesos usando puertos ocupados
- Proporciona detalles del conflicto

### 3. Auto-resolución de Conflictos

Resuelve conflictos según configuración:
- `skip`: Ignora conflicto
- `kill`: Matar proceso
- `assign_new`: Asignar nuevo puerto

### 4. Estadísticas

Proporciona estadísticas completas:
- Total de puertos asignados
- Total de puertos reservados
- Número de conflictos activos
- Detalles de conflictos
- Historial de uso

## Archivos Creados

- `config/ports_config.json` - Configuración de puertos
- `core/port_manager.py` - Gestor de puertos
- `core/file_lock.py` - Sistema de locks para archivos
- `core/port_conflict_monitor.py` - Monitor de conflictos
- `tests/test_port_manager.py` - Tests del sistema
- `data/port_history.json` - Historial de uso (se crea automáticamente)

## Dependencias

- Python 3.8+
- Flask (para APIs)
- fcntl (locks de archivos - Unix only)
- lsof (detección de procesos - Unix only)

## Notas

- Los locks de archivos solo funcionan en sistemas Unix/Linux/macOS
- La detección de procesos usa `lsof` (Unix only)
- Para Windows, se requiere implementación alternativa
- El sistema es thread-safe para escritura concurrente

## Mantenimiento

El sistema es auto-mantenible:
- Historial persistente entre reinicios
- Configuración centralizada
- Detección automática de conflictos
- No requiere intervención manual

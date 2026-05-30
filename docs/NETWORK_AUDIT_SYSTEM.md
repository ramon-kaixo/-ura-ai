# Sistema de Auditoría de Red - URA

## Descripción General

El Sistema de Auditoría de Red es un módulo completo para monitorear, validar y gestionar puertos en el sistema URA. Detecta conflictos de puertos, valida APIs conocidas y proporciona reasignación automática de puertos.

## Fecha de Implementación

28 de abril de 2026

## Componentes

### 1. core/network_audit.py

Módulo principal del sistema de auditoría de red.

#### Clases Principales

**PortInfo**
- Información detallada de cada puerto
- Campos: port, protocol, process_name, pid, ip_address, is_docker, container_name, api_endpoint, health_status, is_authorized, status

**APIHealthCheck**
- Resultado de health check de APIs
- Campos: endpoint, port, status, response_time, content_available, error

**NetworkAuditSystem**
- Clase principal del sistema
- Gestiona escaneo de puertos, validación y reasignación

#### Funcionalidades

##### Escaneo de Puertos
- `_scan_with_lsof()`: Escanea puertos usando lsof
- `_scan_with_netstat()`: Escanea puertos usando netstat (complementario)
- `_scan_docker_containers()`: Escanea contenedores de Docker
- `scan_ports()`: Ejecuta escaneo completo

##### Validación de Puertos
- `_validate_ports()`: Valida puertos contra ALLOWED_PORTS
- `validate_port_identity()`: Valida contenido esperado de APIs
- `_mark_port_as_conflict()`: Marca puertos como CONFLICTO

##### Gestión de Puertos
- `get_available_port()`: Obtiene puerto de reserva disponible
- `reassign_port()`: Reasigna puerto para un servicio
- `move_service_to_reserve()`: Mueve servicio a puerto de reserva

##### Health Check de APIs
- `health_check_apis()`: Verifica APIs conocidas
- Valida contenido no vacío
- Valida identidad de puertos

##### Persistencia
- `_load_inventory()`: Carga inventario desde JSON
- `_save_inventory()`: Guarda inventario en JSON
- Archivo: `config/network_inventory.json`

#### Configuración

**ALLOWED_PORTS** - Lista maestra de puertos permitidos:
```python
ALLOWED_PORTS = {
    11435: {"service": "ollama", "expected_content": "models"},
    11434: {"service": "ollama_docker", "expected_content": "models"},
    3000: {"service": "windsurf", "expected_content": None},
    6379: {"service": "redis", "expected_content": None},
    5432: {"service": "postgres", "expected_content": None},
    80: {"service": "http", "expected_content": None},
    443: {"service": "https", "expected_content": None},
    8000: {"service": "http_alt", "expected_content": None},
    8888: {"service": "jupyter", "expected_content": None},
    9090: {"service": "prometheus", "expected_content": None},
}
```

**RESERVE_PORTS** - Bandeja de puertos de reserva:
```python
RESERVE_PORTS = [11436, 11437, 11438, 11439, 11440]
```

**FIXED_ASSIGNMENTS** - Tabla de asignación fija:
```python
FIXED_ASSIGNMENTS = {
    "ollama": {"port": 11435, "ip": "127.0.0.1", "api_endpoint": "/api/tags"},
    "windsurf": {"port": 3000, "ip": "127.0.0.1", "api_endpoint": "/health"},
    "redis": {"port": 6379, "ip": "127.0.0.1", "api_endpoint": None},
    "postgres": {"port": 5432, "ip": "127.0.0.1", "api_endpoint": None},
}
```

**KNOWN_APIS** - APIs conocidas para health check:
```python
KNOWN_APIS = {
    11435: {"name": "ollama", "endpoint": "/api/tags", "expected_content": "models"},
    11434: {"name": "ollama_docker", "endpoint": "/api/tags", "expected_content": "models"},
    3000: {"name": "windsurf", "endpoint": "/health", "expected_content": None},
}
```

#### Estados de Puertos

- **OCCUPIED**: Puerto en uso y autorizado
- **CONFLICT**: Puerto en uso pero NO autorizado
- **FREE**: Puerto disponible
- **UNKNOWN**: Estado desconocido

#### Detección de Puertos Dinámicos en Docker

El sistema detecta automáticamente contenedores de Docker que usan puertos dinámicos (sin mapeo fijo) y genera alertas CRITICAL.

## Uso

### Ejecutar Auditoría Completa

```python
from core.network_audit import NetworkAuditSystem

audit = NetworkAuditSystem(use_localhost=True)
report = audit.run_full_audit()
```

### Escanear Puertos

```python
audit = NetworkAuditSystem(use_localhost=True)
inventory = audit.scan_ports()
```

### Health Check de APIs

```python
audit = NetworkAuditSystem(use_localhost=True)
health = audit.health_check_apis()
```

### Validar Identidad de Puerto

```python
audit = NetworkAuditSystem(use_localhost=True)
is_valid = audit.validate_port_identity(11435, "models")
```

### Mover Servicio a Reserva

```python
audit = NetworkAuditSystem(use_localhost=True)
new_port = audit.move_service_to_reserve("ollama", 11435)
```

## Archivos Generados

### config/network_inventory.json

Inventario completo de puertos en uso:
- inventory: Dict con información de cada puerto
- api_health: Dict con resultados de health check
- audit_log: Historial de auditorías
- last_updated: Timestamp de última actualización

## Integración con URA

### main_final.py

El sistema se integra en el inicio de URA:

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

## Dependencias

- requests: Para health check de APIs
- subprocess: Para ejecutar lsof, netstat, docker
- json: Para persistencia
- logging: Para logs
- dataclasses: Para estructuras de datos

## Logs

El sistema genera logs detallados:
- Escaneo de puertos
- Detección de puertos no autorizados
- Health check de APIs
- Reasignación de puertos
- Errores y excepciones

## Seguridad

- Usa localhost (127.0.0.1) por defecto
- Configurable para usar IP local
- Valida identidad de puertos
- Marca puertos no autorizados como CONFLICTO
- No cierra procesos sin confirmación

## Mantenimiento

### Agregar Puerto Permitido

Editar `core/network_audit.py` y agregar a `ALLOWED_PORTS`:
```python
ALLOWED_PORTS = {
    # ... puertos existentes
    8080: {"service": "mi_servicio", "expected_content": None},
}
```

O usar la interfaz gráfica:
```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 scripts/port_config_panel.py
```

### Ver Inventario

```bash
cat ~/Desktop/URA_App/config/network_inventory.json
```

### Ejecutar Auditoría Manual

```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 core/network_audit.py
```

## Problemas Comunes

### Puerto no autorizado detectado

**Causa**: Un puerto está en uso pero no está en ALLOWED_PORTS.

**Solución**: 
1. Verificar si el puerto es legítimo
2. Agregar a ALLOWED_PORTS si es necesario
3. O detener el proceso si no es necesario

### Health check falla

**Causa**: API no responde o contenido incorrecto.

**Solución**:
1. Verificar que el servicio esté corriendo
2. Verificar el endpoint correcto
3. Verificar contenido esperado

### No hay puertos de reserva disponibles

**Causa**: Todos los puertos de reserva están ocupados.

**Solución**:
1. Agregar más puertos a RESERVE_PORTS
2. Liberar puertos no utilizados
3. Ajustar configuración de servicios

## Contacto

Para problemas con el Sistema de Auditoría de Red, contactar al equipo de mantenimiento de URA.

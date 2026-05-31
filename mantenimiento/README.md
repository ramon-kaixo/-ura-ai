# URA Maintenance System

Sistema de mantenimiento automatizado para el enjambre URA.

## Descripción

El sistema URA Maintenance realiza limpieza automática y segura de todos los nodos del enjambre, liberando espacio en disco y manteniendo los sistemas optimizados.

## Características

- **Multiplataforma**: Soporta Linux y macOS
- **Seguro**: Exclusiones automáticas de directorios críticos
- **Automatizado**: Ejecución periódica vía systemd
- **Distribuido**: Puede ejecutarse en todos los nodos del enjambre
- **Auditado**: Logs detallados de todas las operaciones
- **Configurable**: Umbrales y retención personalizables

## Componentes

### 1. ura_maintenance.py
Script principal de mantenimiento que ejecuta:

**En Linux:**
- Limpieza de Docker (imágenes, contenedores, volúmenes)
- Limpieza de cache de apt
- Limpieza de cache de pip
- Limpieza de logs antiguos (>7 días)
- Limpieza de archivos temporales

**En macOS:**
- Limpieza de Docker
- Limpieza de cache de Homebrew
- Limpieza de cache de pip
- Limpieza de caches de aplicaciones
- Limpieza de logs de aplicaciones

### 2. ura_maintenance_remote.py
Script para ejecutar mantenimiento en nodos remotos del enjambre.

### 3. ura-maintenance.service
Servicio systemd para ejecución del mantenimiento.

### 4. ura-maintenance.timer
Timer systemd para ejecución semanal automática.

## Instalación

### En Linux (GX10)

```bash
# Copiar scripts
cp ura_maintenance.py /home/ramon/URA/mantenimiento/
chmod +x /home/ramon/URA/mantenimiento/ura_maintenance.py

# Instalar servicio
sudo cp ura-maintenance.service /etc/systemd/system/
sudo cp ura-maintenance.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ura-maintenance.timer
sudo systemctl start ura-maintenance.timer
```

### En macOS

```bash
# Copiar script
cp ura_maintenance.py ~/URA/mantenimiento/
chmod +x ~/URA/mantenimiento/ura_maintenance.py

# Configurar launchd (pendiente)
```

## Uso

### Ejecución manual

```bash
# Local
python3 /home/ramon/URA/mantenimiento/ura_maintenance.py

# Remoto en todos los nodos
python3 /home/ramon/URA/mantenimiento/ura_maintenance_remote.py
```

### Ejecución automática

El timer systemd ejecuta el mantenimiento semanalmente automáticamente.

## Configuración

El sistema usa un archivo de configuración JSON externo para flexibilidad y seguridad.

### Archivo de configuración

Ubicación: `/home/ramon/URA/mantenimiento/config.json`

```json
{
  "log_dir": "/opt/ura/logs/maintenance",
  "exclude_patterns": [
    "*.db",
    "*.sqlite",
    "*.sqlite-wal",
    "*.key",
    "*.pem",
    "*.crt",
    "*.env",
    "*.secret",
    "/home/*/URA/",
    "/home/*/projects/",
    "/home/*/Documents/",
    "/home/*/Desktop/",
    "/home/*/Downloads/",
    "/opt/ura/",
    "/etc/",
    "/var/lib/"
  ],
  "thresholds": {
    "docker_images": 10,
    "docker_volumes": 5,
    "cache_size": 2,
    "log_size": 1
  },
  "retention_days": {
    "logs": 7,
    "cache": 30,
    "docker_build": 7
  },
  "allowed_temp_dirs": [
    "/tmp",
    "/var/tmp"
  ],
  "allowed_log_dirs": [
    "/var/log",
    "/opt/ura/logs"
  ]
}
```

### Variables de entorno

También puedes especificar la ruta del archivo de configuración mediante variable de entorno:

```bash
export URA_MAINTENANCE_CONFIG=/ruta/a/config.json
python3 ura_maintenance.py
```

### Umbrales de limpieza

Edita `thresholds` en el archivo de configuración:

```json
"thresholds": {
    "docker_images": 10,  // Limpiar si > 10GB
    "docker_volumes": 5,  // Limpiar si > 5GB
    "cache_size": 2,      // Limpiar si > 2GB
    "log_size": 1          // Limpiar si > 1GB
}
```

### Retención de días

Edita `retention_days` en el archivo de configuración:

```json
"retention_days": {
    "logs": 7,            // Mantener logs 7 días
    "cache": 30,          // Mantener cache 30 días
    "docker_build": 7     // Mantener build cache 7 días
}
```

### Exclusiones

Los siguientes directorios NUNCA se borran:

- `/home/*/URA/` - Directorio URA
- `/home/*/projects/` - Proyectos
- `/home/*/Documents/` - Documentos
- `/home/*/Desktop/` - Escritorio
- `/home/*/Downloads/` - Descargas
- `/opt/ura/` - Directorio URA del sistema
- `/etc/` - Configuración del sistema
- `/var/lib/` - Datos del sistema
- Archivos de bases de datos (*.db, *.sqlite)
- Certificados y claves (*.key, *.pem, *.crt)
- Archivos de configuración sensible (*.env, *.secret)

## Logs

Los logs se guardan en `/opt/ura/logs/maintenance/`:

- `maintenance_YYYYMMDD_HHMMSS.log` - Log de ejecución
- `maintenance_results_YYYYMMDD_HHMMSS.json` - Resultados en JSON
- `remote_maintenance_YYYYMMDD_HHMMSS.log` - Log de ejecución remota
- `remote_maintenance_results_YYYYMMDD_HHMMSS.json` - Resultados remotos

## Resultados de prueba

**Prueba en GX10:**
- Espacio inicial: 792.77GB / 1832.21GB (43.3%)
- Espacio final: 786.34GB / 1832.21GB (42.9%)
- **Espacio liberado: 5.02GB**

**Operaciones realizadas:**
- Docker prune: 3.05GB
- apt cache: 0.13GB
- pip cache: 0.50GB
- temp files: 1.33GB

## Integración con enjambre

El sistema se integra con el enjambre URA mediante:

1. Lectura de `known_devices.json` para obtener nodos activos
2. Ejecución remota vía SSH
3. Agregación de resultados de todos los nodos

## Seguridad

El sistema implementa múltiples capas de seguridad:

### Validaciones de seguridad

- **Verificación de symlinks**: Detecta y rechaza symlinks para evitar ataques
- **Verificación de ownership**: Solo borra archivos del usuario actual (o root)
- **Validación de rutas**: Previene directory traversal usando rutas reales
- **Patrones de exclusión**: Implementación real de exclusiones configurables
- **Timeouts**: Límites de tiempo para todas las operaciones externas
- **Sin shell=True**: Usa subprocess sin shell para evitar inyección de comandos

### Exclusiones implementadas

Los siguientes directorios y patrones NUNCA se borran:

- `/home/*/URA/` - Directorio URA
- `/home/*/projects/` - Proyectos
- `/home/*/Documents/` - Documentos
- `/home/*/Desktop/` - Escritorio
- `/home/*/Downloads/` - Descargas
- `/opt/ura/` - Directorio URA del sistema
- `/etc/` - Configuración del sistema
- `/var/lib/` - Datos del sistema
- Archivos de bases de datos (*.db, *.sqlite, *.sqlite-wal)
- Certificados y claves (*.key, *.pem, *.crt)
- Archivos de configuración sensible (*.env, *.secret)

### Auditoría

- Todas las operaciones se loguean en `/opt/ura/logs/maintenance/`
- Resultados guardados en JSON con timestamp
- Logs incluyen razón de rechazo de archivos
- Rollback manual posible desde logs

## Próximas mejoras

- [ ] Integración con launchd para macOS
- [ ] Dashboard web para monitoreo
- [ ] Alertas cuando espacio < 10%
- [ ] Limpieza selectiva por tipo de archivo
- [ ] Integración con sistema de cuarentena URA

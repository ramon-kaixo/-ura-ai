# Guía para Equipo de Mantenimiento - URA

## Información Importante

**Fecha de Implementación:** 28 de abril de 2026
**Versión:** URA v3.0
**Prioridad:** CRÍTICA

## Resumen Ejecutivo

Se han implementado dos sistemas críticos para el mantenimiento y estabilidad de URA:

1. **Sistema de Auditoría de Red** - Monitorea puertos, detecta conflictos y valida APIs
2. **Limpiador de Hilos Completo** - Detecta y limpia procesos zombies, hilos colgados y procesos de red no autorizados

Ambos sistemas están completamente integrados en URA y se ejecutan automáticamente.

## Cambios Realizados

### 1. Sistema de Auditoría de Red

**Archivo:** `core/network_audit.py` (NUEVO)

**Funcionalidades:**
- Escaneo de puertos (nativos y Docker) usando lsof y netstat
- Health check de APIs conocidas (Ollama, Windsurf)
- Validación de identidad de puertos (verifica contenido esperado)
- Detección de puertos dinámicos en Docker (PROHIBIDOS)
- Reasignación automática de puertos a bandeja de reserva
- Persistencia en JSON (`config/network_inventory.json`)

**Configuración:**
- ALLOWED_PORTS: Lista maestra de puertos permitidos
- RESERVE_PORTS: 5 puertos de reserva (11436-11440)
- FIXED_ASSIGNMENTS: Tabla de asignación fija de servicios
- KNOWN_APIS: APIs conocidas para health check

**Integración:**
- Se ejecuta automáticamente al iniciar URA
- Disponible para auditorías manuales durante ejecución
- Genera logs detallados

### 2. Limpiador de Hilos

**Archivo:** `core/thread_cleaner.py` (ACTUALIZADO)

**Funcionalidades:**
- Detección de procesos zombies (estado, inactividad, bajo uso CPU/RAM)
- Limpieza de procesos zombies
- Limpieza de procesos de red no autorizados (integra con NetworkAuditSystem)
- Gestión de hilos de mensajería (WhatsApp, Email, Telegram, Instagram)
- Gestión de hilos de aplicación
- Limpieza post-acción (QuickBooks, Email, Banco)
- Limpieza completa al cerrar URA

**Configuración:**
- Lista blanca de procesos protegidos
- Criterios de detección de zombies (30 min inactividad, <0.1% CPU, <0.5% RAM)
- Modo seguro por defecto
- Configuración en `config/thread_cleaner.json`

**Integración:**
- Se inicializa al iniciar URA
- Ejecuta limpieza completa en closeEvent
- Registra hilos de mensajería y aplicación

### 3. Interfaz de Configuración de Puertos

**Archivo:** `scripts/port_config_panel.py` (NUEVO)

**Funcionalidades:**
- Interfaz gráfica para agregar/eliminar puertos permitidos
- Escaneo de puertos en tiempo real
- Ejecución de auditoría completa desde la UI
- Visualización de puertos de reserva
- Guarda configuración en `core/network_audit.py`

**Uso:**
```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 scripts/port_config_panel.py
```

### 4. Integraciones en main_final.py

**Cambios:**
- Importación de NetworkAuditSystem y ThreadCleaner
- Inicialización de NetworkAuditSystem en __init__
- Ejecución de auditoría al inicio
- Inicialización de ThreadCleaner en __init__
- Limpieza completa en closeEvent
- Detención de hilos de mensajería en closeEvent

**Ubicaciones:**
- Importaciones: Líneas 35-49
- Inicialización NetworkAuditSystem: Líneas 1618-1626
- Inicialización ThreadCleaner: Líneas 1628-1629
- closeEvent: Líneas 4885-4924

### 5. Actualización de Puerto de Ollama

**Cambios:**
- Puerto de Ollama cambiado de 11434 a 11435
- Actualizado en `core/ollama_connector.py` (línea 123)
- Actualizado en `main_final.py` (línea 1746)

**Motivo:** Evitar conflicto con contenedor de Docker `ura-ollama` que usaba el puerto 11434.

## Archivos Modificados/Creados

### Archivos Nuevos

1. `core/network_audit.py` - Sistema de Auditoría de Red
2. `scripts/port_config_panel.py` - Interfaz de configuración de puertos
3. `docs/NETWORK_AUDIT_SYSTEM.md` - Documentación del sistema de auditoría
4. `docs/THREAD_CLEANER.md` - Documentación del limpiador de hilos
5. `docs/URA_INTEGRATIONS.md` - Documentación de integraciones
6. `docs/MAINTENANCE_GUIDE.md` - Esta guía

### Archivos Modificados

1. `core/thread_cleaner.py` - Actualizado con limpieza completa
2. `main_final.py` - Integrado auditoría y limpiador
3. `core/ollama_connector.py` - Puerto actualizado a 11435

### Archivos Generados

1. `config/network_inventory.json` - Inventario de puertos (generado automáticamente)
2. `config/thread_cleaner.json` - Configuración del limpiador (generado automáticamente)

## Comandos de Mantenimiento

### Verificar Sistema de Auditoría de Red

```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 core/network_audit.py
```

### Verificar Limpiador de Hilos

```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 core/thread_cleaner.py --list
```

### Limpiar Procesos Zombies Manualmente

```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 core/thread_cleaner.py --clean
```

### Abrir Panel de Configuración de Puertos

```bash
cd ~/Desktop/URA_App
source .venv/bin/activate
python3 scripts/port_config_panel.py
```

### Ver Inventario de Puertos

```bash
cat ~/Desktop/URA_App/config/network_inventory.json
```

### Ver Configuración del Limpiador

```bash
cat ~/Desktop/URA_App/config/thread_cleaner.json
```

### Ver Logs de URA

```bash
tail -f ~/Desktop/URA_App/logs/ura_app.log
```

## Problemas Comunes y Soluciones

### 1. Puerto no autorizado detectado

**Síntoma:** Log muestra "Puerto X NO autorizado"

**Causa:** Un puerto está en uso pero no está en ALLOWED_PORTS

**Solución:**
1. Verificar si el puerto es legítimo
2. Agregar a ALLOWED_PORTS usando el panel de configuración
3. O detener el proceso si no es necesario

### 2. Auditoría falla al inicio

**Síntoma:** Log muestra "Error ejecutando auditoría de red"

**Causa:** Permisos insuficientes para lsof/netstat/docker

**Solución:**
1. Verificar permisos para ejecutar lsof, netstat, docker
2. Verificar que Docker está corriendo (si se usa)
3. Revisar logs para error específico

### 3. Proceso protegido no se elimina

**Síntoma:** Proceso sigue corriendo después de limpieza

**Causa:** El proceso está en la lista blanca

**Solución:**
1. Verificar si debe ser eliminado
2. Eliminar de lista blanca si es necesario
3. Usar `--force` para ignorar lista blanca

### 4. No hay puertos de reserva disponibles

**Síntoma:** Log muestra "No hay puertos de reserva disponibles"

**Causa:** Todos los puertos de reserva están ocupados

**Solución:**
1. Agregar más puertos a RESERVE_PORTS
2. Liberar puertos no utilizados
3. Ajustar configuración de servicios

### 5. Hilos no se detienen al cerrar

**Síntoma:** URA no cierra completamente

**Causa:** Hilos no responden a quit()

**Solución:**
1. Verificar que los hilos implementen quit()
2. Aumentar timeout en wait()
3. Usar terminate() como último recurso

## Checklist de Mantenimiento

### Diario

- [ ] Verificar logs de URA para errores
- [ ] Verificar que Ollama está corriendo en puerto 11435
- [ ] Verificar que no hay puertos no autorizados

### Semanal

- [ ] Ejecutar auditoría de red manualmente
- [ ] Verificar inventario de puertos
- [ ] Limpiar procesos zombies si es necesario
- [ ] Revisar logs de thread_cleaner

### Mensual

- [ ] Revisar y actualizar ALLOWED_PORTS si es necesario
- [ ] Revisar y actualizar lista blanca de procesos
- [ ] Verificar configuración de detección de zombies
- [ ] Revisar documentación y actualizar si hay cambios

## Contacto de Emergencia

Para problemas críticos que no puedan resolverse con esta guía:

1. Revisar documentación detallada:
   - `docs/NETWORK_AUDIT_SYSTEM.md`
   - `docs/THREAD_CLEANER.md`
   - `docs/URA_INTEGRATIONS.md`

2. Verificar logs:
   - `logs/ura_app.log`
   - Logs de NetworkAuditSystem
   - Logs de ThreadCleaner

3. Contactar al equipo de desarrollo de URA

## Notas Importantes

- **Ollama ahora usa el puerto 11435** (no 11434)
- **El contenedor de Docker ura-ollama está configurado para no iniciarse automáticamente**
- **La auditoría de red se ejecuta automáticamente al iniciar URA**
- **La limpieza de hilos se ejecuta automáticamente al cerrar URA**
- **Todos los cambios están documentados en los archivos de documentación**
- **La configuración se guarda en archivos JSON para persistencia**

## Resumen de Cambios para Despliegue

1. Copiar archivos nuevos al servidor de producción
2. Actualizar archivos modificados
3. Verificar que dependencias (psutil, requests) están instaladas
4. Ejecutar prueba de auditoría de red
5. Ejecutar prueba de limpieza de hilos
6. Verificar que URA inicia correctamente
7. Verificar que URA cierra correctamente
8. Monitorear logs durante 24 horas

## Firma

Implementado por: Cascade (AI Assistant)
Fecha: 28 de abril de 2026
Revisado por: Equipo de Mantenimiento URA

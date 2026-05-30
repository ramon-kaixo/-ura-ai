# Sistema de Auto-Reparación de Errores

## Descripción

El sistema de auto-reparación de errores detecta automáticamente errores en la aplicación URA y ofrece soluciones automáticas o manuales para repararlos.

## Características

### 1. Detección Automática de Errores

El sistema detecta los siguientes tipos de errores:

- **missing_module**: Módulo Python faltante
- **ollama**: Servicio Ollama caído
- **redis**: Servicio Redis caído
- **missing_file**: Archivo o directorio faltante
- **import_error**: Error de importación
- **permission**: Error de permisos
- **key_error**: KeyError en diccionarios
- **attribute_error**: AttributeError en objetos
- **type_error**: TypeError en tipos de datos
- **connection**: Error de conexión o timeout

### 2. Reparación Automática

El sistema intenta reparar automáticamente los siguientes errores:

- **Módulos faltantes**: Instala con pip3 automáticamente
- **Ollama caído**: Reinicia el servicio automáticamente
- **Redis caído**: Reinicia el servicio automáticamente
- **Archivos faltantes**: Crea archivos/directorios automáticamente

### 3. Reparación Manual

Para errores que no pueden repararse automáticamente, el sistema ofrece un botón "🔧 Auto-Reparar" en la ventana de error que:

- Detecta el tipo de error
- Ejecuta la reparación apropiada
- Muestra el resultado (éxito/fallo)
- Reintenta la acción original tras reparación exitosa

### 4. Logging y Historial

- **Logging**: Cada reparación se registra en logs (logger.info/warning)
- **Historial**: Guarda hasta 100 reparaciones recientes en `data/repair_history.json`
- **Detección de recurrentes**: Identifica errores que fallan repetidamente

### 5. Configuración Persistente

La configuración se guarda en `config/auto_repair_config.json`:

```json
{
  "auto_repair_enabled": true,
  "auto_repair_types": ["missing_module", "ollama", "redis", "missing_file", "import_error"],
  "max_repair_attempts": 3,
  "log_repairs": true,
  "alert_on_failure": false
}
```

- `auto_repair_enabled`: Habilitar/deshabilitar auto-reparación
- `auto_repair_types`: Tipos de errores a reparar automáticamente
- `max_repair_attempts`: Máximo de intentos de reparación
- `log_repairs`: Habilitar/deshabilitar logging
- `alert_on_failure`: Alertar en caso de fallo

## Uso

### Integración en Código

```python
from core.error_auto_repair import show_error_with_repair, ErrorAutoRepair

# Mostrar ventana de error con auto-reparación
show_error_with_repair(
    parent=self,
    title="Error en Panel",
    message="ModuleNotFoundError: No module named 'requests'",
    repair_callback=lambda success, msg: self.retry_action() if success else None,
    auto_repair=True
)

# Usar sistema de auto-reparación directamente
repair_system = ErrorAutoRepair()
success, message = repair_system.attempt_repair("missing_module", error_message)

# Ver historial de reparaciones
history = repair_system.get_repair_history()

# Ver errores recurrentes
recurrent = repair_system.get_recurrent_errors()
```

### Configuración

El usuario puede configurar la auto-reparación mediante:

1. **Checkbox en ventana de error**: "Reparar automáticamente en el futuro"
2. **Archivo de configuración**: `config/auto_repair_config.json`
3. **Programáticamente**: `repair_system.config["auto_repair_enabled"] = True`

## Archivos

- `core/error_auto_repair.py`: Sistema de auto-reparación
- `data/repair_history.json`: Historial de reparaciones
- `config/auto_repair_config.json`: Configuración de auto-reparación

## Comparación con Sistema Viejo

| Aspecto | Viejo (SelfHealingSystem) | Nuevo (error_auto_repair) |
|---------|---------------------------|---------------------------|
| Threading | Threads en segundo plano | Sin threads |
| Autonomía | 100% autónomo | Requiere interacción (o automático configurable) |
| Qt compatibility | ❌ Conflictos | ✅ Compatible |
| Integración | Ollama, Telegram | Solo ventanas de error |
| Reparaciones | General | Específicas por tipo |
| Estado | Desactivado | Activo |
| Logging | Básico | Completo con historial |
| Configuración | Hardcodeada | Persistente JSON |

## Flujo de Reparación

1. **Error aparece** → Sistema detecta tipo de error
2. **Auto-reparación habilitada** → Intenta reparar automáticamente
3. **Éxito** → Reintenta acción (sin mostrar ventana)
4. **Fallo** → Muestra ventana con botón "Auto-Reparar" manual
5. **Usuario click** → Ejecuta reparación manual
6. **Resultado** → Muestra éxito/fallo
7. **Reintento automático** → Si éxito, reintenta acción tras 1 segundo
8. **Logging** → Registra en historial y logs

## Ventajas

- ✅ Compatible con Qt threading
- ✅ Configuración persistente
- ✅ Historial completo de reparaciones
- ✅ Detección de errores recurrentes
- ✅ Reparación automática configurable
- ✅ Reintento automático tras éxito
- ✅ Logging estructurado

## Limitaciones

- ❌ No repara errores de lógica de código
- ❌ Requiere conexión a internet para instalar módulos
- ❌ Algunos errores requieren intervención manual (permisos, configuración)

## Futuras Mejoras

- [ ] Panel de visualización de historial de reparaciones
- [ ] Exportación de reportes de reparaciones (PDF/CSV)
- [ ] Alertas de errores recurrentes a Telegram/Discord
- [ ] Integración con sistema de aprendizaje para predecir errores
- [ ] Comparación de rendimiento antes/después de reparaciones

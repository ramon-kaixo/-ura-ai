# Protocolo de Comunicación OpenCode

## Introducción al Protocolo

### Objetivo
Establecer comunicación estándar entre componentes del sistema OpenCode para garantizar la coordinación eficiente y el intercambio de información estructurada.

### Alcance  
Todos los componentes del sistema OpenCode (OpenCode 1, 2 y 3).

### Versiones
Protocolo v1.0

## Estructura de Mensajes

```json
{
  "message_id": "msg_001_20260830",
  "source_component": "OpenCode_1",
  "destination_component": "OpenCode_2",  
  "message_type": "status_update",
  "timestamp": "2026-08-30T16:39:00Z",
  "content": {
    "status": "operational",
    "metrics": {
      "tests_passed": 10728,
      "tests_failed": 0,
      "tests_error": 0
    }
  }
}
```

## Tipos de Mensajes

| Tipo Mensaje         | Descripción                       |
|----------------------|-----------------------------------|
| status_update        | Actualización de estado           |
| alert_critical       | Alerta crítica                    |
| task_assignment      | Asignación de tarea               |
| confirmation         | Confirmación de tarea             |
| error_report         | Reporte de error                  |

## Componentes del Sistema

### OpenCode 1 - Supervisión
Componente encargado de monitorear el estado y desempeño del sistema.

### OpenCode 2 - Implementación  
Componente responsable de ejecutar tareas y operaciones según asignación recibida.

### OpenCode 3 - Documentación 
Componente dedicado a la creación, mantenimiento y actualización de documentación técnica.
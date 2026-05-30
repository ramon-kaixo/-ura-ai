# Ciclo Evolutivo de URA

Este documento describe el sistema completo de evolución de URA, incluyendo la arquitectura híbrida, el ciclo de sandboxes, el sistema de versiones y el rollback automático.

## 1. Arquitectura Híbrida

### Configuración de Hardware

**Mac Mini (Orquestador)**
- RAM: 16GB
- Función: Orquestador principal
- Responsabilidades:
  - Coordinación de sandboxes
  - Gestión de procesos PM2
  - Comunicación con GX10
  - Monitoreo de salud del sistema
  - Gestión de versiones y rollbacks

**GX10 (Cerebro de IA)**
- RAM: 128GB
- Función: Cerebro de IA
- Responsabilidades:
  - Ejecución de modelos Ollama (qwen3:32b-q8_0)
  - Procesamiento de embeddings
  - Inferencia de lenguaje
  - Almacenamiento de memoria a largo plazo
  - Ejecución de sandboxes Docker

### Comunicación

**Red Local 10GbE**
- Conexión directa Mac ↔ GX10
- Latencia: <2ms
- Ancho de banda: 10Gbps
- Protocolo: TCP/IP sobre Ethernet

**Tailscale (Backup)**
- IP Mac: 100.123.81.101
- IP GX10: 100.127.206.86
- Exit Node: ura-shield (100.90.84.4)
- Uso: Conectividad remota y failover

## 2. Ciclo de 4 Sandboxes

### Definición de Sandboxes

**Sandbox 1 - Mantenimiento**
- Función: Limpieza y optimización
- Herramientas:
  - Limpieza de cachés
  - Optimización de base de datos
  - Rotación de logs
  - Compresión de datos
  - Limpieza de archivos temporales
- Ubicación: Mac (local)
- Ejecución: 06:00 y 18:00

**Sandbox 2 - Seguridad**
- Función: Validación y auditoría
- Herramientas:
  - Escaneo de vulnerabilidades (bandit)
  - Auditoría de dependencias (pip-audit, safety)
  - Verificación de permisos
  - Validación de firmas
  - Análisis de logs de seguridad
- Ubicación: GX10 (Docker)
- Ejecución: 06:00 y 00:00

**Sandbox 3 - Aprendizaje**
- Función: Memoria y embeddings
- Herramientas:
  - Generación de embeddings
  - Indexación de memoria
  - Procesamiento de documentos
  - Actualización de vectores
  - Entrenamiento de modelos ligeros
- Ubicación: GX10 (Docker)
- Ejecución: 12:00 y 18:00

**Sandbox 4 - Documentación**
- Función: Manuales e informes
- Herramientas:
  - Generación de manuales
  - Creación de informes de estado
  - Documentación de cambios
  - Actualización de README
  - Generación de métricas
- Ubicación: Mac (local)
- Ejecución: 12:00 y 00:00

### Rotación Cada 6 Horas

| Hora | Sandbox Activo | Sandbox Activo | Propósito |
|------|----------------|----------------|-----------|
| 06:00 | Sandbox 1 (Mantenimiento) | Sandbox 2 (Seguridad) | Limpieza + Validación matutina |
| 12:00 | Sandbox 3 (Aprendizaje) | Sandbox 4 (Documentación) | Procesamiento + Informes del mediodía |
| 18:00 | Sandbox 1 (Mantenimiento) | Sandbox 3 (Aprendizaje) | Limpieza + Procesamiento vespertino |
| 00:00 | Sandbox 2 (Seguridad) | Sandbox 4 (Documentación) | Validación + Informes nocturnos |

### Coordinación de Ejecución

```python
# Pseudocódigo de coordinación
def ejecutar_rotacion():
    hora = datetime.now().hour
    
    if 6 <= hora < 12:
        ejecutar_sandbox("mantenimiento")
        ejecutar_sandbox("seguridad")
    elif 12 <= hora < 18:
        ejecutar_sandbox("aprendizaje")
        ejecutar_sandbox("documentacion")
    elif 18 <= hora < 24:
        ejecutar_sandbox("mantenimiento")
        ejecutar_sandbox("aprendizaje")
    else:  # 00:00 - 06:00
        ejecutar_sandbox("seguridad")
        ejecutar_sandbox("documentacion")
```

## 3. Comunicación Entre Sandboxes

### Reglas de Comunicación

**Mantenimiento ↔ Documentación (Obligatoria)**
- Todo cambio en Mantenimiento debe documentarse
- Documentación recibe logs de Mantenimiento
- Mantenimiento verifica que Documentación esté actualizada

**Flujo de Datos**
```
Mantenimiento → Cola de Mensajes → Documentación
     ↓                                  ↓
  Logs de cambios                 Generación de informes
     ↓                                  ↓
  Validación de estado            Actualización de README
```

**Registro Automático**
- Todo cambio queda registrado automáticamente
- Timestamp exacto de cada modificación
- Autor del cambio (sandbox o usuario)
- Hash de versión del código afectado
- Impacto estimado del cambio

### Formato de Mensajes

```json
{
  "timestamp": "2026-05-11T18:30:00Z",
  "from_sandbox": "mantenimiento",
  "to_sandbox": "documentacion",
  "type": "change_log",
  "data": {
    "module": "core/sandbox.py",
    "change": "Optimización de limpieza de caché",
    "impact": "medium",
    "version_hash": "abc123"
  }
}
```

## 4. Sistema de 10 Versiones Aprobadas

### Estructura de Directorios

```
URA_App/
├── versions/
│   ├── candidates/
│   │   ├── v10.1_candidate_2026-05-11/
│   │   ├── v10.2_candidate_2026-05-12/
│   │   └── ...
│   └── approved/
│       ├── v9.1_approved_2026-04-01/
│       ├── v9.2_approved_2026-04-15/
│       ├── v9.3_approved_2026-05-01/
│       └── ... (máximo 10)
├── current/ → symlink a última versión aprobada
└── rollback/ → symlink a versión anterior
```

### Ciclo de Vida de Versiones

**Fase 1: Candidata (candidates/)**
- Duración: 30 días de cuarentena
- Monitoreo continuo por sandboxes
- Logs de estabilidad y errores
- Si pasa sin problemas → Promoción a aprobada
- Si falla → Eliminación y rollback

**Fase 2: Aprobada (approved/)**
- Máximo: 10 versiones
- Si hay 10 → Se borra la más antigua
- Espacio reservado: ~30GB total
- Uso: Producción estable

**Fase 3: Activa (current/)**
- Symlink a última versión aprobada
- Uso en tiempo real
- Monitoreo de salud continua

### Promoción de Candidata a Aprobada

**Criterios de Aprobación**
- 30 días sin errores críticos
- Todos los sandboxes pasan pruebas
- No hay regresiones en funcionalidad
- Rendimiento dentro de parámetros normales
- Seguridad validada

**Proceso de Promoción**
```python
def promover_candidata(version_id):
    # 1. Verificar 30 días de estabilidad
    if not verificar_estabilidad(version_id, dias=30):
        return False
    
    # 2. Ejecutar todos los sandboxes
    if not ejecutar_todos_sandboxes(version_id):
        return False
    
    # 3. Verificar no hay regresiones
    if not verificar_sin_regresiones(version_id):
        return False
    
    # 4. Mover de candidates/ a approved/
    mover_version(version_id, "candidates", "approved")
    
    # 5. Si hay más de 10, borrar la más antigua
    if contar_aprobadas() > 10:
        borrar_version_antigua()
    
    # 6. Actualizar symlink current/
    actualizar_symlink_current(version_id)
    
    return True
```

## 5. Rollback Automático

### Condiciones de Rollback

**Trigger Automático**
- Versión activa falla 3 veces consecutivas
- Error crítico en sandbox de seguridad
- Latencia > 10 segundos durante 5 minutos
- Uso de CPU > 95% durante 10 minutos
- Error en Ollama API (GX10 no responde)

**Trigger Manual**
- Comando de usuario: `ura rollback`
- Panel de control URA
- Alerta de monitoreo

### Proceso de Rollback

```python
def ejecutar_rollback():
    # 1. Identificar versión anterior aprobada
    version_anterior = obtener_ultima_aprobada()
    
    # 2. Detener servicios actuales
    detener_servicios()
    
    # 3. Cambiar symlink current/ a versión anterior
    actualizar_symlink_rollback(version_anterior)
    
    # 4. Reiniciar servicios
    reiniciar_servicios()
    
    # 5. Verificar funcionamiento
    if not verificar_salud():
        # Rollback falló, intentar versión más antigua
        return rollback_emergency()
    
    # 6. Registrar evento
    registrar_rollback(version_anterior)
    
    # 7. Notificar al usuario
    notificar_usuario("Rollback completado a " + version_anterior)
    
    return True
```

### Rollback de Emergencia

Si el rollback normal falla, se usa la versión de emergencia:
- Ubicación: `URA_App/versions/emergency/`
- Contenido: Última versión conocida estable
- Activación: Manual o automática si 3 rollbacks fallan

## 6. Integración con Sistema Actual

### Estado Actual vs Diseño Futuro

**Implementación Actual (sandbox_orchestrator.py)**
- 5 sandboxes: farina, entrada, mantenimiento_1, mantenimiento_2, mantenimiento_3
- Ciclos normales (6h) y acelerados (1h)
- Sin rotación por pares específicos
- Sin sistema de versiones aprobadas/candidates

**Diseño Futuro (este documento)**
- 4 sandboxes: Mantenimiento, Seguridad, Aprendizaje, Documentación
- Rotación específica cada 6 horas
- Sistema de 10 versiones aprobadas
- Rollback automático

### Migración Planificada

**Fase 1: Preparación**
- Crear estructura de directorios versions/
- Implementar sistema de versionamiento
- Crear scripts de rollback

**Fase 2: Implementación**
- Refactorizar sandbox_orchestrator.py para 4 sandboxes
- Implementar rotación por pares según horario
- Integrar comunicación entre sandboxes

**Fase 3: Validación**
- Ejecutar ciclo completo en modo prueba
- Verificar rollback automático
- Validar promoción de versiones

**Fase 4: Despliegue**
- Activar en producción
- Monitorear durante 30 días
- Ajustar parámetros según necesidad

## 7. Monitoreo y Métricas

### Métricas Clave

**Sandboxes**
- Tiempo de ejecución por sandbox
- Tasa de éxito/fallo
- Uso de recursos (CPU, RAM, Disco)
- Latencia de comunicación

**Versiones**
- Tiempo en cuarentena
- Tasa de promoción (candidatas → aprobadas)
- Frecuencia de rollback
- Espacio utilizado por versiones

**Sistema**
- Latencia Mac ↔ GX10
- Uso de Ollama API
- Estabilidad de procesos PM2
- Salud de Tailscale

### Alertas

**Críticas**
- Rollback automático ejecutado
- Versión activa fallando
- Sandbox de seguridad detectó vulnerabilidad
- GX10 no responde

**Advertencias**
- Candidata cerca de 30 días sin aprobar
- Espacio de versiones > 25GB
- Sandbox tardando más de lo normal
- Latencia Mac ↔ GX10 > 5ms

## 8. Comandos de Operación

### Gestión de Sandboxes

```bash
# Ejecutar sandbox específico
ura sandbox run mantenimiento

# Ver estado de todos los sandboxes
ura sandbox status

# Ver logs de un sandbox
ura sandbox logs aprendizaje

# Forzar ejecución de rotación
ura sandbox rotate
```

### Gestión de Versiones

```bash
# Crear nueva versión candidata
ura version create

# Ver versiones candidatas
ura version list candidates

# Promover candidata a aprobada
ura version promote v10.1

# Ver versiones aprobadas
ura version list approved

# Eliminar versión antigua
ura version delete v9.1
```

### Rollback

```bash
# Rollback manual
ura rollback

# Rollback a versión específica
ura rollback v9.2

# Ver historial de rollbacks
ura rollback history
```

## 9. Consideraciones de Seguridad

### Aislamiento de Sandboxes

**Sandboxes Docker (GX10)**
- Contenedores aislados con namespaces
- Límites de recursos (CPU, RAM, Disco)
- Redes separadas (bridge networks)
- Volúmenes de datos encriptados

**Sandboxes Locales (Mac)**
- Entornos virtuales Python separados
- Permisos de archivo restrictivos
- Logs encriptados en reposo
- Comunicación vía sockets Unix

### Validación de Cambios

**Antes de Promoción**
- Escaneo de vulnerabilidades (bandit)
- Auditoría de dependencias (pip-audit)
- Verificación de firmas de código
- Revisión de logs de seguridad

**Después de Rollback**
- Análisis de causa raíz
- Registro en URA_DEPRECATED.md
- Notificación al usuario
- Plan de corrección

## 10. Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────┐
│                     Mac (16GB)                          │
│                   Orquestador                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   PM2        │  │  Sandbox 1   │  │  Sandbox 4   │ │
│  │  Processes   │  │ Mantenimiento│  │Documentación │ │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘ │
│                            │                  │         │
│                            └────────┬─────────┘         │
│                                     │                   │
│                              10GbE Ethernet            │
│                                     │                   │
│                                     ▼                   │
│  ┌─────────────────────────────────────────────────┐ │
│ │                  GX10 (128GB)                      │ │
│ │                Cerebro de IA                       │ │
│ │  ┌──────────────┐  ┌──────────────┐              │ │
│ │  │   Ollama     │  │  Sandbox 2   │              │ │
│ │  │   Models     │  │  Seguridad   │              │ │
│ │  └──────────────┘  └──────┬───────┘              │ │
│ │                          │                        │ │
│ │  ┌──────────────┐        │                        │ │
│ │  │  Sandbox 3   │◄───────┘                        │ │
│ │  │  Aprendizaje │                                 │ │
│ │  └──────────────┘                                 │ │
│ └───────────────────────────────────────────────────┘
│
│  ┌─────────────────────────────────────────────────┐
│ │              Sistema de Versiones                │
│ │  ┌──────────────┐  ┌──────────────┐              │
│ │  │ candidates/  │  │  approved/   │              │ │
│ │  │ (cuarentena) │  │ (producción) │              │ │
│ │  └──────────────┘  └──────────────┘              │ │
│ └───────────────────────────────────────────────────┘
```

## 11. Referencias

**Archivos Relacionados**
- `core/sandbox_orchestrator.py` - Orquestador actual (5 sandboxes)
- `core/sandbox.py` - Sandbox simple para pruebas
- `URA_CHANGELOG.md` - Registro de cambios
- `URA_DEPRECATED.md` - Registro de código eliminado

**Documentación Externa**
- [Ollama Documentation](https://github.com/ollama/ollama)
- [PM2 Documentation](https://pm2.keymetrics.io/)
- [Docker Documentation](https://docs.docker.com/)

---

**Versión del Documento:** 1.0
**Fecha de Creación:** 2026-05-11
**Autor:** URA System
**Estado:** Especificación de Diseño Futuro

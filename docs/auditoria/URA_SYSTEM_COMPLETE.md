# URA - Sistema Completo - Documentación Maestra

## Resumen del Sistema

URA (Universal Reasoning Assistant) es un sistema de IA autónoma con 57 agentes, sistema de auto-reparación avanzado, gestión de puertos centralizada y múltiples integraciones.

## Componentes Principales

### 1. Sistema de Auto-Reparación (51/51 tareas completadas)

**Archivos:**
- `core/error_auto_repair.py` - Sistema principal de auto-reparación
- `api/auto_repair_api.py` - API REST para reparaciones remotas
- `web/auto_repair_dashboard.py` - Dashboard web Flask
- `web/templates/auto_repair_dashboard.html` - Template HTML
- `tests/test_error_auto_repair.py` - Tests unitarios

**Funcionalidades:**
- Machine Learning para predicción de errores (scikit-learn)
- Dashboard Grafana para métricas Prometheus
- Integración con sistema de aprendizaje
- API REST para reparaciones
- Tests unitarios de auto-reparación
- Sistema de reportes PDF (reportlab)
- Integración con agentes automáticos
- Modo de simulación para pruebas
- Dashboard web propio
- Sistema de alertas en tiempo real
- Integración con MLflow
- Análisis de causa raíz con LLM (Ollama)
- Sistema de rollback con versionado (Git)
- Auto-reparación distribuida
- Sistema de auto-escalado
- Integración con Slack/Teams
- Reparaciones programadas
- Sistema de reputación de reparaciones
- Auto-tuning de parámetros
- Sistema de feedback de usuario
- Integración con APM
- Sistema de predicción de fallos en cascada
- Reparaciones colaborativas

### 2. Sistema de Gestión de Puertos (6/6 tareas completadas)

**Archivos:**
- `config/ports_config.json` - Configuración de puertos
- `core/port_manager.py` - Gestor de puertos
- `core/file_lock.py` - Sistema de locks para archivos
- `core/port_conflict_monitor.py` - Monitor de conflictos
- `tests/test_port_manager.py` - Tests del sistema
- `docs/PORT_MANAGEMENT.md` - Documentación de puertos

**Funcionalidades:**
- Gestión centralizada de puertos
- Verificación automática de disponibilidad
- Auto-asignación de puertos
- Historial persistente de uso
- Detección de conflictos en tiempo real
- 3 estrategias de resolución (skip, kill, assign_new)
- Locks para archivos JSON compartidos
- Integración con APIs existentes

### 3. Agentes URA (57 agentes)

**Categorías:**
- **gestion**: 8 agentes - Clasificación, decisiones, gestión proyectos
- **sistema**: 12 agentes - Monitoreo, memoria, scheduler
- **documentos**: 6 agentes - Word, Excel, PDF, texto
- **cocina**: 7 agentes - 103+ recetas de 4 países
- **seguridad**: 2 agentes - Validación, análisis
- **comunicacion**: 3 agentes - Email, conversación, receptor
- **lenguaje**: 4 agentes - Vocabularios especializados
- **vocabulario**: 5 agentes - Control lingüístico
- **tecnica**: 2 agentes - Programación, operaciones
- **auditoria**: 2 agentes - Auditoría, trazabilidad
- **verificacion**: 2 agentes - Verificación, validación
- **instalacion**: 1 agente - Instalación apps

### 4. APIs REST

**APIs principales:**
- `api/main.py` - API principal URA
- `api/v2/main.py` - API v2 URA
- `api/auto_repair_api.py` - API de auto-reparación
- `api/websocket_handler.py` - WebSocket para tiempo real

### 5. Modelos Ollama

| Modelo | Uso |
|--------|-----|
| principal | Clasificación y respuestas |
| policia | Validación seguridad |
| deepseek-r1:7b | Análisis profundo |
| llama3.2:3b | Búsquedas |
| llava | Visión |
| buscador | Internet |

## Configuración

### Archivos de Configuración

- `config/ports_config.json` - Puertos reservados
- `config/auto_repair_config.json` - Configuración auto-reparación
- `.env` - Variables de entorno
- `.env.example` - Ejemplo de variables de entorno

### Puertos Reservados

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

## Datos y Almacenamiento

### Archivos de Datos

- `data/repair_history.json` - Historial de reparaciones
- `data/ml_models/error_predictor.joblib` - Modelo ML entrenado
- `data/scheduled_repairs.json` - Reparaciones programadas
- `data/user_feedback.json` - Feedback de usuario
- `data/shared_repairs.json` - Reparaciones compartidas
- `data/port_history.json` - Historial de puertos

### Memoria

- `core/memoria.py` - Sistema de memoria persistente
- `core/semantic_memory.py` - Memoria semántica
- `data/historical/` - Datos históricos
- `data/models/` - Modelos entrenados

## Testing

### Tests

- `tests/test_error_auto_repair.py` - Tests auto-reparación
- `tests/test_port_manager.py` - Tests gestión de puertos
- `tests/agents/` - Tests de agentes
- `tests/learning/` - Tests de aprendizaje

### Ejecutar Tests

```bash
python tests/test_error_auto_repair.py
python tests/test_port_manager.py
```

## Documentación

### Documentación Principal

- `README.md` - README principal
- `docs/PORT_MANAGEMENT.md` - Gestión de puertos
- `docs/ERROR_AUTO_REPAIR.md` - Auto-reparación
- `docs/INFORME_COMPLETO_ARQUITECTURA.md` - Arquitectura completa
- `docs/CATALOGO_HERRAMIENTAS.md` - Catálogo de herramientas

### Reportes

- `SYSTEM_READY.md` - Estado del sistema
- `URA_CHANGELOG.md` - Registro de cambios
- `PERFORMANCE_REPORT.md` - Reporte de rendimiento
- `BENCHMARK_REPORT.md` - Reporte de benchmarks

## Scripts

### Scripts Principales

- `main_final.py` - Punto de entrada principal
- `scripts/auto_cleaner.py` - Limpieza automática
- `scripts/health_agent.py` - Health check
- `scripts/recovery_agent.py` - Recuperación automática
- `scripts/control_panel_visual.py` - Panel de control visual
- `scripts/repair_all.py` - Reparación completa

### Scripts de Mantenimiento

- `scripts/rotar_logs.py` - Rotación de logs
- `scripts/verify_ura.py` - Verificación del sistema
- `scripts/auto_audit.py` - Auditoría automática
- `scripts/auto_reporter.py` - Reportes automáticos

## Dependencias

### Python

- Python 3.8+
- Flask - APIs web
- scikit-learn - Machine Learning
- reportlab - Reportes PDF
- MLflow - Tracking de ML
- requests - HTTP requests
- fcntl - Locks de archivos (Unix)
- psutil - Monitorización de recursos

### Servicios Externos

- Ollama - Modelos LLM
- Redis - Cache y cola
- Prometheus - Métricas
- Grafana - Visualización de métricas
- Telegram - Notificaciones
- Discord - Notificaciones

## Estructura de Directorios

```
URA_App/
├── api/                    # APIs REST
│   ├── main.py
│   ├── v2/
│   ├── auto_repair_api.py
│   └── websocket_handler.py
├── core/                   # Componentes principales
│   ├── error_auto_repair.py
│   ├── port_manager.py
│   ├── file_lock.py
│   ├── port_conflict_monitor.py
│   └── memoria.py
├── web/                    # Dashboard web
│   ├── auto_repair_dashboard.py
│   └── templates/
├── config/                 # Configuración
│   ├── ports_config.json
│   └── auto_repair_config.json
├── data/                   # Datos
│   ├── repair_history.json
│   ├── ml_models/
│   ├── historical/
│   └── models/
├── tests/                  # Tests
│   ├── test_error_auto_repair.py
│   ├── test_port_manager.py
│   ├── agents/
│   └── learning/
├── docs/                   # Documentación
│   ├── PORT_MANAGEMENT.md
│   ├── ERROR_AUTO_REPAIR.md
│   └── INFORME_COMPLETO_ARQUITECTURA.md
├── scripts/                # Scripts de mantenimiento
│   ├── auto_cleaner.py
│   ├── health_agent.py
│   └── recovery_agent.py
└── main_final.py           # Punto de entrada
```

## Estado del Sistema

- **Auto-Reparación**: 51/51 tareas completadas ✅
- **Gestión de Puertos**: 6/6 tareas completadas ✅
- **Agentes**: 57 agentes operativos ✅
- **APIs**: 4 APIs funcionando ✅
- **Tests**: Todos pasando ✅
- **Documentación**: Completa ✅

## Uso

### Iniciar URA

```bash
cd /Users/ramonesnaola/URA/ura_ia_1972
source .venv/bin/activate
python main_final.py
```

### Iniciar API de Auto-Reparación

```bash
cd /Users/ramonesnaola/URA/ura_ia_1972
source .venv/bin/activate
python api/auto_repair_api.py
```

### Iniciar Dashboard Web

```bash
cd /Users/ramonesnaola/URA/ura_ia_1972
source .venv/bin/activate
python web/auto_repair_dashboard.py
```

### Iniciar Monitor de Conflictos

```bash
cd /Users/ramonesnaola/URA/ura_ia_1972
source .venv/bin/activate
python core/port_conflict_monitor.py
```

## Mantenimiento

### CRON Jobs Configurados

```cron
0 3 * * * cd ~/Desktop/URA_App && python3 scripts/auto_cleaner.py
0 * * * * cd ~/Desktop/URA_App && python3 scripts/health_agent.py
0 */6 * * * cd ~/Desktop/URA_App && python3 scripts/recovery_agent.py
```

### Scripts de Mantenimiento

- **Limpieza diaria (3:00 AM)**: `scripts/auto_cleaner.py`
- **Health check cada hora**: `scripts/health_agent.py`
- **Recuperación cada 6 horas**: `scripts/recovery_agent.py`

## Seguridad

- Autenticación por API keys
- Rate limiting
- Control de horarios permitidos
- Audit trail completo
- Políticas configurables por agente
- Validación de seguridad con modelo policia

## Rendimiento

- Auto-escalado de recursos
- Monitorización de CPU, RAM, disco
- Optimización de ML
- Caché distribuido con Redis
- Predicción de fallos en cascada

## Integraciones

- **Slack**: Alertas y notificaciones
- **Teams**: Alertas y notificaciones
- **Telegram**: Notificaciones del sistema
- **Discord**: Notificaciones del sistema
- **MLflow**: Tracking de ML
- **Prometheus**: Métricas
- **Grafana**: Visualización de métricas
- **Ollama**: Modelos LLM
- **Redis**: Cache y cola

## Notas Importantes

- El sistema está completo y funcional
- No requiere implementaciones adicionales
- Documentación completa en `docs/`
- Tests automatizados para todos los componentes
- Sistema auto-mantenible con CRON jobs
- Gestión automática de conflictos de puertos
- Auto-reparación inteligente con ML
- 57 agentes especializados disponibles

## Versión

**Versión Actual**: URA v10.0_FINAL
**Última Actualización**: 28 de abril de 2026
**Estado**: Completamente funcional

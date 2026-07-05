# Propuesta — Fase 11: Plataforma (Capacidades del Motor)

> **Versión:** 1.0
> **Fecha:** 2026-07-05
> **Estado:** 🔮 Planificado
> **Fase anterior:** Fase 10 (Estabilización)
> **Objetivo:** Convertir el programa monolítico en una plataforma extensible

---

## Prerrequisitos para Iniciar (Go/No-Go)

| # | Requisito | Criterio |
|---|-----------|----------|
| G.1 | Fase 10 cerrada | Tag `vX.Y.Z-fase10` existente |
| G.2 | Closeout aprobado | `docs/architecture/FASE10_CLOSEOUT.md` existe y refleja estado real |
| G.3 | Baseline generado | Commit del tag Fase 10 documentado como baseline de Fase 11 |
| G.4 | Sin incidencias críticas | `pytest` 0 failures, `sys.exit(78)` eliminado, `guardian_logger.py` corregido |
| G.5 | CI verde | Todos los hooks de pre-commit pasan sin errores nuevos |

**Decisión:** Go ✅ / No-Go ❌

---

## Principio Rector

Fase 9 construyó la **infraestructura mínima** (PluginRegistry, Executor,
DegradedMode, CLI modular). Fase 11 la explota para crear un **ecosistema
de extensión** donde nuevos módulos se integren sin tocar el núcleo.

Fase 11 construye el **motor** en el sentido de plataforma.
Fase 12 hará inteligente ese motor.

---

## Regla Global de No Regresión

Ninguna fase podrá degradar rendimiento, calidad o funcionalidad respecto al
baseline de la fase anterior sin documentarlo **y justificarlo** en el Closeout.

| Dimensión | Qué no puede degradarse |
|-----------|------------------------|
| Rendimiento | Tiempos de respuesta CLI, latencia de búsqueda, throughput de ingestión |
| Calidad | Tests pasando, precisión de recuperación, cobertura de código |
| Funcionalidad | Comandos CLI existentes, endpoints API, plugins cargables |

Si una fase introduce una mejora que **inherentemente** degrada una métrica,
debe documentar la degradación esperada en la propuesta, justificar el
trade-off y verificar en el Closeout que la degradación real está dentro
de lo estimado.

---

## Regla Transversal (Fases 10–13)

No abrir una fase nueva sin haber cerrado la anterior mediante:

| Paso | Requisito |
|------|-----------|
| Validación completa | Checklist de cierre (compilación, lint, tests, smoke) |
| Actualización de documentación | AGENTS.md + propuesta de fase reflejan estado real |
| Comparación con baseline | 0 regresiones funcionales vs commit/tag de inicio |
| Tag de versión | `git tag -a vX.Y.Z-faseN` |
| Acta de cierre | `docs/architecture/FASEN_CLOSEOUT.md` actual |

---

## Definición de Baseline

El baseline de cada fase es el **commit etiquetado** de la fase anterior e
incluye el estado completo del repositorio en ese punto. Para garantizar
reproducibilidad, el baseline documenta:

| Componente | Detalle |
|------------|---------|
| Hardware | CPU, GPU, RAM, almacenamiento |
| Sistema operativo | Distribución, kernel, versión |
| Python | `python --version`, entorno virtual usado |
| Modelo de embeddings | Nombre, tamaño, provider (Ollama/Qdrant) |
| Modelo LLM | Nombres, tamaños, cuantización, provider |
| Tamaño del corpus | Nº de documentos, Nº de fragmentos indexados |
| Configuración del índice | Dimensión de vectors, distancia, chunk size, overlap |
| Conjunto de evaluación | Consultas de referencia (mín. 200) con respuestas anotadas |
| Versión del repositorio | Tag git + `git rev-parse HEAD` |
| Métricas de referencia | Tests pasando/fallando, lint errors, tiempos CLI, cobertura |

Cada fase genera su propio baseline al cerrarse, que sirve como punto de
comparación para la fase siguiente.

---

## Criterios de Entrada

| # | Criterio | Estado |
|---|----------|--------|
| E.1 | Fase 10 cerrada y etiquetada | Pendiente |
| E.2 | `pytest` 0 failures | Pendiente |
| E.3 | CI completamente verde | Pendiente |

---

## Objetivos

### 11.1 — Plugins instalables

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Formato de paquete | Plugin como directorio con `plugin.yaml` + `__init__.py` | 3-5h |
| Registro desde disco | `PluginRegistry.scan(path)` escanea directorios adicionales | 2-3h |
| Dependencias entre plugins | Declarativas en `plugin.yaml`, resolución de orden | 3-5h |
| Ciclo de vida | `on_load`, `on_unload`, `on_config_change` hooks | 3-5h |
| CLI para plugins | `ura.py plugin install/list/enable/disable` | 2-4h |

### 11.2 — Hooks y Eventos

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Bus de eventos interno | `EventBus` síncrono/asíncrono con tópicos | 4-6h |
| Hooks de pipeline | `pre_ingest`, `post_ingest`, `pre_search`, `post_search` | 3-5h |
| Hooks de sistema | `on_startup`, `on_shutdown`, `on_degraded`, `on_restore` | 2-3h |
| Hook de CLI | `pre_command`, `post_command` para wrappers/auditoría | 2-3h |
| Filtros de eventos | Suscripción por patrón de tópico (ej. `knowledge.*`) | 2-3h |

### 11.3 — Pipelines Dinámicos

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Pipeline configurable | Secuencia de etapas definida en YAML/JSON | 4-6h |
| Etapas reutilizables | `IngestStage`, `TransformStage`, `IndexStage`, `SearchStage` | 4-6h |
| Ramificación condicional | `if/else` en pipeline según metadata o resultado anterior | 3-5h |
| Pipeline CLI | `ura.py pipeline run/list/logs` | 2-3h |

### 11.4 — Observabilidad Técnica

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| `/metrics` | Endpoint con métricas internas (plugins, executor, tiempos) | 2-4h |
| `/health` | Health check agregado (todos los subsistemas) | 1-2h |
| `/ready` | Readiness check (todo inicializado correctamente) | 1-2h |
| Métricas de plugins | Cuántos cargados, activos, fallos, eventos emitidos | 2-3h |
| Estadísticas del Executor | Comandos ejecutados, timeouts, errores, cola | 2-3h |
| Estado de DegradedMode | Historial de degradaciones/restauraciones | 1-2h |

**Nota:** Esto NO incluye Prometheus/Grafana/alertas — eso es Fase 13.
Aquí solo se trata de que el sistema exponga información estructurada
en endpoints estándar.

### 11.5 — Extensión por Terceros

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Plugin SDK mínimo | Clase base `PluginBase` mejorada con hooks y metadata | 3-5h |
| Documentación de API | `docs/plugins/` con ejemplos de plugins funcionales | 3-5h |
| Plugin template | `cookiecutter` o template para `ura plugin create` | 2-3h |
| Sandbox de plugins | Aislamiento opcional por subprocess (reutilizar Executor) | 4-6h |

### 11.6 — Objetivos de Rendimiento (Medibles)

| Métrica | Objetivo | Cómo se mide |
|---------|----------|--------------|
| Plugin install → activo | < 1s | `ura.py plugin install ./plugin` desde disco local |
| EventBus emisión → recepción | < 50ms | Suscriptor local, mismo proceso |
| Pipeline 3 etapas (vacío) | < 100ms | Pipeline YAML sin IO |
| `/health` response | < 50ms | Petición HTTP local |
| Latencia extra de plugin hook | < 5ms por hook | Plugin no-operativo en hook `pre_command` |

---

## Arquitectura

```
motor/
  plugin/          ← Fase 9 (base)
    base.py          PluginBase abstracto
    registry.py      PluginRegistry (scan, load, enable/disable)
  events/          ← Nuevo
    bus.py           EventBus síncrono/asíncrono
    topics.py        Tópicos predefinidos del sistema
  pipeline/        ← Nuevo
    engine.py        Motor de pipelines: carga YAML, ejecuta etapas
    stages.py        Etapas base (abstractas)
    registry.py      Registro de tipos de etapa
  observability/   ← Nuevo
    metrics.py       Colector de métricas internas
    health.py        Health/Readiness checks
    exporter.py      Serialización a JSON para /metrics, /health, /ready
```

---

## Lo que NO es Fase 11

- Algoritmos de IA (ranking, RAG, chunking semántico → Fase 12)
- Memoria contextual avanzada (→ Fase 12)
- Multiagente con Planner/Researcher (→ Fase 12)
- Dashboard gráfico, alertas, Prometheus (→ Fase 13)
- Documentación para usuarios finales (→ Fase 13)

---

## Criterios de Cierre Obligatorios

Toda nueva funcionalidad es extensible mediante plugins/eventos, sin modificar el núcleo.

| # | Criterio | Detalle |
|---|----------|---------|
| C.1 | Plugin instalable | `ura.py plugin install ./my-plugin` sin tocar core/ |
| C.2 | EventBus funcional | Suscripción+emisión+desuscripción en 3+ tópicos |
| C.3 | Pipeline dinámico | Pipeline YAML con 3+ etapas ejecuta secuencia completa sin errores |
| C.4 | Observabilidad técnica | `/metrics`, `/health`, `/ready` responden con estado del sistema |
| C.5 | Sin regresiones | Mismos tests verdes que Fase 10 |
| C.6 | Validación transversa | Acta de cierre, tag, baseline comparado, docs actualizados |

Los objetivos de rendimiento (plugin install < 1s, EventBus < 50ms, etc.) se
definen en la sección 11.6 como metas medibles, no como requisitos de cierre.

# Propuesta — Fase 13: Producción

> **Versión:** 1.0
> **Fecha:** 2026-07-05
> **Estado:** 🔮 Planificado
> **Fase anterior:** Fase 12 (Inteligencia)
> **Objetivo:** Que otra persona pueda instalar URA y usarlo sin conocer el código

---

## Prerrequisitos para Iniciar (Go/No-Go)

| # | Requisito | Criterio |
|---|-----------|----------|
| G.1 | Fase 12 cerrada | Tag `vX.Y.Z-fase12` existente |
| G.2 | Closeout aprobado | `docs/architecture/FASE12_CLOSEOUT.md` existe |
| G.3 | Baseline generado | Commit del tag Fase 12 documentado como baseline de Fase 13 |
| G.4 | KE 2.0 cumple métricas | Recall@10 ≥ 0.85, NDCG@10 +20% vs baseline, latencia P95 ≤ 500ms |
| G.5 | Multiagente funcional | Planner → Researcher → Executor → Validator operativo en pipeline |
| G.6 | Sin regresiones | Mismos tests verdes que Fase 11 |

**Decisión:** Go ✅ / No-Go ❌

---

## Principio Rector

Fase 13 cierra el ciclo: de un proyecto personal a un producto instalable.
Cuando todo lo anterior (estabilidad, plataforma, inteligencia) esté sólido,
se prepara el sistema para operar en producción real, con monitorización,
documentación y despliegue estandarizado.

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

| # | Criterio | Estado |
|---|----------|--------|
| E.1 | Fase 12 cerrada y etiquetada | Pendiente |
| E.2 | KE 2.0 funcional con NDCG@10 +20% | Pendiente |
| E.3 | Multiagente operativo | Pendiente |

---

## Objetivos

### 13.1 — Docker y Despliegue

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Dockerfile oficial | Imagen multi-etapa con dependencias mínimas | 3-5h |
| docker-compose.yml | Servicios: api, knowledge-engine, plugins, postgres (opcional) | 4-6h |
| Healthcheck en contenedor | Endpoint `/health` para orquestadores | 1-2h |
| Entrypoint configurable | Variables de entorno para configuración inicial | 2-3h |
| Imagen publicada | Docker Hub o GitHub Container Registry | 2-3h |

### 13.2 — Instalación Sencilla

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Script `install.sh` | Detecta SO, instala dependencias, configura servicios | 4-6h |
| Paquete pip | `pip install ura` con entry points | 3-5h |
| Configuración guiada | `ura.py setup` o `ura init` interactivo | 3-5h |
| Desinstalación limpia | `ura.py uninstall` o script inverso | 2-3h |

### 13.3 — Observabilidad Operativa

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Exportador Prometheus | Endpoint `/metrics` en formato OpenMetrics estándar | 3-5h |
| Dashboard Grafana | Panel predefinido con métricas clave | 4-6h |
| Alertas | Reglas de alerta para caídas, degradación, errores | 3-5h |
| Tracing distribuido | OpenTelemetry para trazas entre componentes | 5-8h |
| Logs estructurados | Formato JSON con correlation ID por petición | 3-5h |
| Métricas históricas | Almacenamiento en Prometheus + períodos de retención | 2-4h |
| SLO/SLA | Definción y monitoreo de objetivos de nivel de servicio | 3-5h |

### 13.4 — Documentación para Usuarios

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| README completo | Instalación, configuración, ejemplos rápidos | 3-5h |
| Guía de inicio rápido | Primeros pasos en 5 minutos | 2-3h |
| Documentación de API | OpenAPI/Swagger para todos los endpoints públicos | 4-6h |
| Documentación de plugins | Cómo crear, instalar y configurar plugins | 4-6h |
| Documentación de CLI | Referencia completa de comandos | 3-5h |
| Ejemplos y tutoriales | Casos de uso reales con código | 5-8h |

### 13.5 — Integración Continua Completa

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| CI en GitHub Actions | Lint, test, build, push imagen Docker | 4-6h |
| Release automatizado | `git tag` → build → publish pip + docker | 3-5h |
| Pruebas de integración | Tests que usan servicios reales (Ollama, Qdrant) | 5-8h |
| Pruebas de humo post-deploy | Verificar que el sistema responde tras release | 2-4h |
| Matriz de SO | Tests en Ubuntu, Debian, macOS (ARM + x86) | 4-6h |

### 13.6 — Objetivos de Rendimiento (Medibles)

| Métrica | Objetivo | Cómo se mide |
|---------|----------|--------------|
| `pip install ura` | ≤ 60s | Instalación limpia Ubuntu 24.04 ARM |
| `docker run ura` → primer `/health` OK | ≤ 10s | Contenedor sin modelo precargado |
| `ura setup` completo | ≤ 5min | Configuración interactiva mínima |
| Latencia `/health` | P95 ≤ 100ms | Sin carga concurrente |
| Uptime del servicio | ≥ 99% | Monitoreo 7 días consecutivos |
| Documentación evaluada por tercero | Completa y comprensible | Test de usuario externo sin conocimiento del código |

---

## Arquitectura

```
ura/
  Dockerfile               ← Nuevo
  docker-compose.yml       ← Nuevo
  install.sh               ← Nuevo
  docs/
    user/
      QUICKSTART.md        ← Nuevo
      INSTALL.md           ← Nuevo
      CLI_REFERENCE.md     ← Nuevo
      PLUGIN_DEV.md        ← Nuevo
    api/
      openapi.json         ← Nuevo
  .github/
    workflows/
      ci.yml               ← Nuevo
      release.yml          ← Nuevo
```

---

## Lo que NO es Fase 13

- Nuevos algoritmos de IA (→ Fase 12)
- Cambios en la arquitectura de plugins (→ Fase 11)
- Refactorización del núcleo (→ Fase 9-10)
- Mejora de tests unitarios (→ Fase 10)

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

## Criterios de Cierre Obligatorios

Instalación reproducible, despliegue automatizado, monitorización completa y documentación suficiente para un usuario externo.

| # | Criterio | Detalle |
|---|----------|---------|
| C.1 | Docker | `docker run ura` funciona con configuración mínima |
| C.2 | pip install | `pip install ura && ura --help` funciona |
| C.3 | Prometheus + Grafana | Dashboard predefinido importable, alertas funcionales |
| C.4 | Documentación | README, QUICKSTART, INSTALL, CLI, API, plugins documentados para usuario externo |
| C.5 | CI/CD | GitHub Actions: lint → test → build → release → publish |
| C.6 | OpenAPI | Endpoints públicos documentados y accesibles vía Swagger UI |
| C.7 | Sin regresiones | Mismos tests verdes que Fase 12 |
| C.8 | Validación transversa | Acta de cierre, tag, baseline comparado, docs actualizados |

Los objetivos de rendimiento (tiempos de instalación, latencias, uptime) se
definen en la sección 13.6 como metas medibles. El Closeout documentará
los valores obtenidos frente a esos objetivos, pero pequeñas variaciones
no bloquean el cierre de la fase.

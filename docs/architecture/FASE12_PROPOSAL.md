# Propuesta — Fase 12: Inteligencia

> **Versión:** 1.0
> **Fecha:** 2026-07-05
> **Estado:** 🔮 Planificado
> **Fase anterior:** Fase 11 (Plataforma)
> **Objetivo:** Hacer inteligente el motor construido en Fase 11

---

## Prerrequisitos para Iniciar (Go/No-Go)

| # | Requisito | Criterio |
|---|-----------|----------|
| G.1 | Fase 11 cerrada | Tag `vX.Y.Z-fase11` existente |
| G.2 | Closeout aprobado | `docs/architecture/FASE11_CLOSEOUT.md` existe |
| G.3 | Baseline generado | Commit del tag Fase 11 documentado como baseline de Fase 12 |
| G.4 | Plataforma validada | Plugins instalables, EventBus, pipelines dinámicos, `/metrics \| /health \| /ready` operativos |
| G.5 | Sin regresiones | Mismos tests verdes que Fase 10 |

**Decisión:** Go ✅ / No-Go ❌

---

## Principio Rector

Fase 11 construyó el **motor** (hooks, eventos, pipelines, plugins).
Fase 12 hace **inteligente** ese motor añadiendo algoritmos de IA,
razonamiento y memoria sobre una plataforma estable.

La separación evita que la lógica de IA quede acoplada a una
arquitectura que todavía está cambiando.

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
| E.1 | Fase 11 cerrada y etiquetada | Pendiente |
| E.2 | Sistema de hooks y eventos operativo | Pendiente |
| E.3 | Pipelines dinámicos funcionales | Pendiente |

---

## Objetivos

### 12.1 — Knowledge Engine 2.0

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Ranking híbrido | Fusión de scores vectorial + FTS5 + BM25 con pesos configurables | 5-8h |
| Reranking | Segundo paso con cross-encoder o LLM para top-K resultados | 6-10h |
| Chunking semántico | División por fronteras semánticas (no por tokens) usando embeddings | 5-8h |
| Recuperación multi-etapa | Coarse (vectorial rápido) → Fine (reranking caro) | 4-6h |
| Expansión de consultas | Query expansion con términos relevantes del grafo | 4-6h |
| Resúmenes de contexto | Cache de resúmenes por sesión para mantener coherencia | 3-5h |

### 12.2 — Memoria Contextual Avanzada

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Memoria episódica | Almacenamiento de interacciones recientes con pesos temporales | 5-8h |
| Memoria semántica | Conocimiento factual extraído de documentos y conversaciones | 5-8h |
| Compresión de memoria | Resúmenes periódicos para evitar crecimiento infinito | 4-6h |
| Recuperación contextual | Búsqueda en memoria usando embedding del contexto actual | 4-6h |
| Olvido dirigido | Decaimiento temporal y eliminación de información obsoleta | 3-5h |

### 12.3 — Sistema Multiagente

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Planner | Descompone tareas complejas en subtareas planificables | 6-10h |
| Researcher | Busca información en múltiples fuentes (KE, web, docs) | 5-8h |
| Memory Agent | Gestiona memoria episódica y semántica para el equipo | 4-6h |
| Executor Agent | Ejecuta subtareas usando el SubprocessExecutor | 3-5h |
| Validator Agent | Verifica resultados contra criterios de calidad | 4-6h |
| Supervisor | Coordina agentes, detecta loops, asigna prioridades | 6-10h |

### 12.4 — Consenso y Autoevaluación

| Feature | Descripción | Esfuerzo |
|---------|-------------|----------|
| Consenso entre agentes | Votación ponderada cuando múltiples agentes divergen | 4-6h |
| Autoevaluación de respuestas | El sistema puntúa su propia salida antes de entregarla | 3-5h |
| Aprendizaje de patrones | Detección de consultas frecuentes y optimización de rutas | 5-8h |
| Recuperación automática | Si un agente falla, el supervisor reasigna la tarea | 3-5h |

### 12.5 — Objetivos de Rendimiento (Medibles)

| Métrica | Objetivo | Cómo se mide |
|---------|----------|--------------|
| Recall@10 | ≥ 0.85 | Frente a corpus de referencia anotado (200+ consultas) |
| NDCG@10 | ≥ baseline Fase 10 + 20% | Mismo corpus de referencia |
| Latencia P95 de búsqueda | ≤ 500ms | Búsqueda híbrida (vectorial + FTS5) sin caché |
| Latencia P95 de reranking | ≤ 2s | Reranking de top-20 con cross-encoder ligero |
| Consumo memoria (KE) | ≤ 2GB RSS | Índice de 100K fragmentos |
| Tiempo de indexación | ≤ baseline Fase 10 + 10% | Pipeline completo: chunking → embedding → almacenamiento |
| Calidad respuestas multiagente | ≥ 80% aceptación | Evaluación LLM-as-judge en 50 tareas de prueba |

---

## Arquitectura

```
motor/
  intelligence/    ← Nuevo
    ranking/         Ranking híbrido, reranking, BM25 fusion
    memory/          Memoria episódica, semántica, compresión, olvido
      episodic.py
      semantic.py
      compression.py
      decay.py
    agents/          Sistema multiagente
      planner.py
      researcher.py
      memory_agent.py
      executor_agent.py
      validator.py
      supervisor.py
    consensus/       Votación, autoevaluación, aprendizaje
      voting.py
      self_eval.py
      pattern_learner.py
```

Los agentes usan **el sistema de plugins de Fase 11** como mecanismo
de registro. Cada agente es un plugin que emite y escucha eventos.

---

## Lo que NO es Fase 12

- Cambios en la arquitectura de plugins (→ Fase 11)
- Observabilidad operativa (→ Fase 13)
- Docker, CI/CD, releases (→ Fase 13)
- Documentación para usuarios (→ Fase 13)

---

## Criterios de Cierre Obligatorios

KE 2.0 operativo con métricas documentadas frente al benchmark de referencia.

| # | Criterio | Detalle |
|---|----------|---------|
| C.1 | KE 2.0 funcional | Ranking híbrido, reranking, chunking semántico operativos en pipeline |
| C.2 | Memoria contextual | Recuperación coherente en sesiones de +10 turnos con compresión funcional |
| C.3 | Multiagente | Planner descompone tarea, Supervisor coordina, Validator verifica |
| C.4 | Consenso funcional | Votación entre agentes con resultado reproducible |
| C.5 | Sin regresiones | Mismos tests verdes que Fase 11 |
| C.6 | Validación transversa | Acta de cierre, tag, baseline comparado, docs actualizados |

Los objetivos de rendimiento (Recall@10, NDCG@10, latencias, memoria) se
definen en la sección 12.5 como metas medibles. El Closeout documentará
los valores obtenidos frente a esos objetivos, pero pequeñas variaciones
no bloquean el cierre de la fase.

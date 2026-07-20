# Roadmap de Capacidades — URA post-v2.3

**Infraestructura congelada en v2.3 (ADR-030).**  
Todo nuevo desarrollo será sobre capacidades funcionales, no sobre arquitectura de pipeline.
La pregunta cambia: de "¿cómo debe ejecutarse URA?" a **"¿qué debe ser capaz de hacer URA por sí misma?"**

---

## Verificaciones periódicas (infraestructura)

Aunque la infraestructura esté congelada, se mantienen estas comprobaciones:

| Check | Frecuencia | Qué detecta |
|-------|------------|-------------|
| Compatibilidad API v1 | Cada release | Plugins que usan métodos deprecated |
| Tiempo medio de pipeline | Semanal | Degradaciones por crecimiento del ledger |
| Frecuencia rollbacks/promociones | Mensual | Salud del pipeline |
| Crecimiento del ExecutionLedger | Mensual | Retención y rotación de datos |
| Compatibilidad de plugins | Cada release | Plugins que requieren versión superior del motor |

---

## Orden de ejecución

```
Autonomía ──→ Memoria ──→ Razonamiento ──→ Autoevaluación ──→ Descubrimiento ──→ Agentes
```

Cada bloque aprovecha las capacidades del anterior.

---

## Bloque 1 — Autonomía (v3.0, prioridad máxima)

**Objetivo:** URA puede trabajar durante horas con mínima supervisión.

### Componentes

```
┌──────────────────────────────────────────────────────────┐
│                    AUTONOMÍA (v3.0)                       │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Goal    │──│ Planner  │──│  Task    │──│ Evaluator│ │
│  │ Manager  │  │          │  │ Executor │  │          │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│                                    │                     │
│                                    ▼                     │
│  ┌──────────┐            ┌──────────────────┐           │
│  │ Learning │────────────│ ExecutionLedger  │           │
│  │  Plugin  │            │  (v2.3 base)     │           │
│  └──────────┘            └──────────────────┘           │
│                                                          │
│  Presupuestos: tiempo, coste, llamadas, cambios, memoria │
└──────────────────────────────────────────────────────────┘
```

### Goal Manager
- Mantiene objetivos activos con estado y prioridad
- Elimina objetivos obsoletos
- Gestiona dependencias entre objetivos

### Planner
- Convierte objetivos en planes ejecutables
- Gestiona dependencias entre tareas
- Replanifica cuando una tarea falla
- Respeta presupuestos (tiempo, coste, llamadas, cambios, memoria)

### Task Executor
- Ejecuta tareas usando herramientas disponibles (plugins, scripts, pipeline_refactor)
- Reintenta según política de errores (transitorio → reintentar, bug → escalar)
- Reporta resultados al Evaluator

### Evaluator
- Comprueba si el objetivo se ha alcanzado
- Decide: continuar, corregir o finalizar
- Alimenta al Learning Plugin

### Learning Plugin
- Extrae lecciones de cada ejecución
- Actualiza conocimiento utilizable (memoria procedimental)
- Se apoya en el ExecutionLedger como fuente de datos

---

## Bloque 2 — Memoria y conocimiento

**Objetivo:** URA aprende del trabajo realizado.

| Capacidad | Descripción |
|-----------|-------------|
| Memoria episódica | Registro de acciones realizadas (qué, cuándo, por qué) |
| Memoria semántica | Conocimiento extraído del trabajo (patrones, reglas) |
| Memoria procedimental | Cómo resolver tareas recurrentes (recetas) |
| Detección de duplicados | Evitar conocimiento redundante |
| Consolidación y olvido | Comprimir información obsoleta |
| Trazabilidad | Cada conocimiento tiene origen y fecha |

**Implementación como:** extensiones de `ExecutionLedger` + banco de conocimiento en Qdrant.

---

## Bloque 3 — Razonamiento

**Objetivo:** Mejorar la calidad de las decisiones.

| Capacidad | Descripción |
|-----------|-------------|
| Verificación de hipótesis | Confirmar o refutar supuestos antes de actuar |
| Comparación de estrategias | Evaluar múltiples aproximaciones |
| Evaluación de incertidumbre | Cuantificar confianza en cada decisión |
| Planificación multi-paso | Anticipar consecuencias a varios niveles |
| Detección de contradicciones | Identificar decisiones incompatibles |
| Selección de herramientas | Elegir el plugin o script óptimo para cada tarea |

---

## Bloque 4 — Autoevaluación

**Objetivo:** URA mide la calidad de su propio trabajo.

| Capacidad | Descripción |
|-----------|-------------|
| Puntuación de resultados | Métrica objetiva por tarea completada |
| Detección de regresiones | Comparar contra ejecuciones históricas |
| Evaluación continua | Medir rendimiento en cada ciclo |
| Aprendizaje de errores | Ajustar comportamiento según fallos pasados |

**Implementación como:** extensión de `MetricsCollector` + `TrendAnalyzer`.

---

## Bloque 5 — Descubrimiento de conocimiento

**Objetivo:** Generar conocimiento útil, no solo recopilarlo.

| Capacidad | Descripción |
|-----------|-------------|
| Cruce de fuentes | Combinar información de plugins, ledger, git |
| Identificación de patrones | Detectar recurrencias en ejecuciones |
| Generación de hipótesis | Proponer relaciones causales |
| Detección de lagunas | Identificar áreas sin cubrir |
| Experimentos | Proponer y ejecutar validaciones |

---

## Bloque 6 — Especialización por agentes

**Objetivo:** Distribuir el trabajo entre agentes especializados.

| Agente | Responsabilidad |
|--------|----------------|
| Arquitectura | Decisiones estructurales, deuda técnica |
| Seguridad | Auditorías, secretos, permisos |
| Rendimiento | Benchmarks, profiling, optimización |
| Documentación | README, diagramas, ADRs |
| Investigación | Explorar nuevas bibliotecas, patrones |
| Pruebas | Cobertura, integración, regresión |

**Implementación como:** plugins independientes que comparten el `PipelineEngine` pero cada uno con su ámbito.

---

## Principios

1. **Todo como plugin o componente separado** — no modificar el flujo principal del pipeline.
2. **Cada bloque usa la salida del anterior** — autonomía genera datos → memoria los almacena → razonamiento los analiza → autoevaluación mide el resultado.
3. **Infraestructura congelada (ADR-030)** — no se toca `tuneladora/` salvo bug crítico.
4. **v2.3 es la base** — ledger, checkpoint, budget son los cimientos de autonomía y memoria.
5. **Presupuestos en todo** — tiempo, coste, llamadas a modelos, cambios, memoria. Si se supera alguno, el sistema replantea o se detiene de forma controlada.

# Roadmap de Capacidades — URA post-v2.3

**Infraestructura congelada en v2.3.**  
Todo nuevo desarrollo será sobre capacidades funcionales, no sobre arquitectura de pipeline.

---

## Orden de ejecución

Cada bloque aprovecha las capacidades del anterior.

```
Autonomía ──→ Memoria ──→ Razonamiento ──→ Autoevaluación ──→ Descubrimiento ──→ Agentes
```

---

## Bloque 1 — Autonomía (prioridad máxima)

**Objetivo:** URA puede trabajar durante horas con mínima supervisión.

| Capacidad | Descripción |
|-----------|-------------|
| Planificador de objetivos | Descomponer objetivos grandes en tareas atómicas |
| Priorización dinámica | Reordenar tareas según contexto y urgencia |
| Replanificación | Cuando una tarea falla, buscar ruta alternativa |
| Presupuestos | Tiempo, coste y recursos por tarea |
| Recuperación automática | Reintentar, degradar o escalar según el error |

**Implementación como:** plugins del PipelineEngine o componente separado que usa `pipeline_refactor` como herramienta.

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
3. **Infraestructura congelada** — no se toca `tuneladora/` salvo bug crítico.
4. **v2.3 es la base** — ledger, checkpoint, budget son los cimientos de memoria y autonomía.

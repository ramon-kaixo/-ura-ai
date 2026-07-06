# Fase 14 — Validación Operativa para Release Candidate

> **Estado:** Planificación (sin implementación)
> **Depende de:** Cierre transversal F10–F13 (`v0.14.0-plan`)
> **Clasificación actual:** Beta técnica avanzada
> **Objetivo de F14:** Obtener evidencia objetiva de robustez para decidir si el proyecto puede clasificarse como **Release Candidate**
> **Regla:** No añadir nuevas funcionalidades salvo que sean imprescindibles para las validaciones

---

## Contexto

El proyecto ha alcanzado madurez estructural en F10–F13:
- 1,100 tests, 0 fallos
- Arquitectura modular con contratos (12 ABCs, 13 Protocols, 16 ADRs)
- Retrieval híbrido R@10=0.87, NoCtx=0.5%
- Multi-Agent Runtime + consenso + reflexión + paralelismo
- Observabilidad (health, readiness, metrics, logging JSON, Prometheus, Grafana)
- Despliegue Docker + compose + entrypoint con healthchecks

**Lo que falta:** Validación operativa. Toda la evidencia actual es estructural
(tests unitarios e integración). No se ha probado el sistema bajo carga real,
caídas de dependencias, ejecución prolongada, ni escenarios extremos.

F14 no añade funcionalidades. Mide, valida, documenta.

---

## Orden de Ejecución

**Bloque 1 → Bloque 2 → Bloque 3 → Bloque 4 → Bloque 5**

| Bloque | Descripción | Esfuerzo | Prioridad |
|--------|-------------|----------|-----------|
| **1** | Load & Stress Testing | 10-16h | 🔴 Máxima |
| **2** | Resiliencia (fallos reales) | 8-12h | 🔴 Alta |
| **3** | End-to-End (componentes reales) | 6-10h | 🟡 Alta |
| **4** | Profiling (CPU, RAM, leaks) | 6-8h | 🟡 Media |
| **5** | RC Readiness Audit | 3-4h | 🔴 Final |
| **Total** | | **33-50h** | |

---

## Bloque 1 — Load & Stress Testing (10-16h)

### Objetivo
Demostrar que el sistema mantiene rendimiento aceptable bajo carga creciente
y sostenida. Establecer la primera línea base objetiva de capacidad.

### Regla
No modificar el código del sistema para que los benchmarks pasen.
Si el sistema no soporta la carga, se documenta el límite.

### Dependencias
- GX10 (GPU NVIDIA, 20 núcleos ARM, 128GB RAM unificada)
- Qdrant accesible (Docker o nativo)
- Ollama con al menos un modelo cargado

### Riesgos
- Resultados HW-dependientes (no reproducibles en Mac)
- Ollama puede saturarse con alta concurrencia
- Benchmarks lentos (ejecución ~2-4h completa)

### Criterios de Aceptación
- [ ] Benchmark concurrente del runtime (10, 100, 1000 workflows)
- [ ] Benchmarks de Retrieval (10, 50, 200 queries concurrentes)
- [ ] Benchmarks de Memory (store, search, consolidate concurrentes)
- [ ] Benchmarks de Consensus (votación con N agents concurrentes)
- [ ] Medición de CPU, RAM y latencias por nivel de carga
- [ ] Throughput dokumentado (workflows/segundo, queries/segundo)
- [ ] Identificación del cuello de botella dominante
- [ ] Documentación de límites conocidos

### Entregable
`docs/architecture/F14_LOAD_TESTS.md`

### Subtareas sugeridas
1. Diseñar suite de benchmarks parametrizable (3-4h)
   - Script Python que lanza N workflows concurrentes
   - Mide: duración total, P50/P95/P99 por operación
   - Captura: CPU%, RSS, Qdrant latencia, Ollama latencia
2. Benchmark Runtime: 10 → 100 → 1000 workflows (2h)
   - Workflow típico: Planner → Researcher → Executor → Validator → Consensus
3. Benchmark Retrieval: 10 → 50 → 200 queries concurrentes (2h)
   - Sobre corpus de evaluación existente (≥200 consultas)
4. Benchmark Memory: store + search concurrentes (2h)
   - 100 episodios → 1,000 → 10,000
5. Benchmark Consensus: N=3, N=5, N=10 agents (1h)
6. Análisis de resultados y documentación de límites (2h)

---

## Bloque 2 — Resiliencia (8-12h)

### Objetivo
Validar que el sistema se degrada elegantemente y se recupera
automáticamente ante fallos de dependencias y componentes.

### Regla
Cada escenario prueba la recuperación automática. Si el sistema
no se recupera, se documenta como riesgo conocido.

### Escenarios de Fallo

| ID | Escenario | Comportamiento Esperado | Componente Afectado |
|----|-----------|------------------------|---------------------|
| R01 | Qdrant cae durante una query | DegradedMode marca qdrant como degraded, retry con backoff, fallback a FTS5 | retrieval |
| R02 | Qdrant se recupera | DegradedMode restaura qdrant tras healthcheck exitoso | retrieval |
| R03 | Ollama no disponible | Timeout controlado, retry N veces, error graceful | agents, embeddings |
| R04 | Ollama timeout (modelo lento) | Circuit breaker se abre tras N fallos | agents |
| R05 | Agente tarda más del timeout | Supervisor cancela, fallback a resultado parcial | runtime |
| R06 | Workflow lanza excepción | PipelineFailed event, rollback de cambios parciales | pipeline |
| R07 | Cancelación manual de workflow | SIGTERM manejado, cleanup de recursos | pipeline |
| R08 | Plugin falla al cargar | RegistryV2 marca plugin como degraded, sistema sigue | plugin |
| R09 | Hook falla en cadena | Circuit breaker del hook, degraded mode del hook | events |
| R10 | Múltiples fallos simultáneos | Degradación progresiva, logging de cada evento | sistema |

### Criterios de Aceptación
- [ ] Matriz de fallos documentada con comportamiento real observado
- [ ] Cada escenario tiene un test reproducible
- [ ] DegradedMode responde correctamente en todos los casos
- [ ] Recuperación automática verificada sin intervención manual
- [ ] Sin crashes ni estados inconsistentes post-recuperación

### Subtareas sugeridas
1. Crear script de inyección de fallos (2h)
   - `scripts/pro/f14_fault_injector.py` — mata procesos Qdrant/Ollama,
     introduce latencia artificial, simula timeouts
2. Ejecutar R01-R05: Qdrant + Ollama (3h)
3. Ejecutar R06-R10: runtime, plugins, hooks, multi-fallo (3h)
4. Verificar DegradedMode + EventBus + logging en cada escenario (1h)
5. Documentar matriz de fallos y resultados (1-2h)

---

## Bloque 3 — End-to-End (6-10h)

### Objetivo
Verificar que el flujo completo funciona con componentes reales,
no mocks. Detectar regresiones de integración invisibles en tests unitarios.

### Regla
Mínimo 70% de componentes reales. Solo se permite mock para
lo que no esté disponible en el entorno (ej: un modelo LLM específico).

### Flujo a Validar

```
Usuario (CLI o script)
  → Pipeline (motor/pipeline/)
  → Retrieval (motor/intelligence/retrieval/) — Qdrant real
  → Memory (motor/intelligence/memory/) — SQLite + Qdrant real
  → Runtime (motor/intelligence/agents/runtime/) — agentes reales
  → Consensus (motor/intelligence/agents/consensus/) — votación real
  → Execution (motor/core/executor/) — subprocess real
  → Observability (motor/observability/) — health/metrics/logging real
```

### Casos de Prueba

| ID | Caso | Descripción |
|----|------|-------------|
| E01 | Consulta simple | `ura ask "¿qué es URA?"` → respuesta coherente |
| E02 | Consulta con contexto | Pregunta que requiere memoria episódica previa |
| E03 | Pipeline completo | `ura pipeline` con todas las etapas |
| E04 | Carga de plugin | Registrar y ejecutar un plugin real vía RegistryV2 |
| E05 | Evento sistema | `SYSTEM_STARTED` → hook on_startup se ejecuta |
| E06 | Degradación + restauración | Qdrant cae → pipeline sigue → Qdrant vuelve |
| E07 | Consulta multi-agente | Tarea que requiere Planner→Researcher→Executor→Validator→Consensus |
| E08 | Observabilidad | `/health`, `/ready`, `/metrics` responden con datos reales |

### Criterios de Aceptación
- [ ] Mínimo 6 de 8 casos E2E pasan con componentes reales
- [ ] Los 2 restantes documentados con causa y plan de mitigación
- [ ] Tiempo total del flujo E2E < 30s para consulta simple
- [ ] Sin errores no controlados (unhandled exceptions)

### Subtareas sugeridas
1. Diseñar suite E2E en `tests/test_e2e_f14.py` (2h)
2. Implementar E01-E04 con asserts reales (3h)
3. Implementar E05-E08 (2h)
4. Ejecutar contra GX10, documentar resultados (1h)

---

## Bloque 4 — Profiling (6-8h)

### Objetivo
Medir consumo de recursos del sistema en ejecución prolongada,
detectar memory leaks, crecimiento anómalo de memoria.

### Regla
No optimizar nada durante F14. Solo medir y documentar.
Las optimizaciones se planifican para F15 si son necesarias.

### Mediciones

| Métrica | Cómo se mide | Umbral de Alerta |
|---------|-------------|------------------|
| RSS del proceso principal | `psutil` cada 10s | Crecimiento > 10% en 1h sin carga |
| RSS de Qdrant | Docker stats | Crecimiento > 20% en 1h |
| RSS de Ollama | Docker stats | Crecimiento sostenido |
| CPU% del proceso principal | `psutil` cada 10s | P95 > 80% sostenido |
| MemoryStore size | `memory count()` cada minuto | Crecimiento lineal sin compresión |
| Latencia P95 sostenida | Histograma de metrics.py | Aumento > 10% en 30 min |
| Número de threads/processes | `/proc` | Crecimiento sin límite |

### Escenarios de Profiling

| ID | Escenario | Duración | Qué detecta |
|----|-----------|----------|-------------|
| P01 | Sistema en reposo | 30 min | Leaks en idle, logger, healthchecks |
| P02 | Carga constante media (10 wf/min) | 60 min | Leaks bajo carga, MemoryStore growth |
| P03 | Carga máxima (100 wf/min) | 15 min | Picos de CPU/RAM, GC pressure |
| P04 | Post-carga (vuelta a reposo) | 30 min | Liberación de memoria, cleanup |
| P05 | Ciclo carga-reposo-carga (3 ciclos) | 3h | Fatiga de recursos, fragmentación |

### Criterios de Aceptación
- [ ] RSS estable (±5%) durante P01 (sin leak en reposo)
- [ ] RSS no crece más del 15% durante P02
- [ ] RSS post-P04 retorna a niveles pre-P02 (±10%)
- [ ] MemoryStore no crece descontroladamente (compresión funciona)
- [ ] Latencia P95 no aumenta más del 10% durante P02
- [ ] Resultados documentados en RC_READINESS.md

### Subtareas sugeridas
1. Crear script de profiling (`scripts/pro/f14_profiling.py`) (2h)
   - Usa `psutil`, `tracemalloc`, Docker stats
   - Logging estructurado a JSON para análisis posterior
2. Ejecutar P01-P04 en GX10 (2h)
3. Ejecutar P05 (1h)
4. Analizar resultados, identificar leaks o anomalías (1-2h)

---

## Bloque 5 — Release Candidate Audit (3-4h)

### Objetivo
Emitir un juicio objetivo basado en toda la evidencia recogida
en F14. Decidir si el proyecto alcanza clasificación RC o qué
falta para ello.

### Entregable
`docs/architecture/RC_READINESS.md`

### Preguntas a Responder

| # | Pregunta | Criterio |
|---|----------|----------|
| 1 | ¿Qué requisitos faltan para RC? | Lista concreta con evidencia |
| 2 | ¿Qué riesgos permanecen abiertos? | Severidad, probabilidad, mitigación |
| 3 | ¿Qué deuda técnica sigue abierta? | Solo la que afecta a producción |
| 4 | ¿Qué evidencia existe de operación continua? | Horas de ejecución sin incidentes |
| 5 | ¿El sistema se degrada correctamente? | Matriz de fallos Bloque 2 |
| 6 | ¿El throughput es suficiente para uso real? | Benchmarks Bloque 1 |
| 7 | ¿Hay memory leaks? | Profiling Bloque 4 |
| 8 | ¿Los componentes E2E funcionan juntos? | Tests Bloque 3 |

### Criterios de Aceptación
- [ ] Documento RC_READINESS.md generado con respuestas a las 8 preguntas
- [ ] Decisión clara: RC alcanzado / RC condicionado / No RC
- [ ] Si no es RC, plan concreto de lo que falta (estimado en horas)
- [ ] Checklist de requisitos RC: presente/ausente con enlace a la evidencia

### Formato de Decisión

```
CLASIFICACIÓN FINAL: [RC | RC-CONDICIONADO | NO-RC]

Evidencia a favor:
  - ...

Evidencia en contra:
  - ...

Requisitos faltantes (si aplica):
  - ...

Riesgos remanentes:
  - ...

Próximo paso:
  - ...
```

---

## Resumen de Esfuerzo

| Bloque | Esfuerzo | Prioridad | Depende de |
|--------|----------|-----------|------------|
| 1 — Load & Stress | 10-16h | 🔴 Máxima | GX10 + Qdrant + Ollama |
| 2 — Resiliencia | 8-12h | 🔴 Alta | Bloque 1 (benchmarks primero) |
| 3 — End-to-End | 6-10h | 🟡 Alta | Bloques 1+2 (entorno estable) |
| 4 — Profiling | 6-8h | 🟡 Media | Bloque 1 (carga definida) |
| 5 — RC Audit | 3-4h | 🔴 Final | Bloques 1-4 completos |
| **Total** | **33-50h** | | |

---

## Reglas de F14

1. **No añadir nuevas funcionalidades.** Solo infraestructura de validación
   (scripts de benchmark, test E2E, profiling tools).
2. **No modificar el sistema para que pase los tests.** Si algo falla,
   se documenta como riesgo conocido.
3. **Cada bloque produce un entregable.** No se avanza al siguiente sin
   el entregable del anterior.
4. **Todo resultado negativo es un hallazgo válido.** Documentar, no ocultar.

---

## Dependencias Externas

| Dependencia | Para | Alternativa |
|-------------|------|-------------|
| GX10 (GPU NVIDIA) | Benchmarks realistas | CPU-only (valores no comparables) |
| Qdrant en Docker | Tests de resiliencia | Mock limitado (no evaluable) |
| Ollama + modelo ligero (7B) | Benchmarks agents | Mock AgentBase (solo estructural) |
| 2h de ejecución ininterrumpida | Profiling P05 | Períodos más cortos (menos precisión) |

---

## Decisión

**No comenzar implementación sin aprobación explícita.**

F14 es la fase más cara hasta ahora (33-50h) y no produce nuevas funcionalidades.
Su valor es la evidencia objetiva que permite decidir si el proyecto puede
llamarse Release Candidate.

Tras F14, si el RC Audit es positivo, se planificará F15 como fase de
producción real. Si es negativo, se documenta exactamente qué falta.

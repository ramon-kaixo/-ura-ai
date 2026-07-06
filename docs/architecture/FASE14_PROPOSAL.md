# Fase 14 — Validación Operativa para Release Candidate

> **Estado:** Planificación (sin implementación)
> **Depende de:** Cierre transversal F10–F13 (`v0.14.0-plan`)
> **Clasificación actual:** Beta técnica avanzada
> **Objetivo de F14:** Obtener evidencia objetiva de robustez y decidir si el proyecto puede clasificarse como **Release Candidate**
> **Regla cardinal:** No añadir funcionalidades. No corregir defectos durante la fase. Medir, demostrar, decidir.

---

## Contexto

El proyecto ha alcanzado madurez estructural en F10–F13:
- 1,100 tests, 0 fallos
- Arquitectura modular con contratos (12 ABCs, 13 Protocols, 16 ADRs)
- Retrieval híbrido R@10=0.87, NoCtx=0.5%
- Multi-Agent Runtime + consenso + reflexión + paralelismo
- Observabilidad (health, readiness, metrics, logging JSON, Prometheus, Grafana)
- Despliegue Docker + compose + entrypoint con healthchecks

**Lo que falta:** Validación operativa. Toda la evidencia actual es estructural.
No se ha probado el sistema bajo carga real, caídas de dependencias,
ejecución prolongada, ni escenarios extremos.

F14 no añade funcionalidades. Mide, valida, documenta.

---

## Reglas de la Fase

1. **No añadir nuevas funcionalidades.** Solo infraestructura de validación:
   scripts de benchmark, tests E2E, tools de profiling.
2. **No corregir defectos durante la validación.** Si un fallo impide
   continuar, se documenta como hallazgo crítico y se evalúa si procede
   corrección urgente o re-planificación. La decisión de corregir durante
   la fase solo se toma si el fallo **bloquea** el resto de pruebas.
3. **Completar toda la evaluación antes de decidir cambios.** Reunir toda
   la evidencia, analizar, y solo entonces planificar correcciones.
4. **Cada bloque termina con métricas objetivas y un criterio de aprobación
   o rechazo.** No se avanza al siguiente sin el entregable del anterior.
5. **Todo resultado negativo es un hallazgo válido.** Documentar, no ocultar.

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
Establecer la primera línea base objetiva de capacidad del sistema:
latencias, throughput, punto de saturación y degradación.

### Regla
No modificar el código del sistema para que los benchmarks pasen.
Si el sistema no soporta la carga, se documenta el límite.

### Entregable
`docs/architecture/F14_LOAD_TESTS.md` + archivos de datos en CSV/JSON
por cada benchmark, almacenados en `motor/data/benchmarks/f14/`.

### Benchmarks

| ID | Benchmark | Niveles | Métricas obligatorias |
|----|-----------|---------|----------------------|
| L01 | Runtime (workflows completos) | 10, 100, 1000 concurrentes | p50, p95, p99 latencia (ms), throughput (wf/s), CPU%, RSS (MB) |
| L02 | Retrieval (queries híbridas) | 10, 50, 200 concurrentes | p50, p95, p99 (ms), throughput (q/s), R@10, NoCtx rate |
| L03 | Memory (store + search) | 100, 1K, 10K episodios | p50, p95, p99 (ms), throughput (ops/s), RSS post-op |
| L04 | Consensus (votación) | N=3, N=5, N=10 agents | p50, p95, p99 (ms), agreement rate, throughput (votes/s) |
| L05 | Saturación progresiva | Escalada cada 30s hasta error | Tiempo hasta saturación (s), carga en saturación (wf/s), punto de degradación (wf/s), comportamiento post-saturación |

### Métricas a reportar por benchmark

| Métrica | Formato | Instrumentación |
|---------|---------|-----------------|
| p50/p95/p99 latencia | ms | Timer de MetricsRegistry, percentiles desde histograma |
| Throughput | operaciones/segundo | Counter de MetricsRegistry / duración total |
| CPU del proceso principal | % | `psutil.cpu_percent(interval=1)` |
| RSS del proceso principal | MB | `psutil.Process().memory_info().rss / 1e6` |
| RSS de Qdrant (si Docker) | MB | `docker stats qdrant --format {{.MemUsage}}` |
| RSS de Ollama (si Docker) | MB | `docker stats ollama --format {{.MemUsage}}` |
| Tiempo hasta saturación | segundos | Timestamp del primer error o timeout |
| Punto de degradación | wf/s | Carga donde P95 > 2× P95 en reposo |
| Comportamiento post-saturación | texto | ¿Se recupera solo? ¿Requiere reinicio? |

### Formato de datos
Cada benchmark produce un archivo JSON en `motor/data/benchmarks/f14/`:
```json
{
  "benchmark_id": "L01",
  "timestamp": "2026-07-06T10:00:00Z",
  "environment": {"host": "gx10", "cpu_cores": 20, "ram_gb": 128, "gpu": "nvidia-blackwell"},
  "results": [
    {
      "level": 10,
      "workflows": 10,
      "duration_s": 12.3,
      "throughput_wfs": 0.81,
      "latency_ms": {"p50": 1200, "p95": 2400, "p99": 3500},
      "cpu_percent": 45.2,
      "rss_mb": 320,
      "qdrant_rss_mb": 280,
      "ollama_rss_mb": 4200,
      "errors": 0,
      "timeouts": 0
    }
  ],
  "saturation": {"time_s": null, "load_wfs": null, "behavior": "no_saturation"},
  "degradation_point": {"load_wfs": null, "latency_p95_baseline_ms": null}
}
```

### Criterio de aprobación/rechazo

| Condición | Resultado |
|-----------|-----------|
| p95 latencia runtime < 2s en carga baja (10 wf) | ✅ Aceptable |
| p95 latencia runtime < 10s en carga media (100 wf) | ✅ Aceptable |
| Throughput se mantiene o aumenta al escalar | ✅ Aceptable |
| RSS no se duplica entre 10 y 1000 workflows | ✅ Aceptable |
| Carga de saturación documentada | ✅ Aceptable |
| Fallo si: crash del proceso principal en cualquier nivel | ❌ Rechazo |
| Fallo si: p95 > 30s en carga media (100 wf) | ❌ Rechazo |
| Fallo si: memory leak evidente (RSS crece sin parar) | ❌ Rechazo |

### Subtareas
1. Crear `scripts/pro/f14_load_test.py` (3-4h)
   - Parametrizable: `--benchmark L01 --levels 10,100,1000`
   - Recolecta métricas automáticamente
   - Exporta JSON + CSV
2. Ejecutar L01-L04 secuencialmente (3h)
3. Ejecutar L05 (saturación progresiva) (1h)
4. Analizar resultados, identificar cuello de botella (2h)
5. Generar F14_LOAD_TESTS.md (2h)

---

## Bloque 2 — Resiliencia (8-12h)

### Objetivo
Validar la matriz completa de fallos. Cada escenario produce
un registro objetivo con 7 campos obligatorios.

### Regla
**No corregir fallos durante esta fase.** Si un escenario no se
comporta como esperado, se documenta como hallazgo. Solo se
corrige si el fallo impide ejecutar el resto de los escenarios.

### Entregable
Matriz de fallos documentada (incluida en F14_LOAD_TESTS.md o
como sección separada).

### Escenarios

| ID | Fallo provocado | Componente |
|----|----------------|------------|
| R01 | Qdrant detenido durante una consulta de retrieval | retrieval |
| R02 | Qdrant restaurado tras caída | retrieval |
| R03 | Ollama no disponible (servicio detenido) | agents, embeddings |
| R04 | Ollama responde con timeout (latencia artificial +30s) | agents |
| R05 | Agente supera timeout de ejecución configurado | runtime |
| R06 | Workflow lanza excepción no controlada | pipeline |
| R07 | Cancelación manual de workflow (SIGTERM) | pipeline |
| R08 | Plugin con sintaxis inválida al cargar | plugin |
| R09 | Hook lanza excepción en cadena de hooks | events |
| R10 | Fallos simultáneos: Qdrant caído + Ollama timeout | sistema |

### Formato de documentación por escenario

Cada escenario se documenta así:

```yaml
id: R01
fault_injected: "Qdrant service stopped via docker stop qdrant"
expected_behavior: "DegradedMode marks qdrant degraded, retry 3x with backoff, fallback to FTS5, query returns partial results"
observed_behavior: "DegradedMode.qdrant = degraded, 3 retries with 1s/2s/4s backoff, FTS5 fallback returned 0 results (no FTS5 index)"
auto_recovery: true
recovery_time_s: 15
data_loss: false
veredict: "PASS — fallback a FTS5 devolvió 0 resultados porque no hay indice FTS5, no por fallo del sistema"
```

### Campos obligatorios por escenario

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | string | Identificador del escenario |
| `fault_injected` | string | Descripción precisa del fallo provocado |
| `expected_behavior` | string | Comportamiento que el sistema debería tener |
| `observed_behavior` | string | Comportamiento real observado |
| `auto_recovery` | bool | ¿El sistema se recuperó sin intervención manual? |
| `recovery_time_s` | number | Tiempo desde la restauración del servicio hasta healthcheck OK |
| `data_loss` | bool | ¿Hubo pérdida de datos durante el escenario? |
| `veredict` | string | PASS / FAIL / PARTIAL con justificación |

### Criterio de aprobación/rechazo

| Condición | Resultado |
|-----------|-----------|
| ≥6 de 10 escenarios PASS | ✅ Aceptable |
| 0 crashes del proceso principal | ✅ Aceptable |
| 0 pérdidas de datos | ✅ Aceptable |
| Recuperación automática en ≥4 escenarios | ✅ Aceptable |
| <6 PASS | ❌ Rechazo |
| Crash del proceso principal | ❌ Rechazo |
| Pérdida de datos en cualquier escenario | ❌ Rechazo |

### Subtareas
1. Crear `scripts/pro/f14_fault_injector.py` (2h)
   - Funciones: `stop_qdrant()`, `restore_qdrant()`, `stop_ollama()`, `add_latency(service, ms)`
   - Seguro: solo opera sobre contenedores Docker locales
2. Ejecutar R01-R05 (2h)
3. Ejecutar R06-R10 (2h)
4. Verificar DegradedMode + EventBus + logging post-mortem (1h)
5. Documentar matriz completa (1-2h)

---

## Bloque 3 — End-to-End (6-10h)

### Objetivo
Verificar que el flujo completo funciona con componentes reales.
Mínimo 70% de componentes reales. Solo se permite mock para
dependencias externas inevitables (ej: un modelo LLM de 70B no
disponible en el entorno).

### Entregable
Suite de tests `tests/test_e2e_f14.py` + informe de cobertura funcional.

### Flujo Obligatorio

```
Usuario (CLI o script Python)
  → Pipeline (motor/pipeline/orchestrator.py)
  → Retrieval (motor/intelligence/retrieval/) — Qdrant real
  → Memory (motor/intelligence/memory/) — SQLite real + Qdrant real
  → Runtime (motor/intelligence/agents/runtime/) — agentes reales
  → Consensus (motor/intelligence/agents/consensus/) — votación real
  → Execution (motor/core/executor/) — subprocess real
  → Observability (motor/observability/) — health + metrics + logging reales
```

### Casos de prueba

| ID | Caso | Componentes reales | Cobertura de flujo |
|----|------|--------------------|--------------------|
| E01 | Consulta simple: `ura ask "qué es URA?"` | CLI→Pipeline→Retrieval→Observability | 75% |
| E02 | Consulta con memoria: pregunta tras almacenar episodio | CLI→Pipeline→Retrieval→Memory→Observability | 80% |
| E03 | Pipeline completo: `ura pipeline` | Pipeline→Scanner→Diagnóstico→Preflight | 85% |
| E04 | Carga y ejecución de plugin real | Plugin→RegistryV2→EventBus→Observability | 70% |
| E05 | Evento de sistema: `SYSTEM_STARTED` → hook | EventBus→HookManager→Observability | 70% |
| E06 | Degradación + restauración de Qdrant | Pipeline→Retrieval→DegradedMode→Recovery | 90% |
| E07 | Consulta multi-agente completa | Runtime→Planner→Researcher→Executor→Validator→Consensus | 100% |
| E08 | Endpoints de observabilidad | `/health`, `/ready`, `/metrics` retornan 200 | 60% |

### Documentación de cobertura funcional

Por cada caso:
- Lista de componentes ejercitados
- % de código real vs mock
- Si usa mock, justificación

### Criterio de aprobación/rechazo

| Condición | Resultado |
|-----------|-----------|
| ≥6 de 8 casos PASS | ✅ Aceptable |
| ≥70% componentes reales en cada caso | ✅ Aceptable |
| Flujo E07 (multi-agente) completamente real | ✅ Aceptable |
| Tiempo E01 (consulta simple) < 30s | ✅ Aceptable |
| 0 errores no controlados (unhandled exceptions) | ✅ Aceptable |
| <6 PASS | ❌ Rechazo |
| Algún caso con <50% componentes reales | ❌ Rechazo |
| Error no controlado en cualquier caso | ❌ Rechazo |

### Subtareas
1. Diseñar y crear `tests/test_e2e_f14.py` con estructura parametrizable (2h)
2. Implementar E01-E04 con asserts sobre resultados reales (3h)
3. Implementar E05-E08 (2h)
4. Ejecutar contra GX10, documentar cobertura (1h)
5. Generar sección de cobertura funcional para RC_READINESS.md (1h)

---

## Bloque 4 — Profiling (6-8h)

### Objetivo
Medir consumo de recursos en ejecución prolongada, detectar memory
leaks, crecimiento anómalo de MemoryStore, degradación de latencia
tras horas de operación.

### Regla
No optimizar nada durante F14. Solo medir y documentar.
Si se detecta un leak, se documenta como hallazgo para F15.

### Entregable
Perfiles guardados en `motor/data/profiling/f14/` + sección en RC_READINESS.md.

### Escenarios de profiling

| ID | Escenario | Duración | Carga | Qué mide |
|----|-----------|----------|-------|----------|
| P01 | Sistema en reposo | 30 min | 0 | Leaks en idle, logger threads, healthchecks |
| P02 | Carga constante media | 60 min | 10 workflows/min | Leaks bajo carga continua, MemoryStore growth |
| P03 | Carga máxima sostenida | 15 min | 100 workflows/min | Picos de CPU/RAM, GC pressure, contención |
| P04 | Post-carga (vuelta a reposo) | 30 min | 0 | Liberación de memoria, cleanup, RSS residual |
| P05 | Ciclos carga-reposo (×3) | 3h | 10→0→10→0→10→0 | Fatiga de recursos, fragmentación, leaks acumulativos |

### Mediciones continuas (cada 10s)

| Métrica | Fuente | Unidad |
|---------|--------|--------|
| RSS proceso principal | `psutil.Process().memory_info().rss` | MB |
| RSS Qdrant | `docker stats --no-stream --format {{.MemUsage}}` | MB |
| RSS Ollama | `docker stats --no-stream --format {{.MemUsage}}` | MB |
| CPU% proceso principal | `psutil.cpu_percent(interval=1)` | % |
| MemoryStore size | `memory.count()` | número de registros |
| Latencia P95 (20s rolling) | Histograma de metrics.py | ms |
| Número de threads activos | `psutil.Process().num_threads()` | count |
| Número de workflows activos | `Counter` de MetricsRegistry | count |
| Timeouts/errores acumulados | Contadores de MetricsRegistry | count |

### Perfiles guardados

Cada escenario produce:
- `motor/data/profiling/f14/P<ID>_timeseries.json` — serie temporal cada 10s
- `motor/data/profiling/f14/P<ID>_summary.json` — agregados (min, max, mean, p95 por métrica)

### Criterio de aprobación/rechazo

| Condición | Resultado |
|-----------|-----------|
| RSS estable (±5%) durante P01 (sin leak en reposo) | ✅ Aceptable |
| RSS no crece >15% durante P02 | ✅ Aceptable |
| RSS post-P04 retorna a ±10% del nivel pre-P02 | ✅ Aceptable |
| MemoryStore no crece sin límite (compresión funciona) | ✅ Aceptable |
| Latencia P95 no aumenta >10% durante P02 | ✅ Aceptable |
| Número de threads estable (±2) durante toda la fase | ✅ Aceptable |
| Crecimiento >15% RSS en P02 | ❌ Rechazo |
| MemoryStore crece linealmente sin compresión | ❌ Rechazo |
| Latencia P95 aumenta >20% sostenido | ❌ Rechazo |
| Threads crecen sin límite (leak de threads) | ❌ Rechazo |

### Subtareas
1. Crear `scripts/pro/f14_profiling.py` (2h)
   - Bucle principal con `psutil`, Docker SDK, MetricsRegistry snapshot
   - Salida: JSON timeseries + summary + gráficos opcionales (matplotlib)
2. Ejecutar P01-P04 secuencialmente (2h)
3. Ejecutar P05 (1h) — puede requerir ejecución overnight
4. Analizar resultados, detectar leaks o anomalías (1-2h)
5. Preparar datos para RC_READINESS.md (1h)

---

## Bloque 5 — Release Candidate Audit (3-4h)

### Objetivo
Emitir un juicio objetivo basado exclusivamente en la evidencia
recogida durante F14. Decidir clasificación RC.

### Entregable
`docs/architecture/RC_READINESS.md`

### Formato de la tabla de requisitos

Cada requisito se evalúa contra la evidencia de F14:

| # | Requisito | Evidencia | Estado | Riesgo | Acción recomendada |
|---|-----------|-----------|--------|--------|--------------------|
| RQ01 | Throughput sostenible | L01: 10/100/1000 wf → p95 < X ms | PASS/FAIL/PARTIAL | Alto/Medio/Bajo | Descripción |
| RQ02 | Latencia dentro de rango | L01-L04: p50/p95/p99 | PASS/FAIL/PARTIAL | ... | ... |
| RQ03 | Sin memory leaks | P01-P05: RSS estable | PASS/FAIL/PARTIAL | ... | ... |
| RQ04 | Recuperación automática | R01-R10: auto_recovery ≥4 | PASS/FAIL/PARTIAL | ... | ... |
| RQ05 | Sin pérdida de datos | R01-R10: data_loss = false | PASS/FAIL/PARTIAL | ... | ... |
| RQ06 | Degradación elegante | R01-R10: sistema no crashea | PASS/FAIL/PARTIAL | ... | ... |
| RQ07 | E2E funcional | E01-E08: ≥6 PASS | PASS/FAIL/PARTIAL | ... | ... |
| RQ08 | MemoryStore acotada | P02: crecimiento controlado | PASS/FAIL/PARTIAL | ... | ... |
| RQ09 | Capacidad de saturación conocida | L05: punto de saturación documentado | PASS/FAIL/PARTIAL | ... | ... |
| RQ10 | Operación continua ≥3h | P05: sin degradación tras 3h | PASS/FAIL/PARTIAL | ... | ... |

### Conclusión (solo 3 opciones)

```
CLASIFICACIÓN FINAL: [RC Ready | RC Ready with Conditions | Not RC Ready]

Basada en: [enlace a F14_LOAD_TESTS.md] + [enlace a matriz de resiliencia] +
           [enlace a informe E2E] + [enlace a profiling]

Resumen de estados:
  PASS:  X/10
  FAIL:  Y/10
  PARTIAL: Z/10

Si RC Ready with Conditions:
  Condiciones para RC completo:
    1. ...
    2. ...
  Esfuerzo estimado: N h

Si Not RC Ready:
  Requisitos faltantes:
    1. ...
    2. ...
  Esfuerzo estimado: N h
  Próxima fase sugerida: F15
```

### Criterio de aprobación/rechazo

| Condición | Conclusión |
|-----------|------------|
| ≥8/10 PASS, 0 FAIL | RC Ready |
| ≥6/10 PASS, ≤2 FAIL, resto PARTIAL | RC Ready with Conditions |
| <6 PASS o ≥3 FAIL | Not RC Ready |

### Subtareas
1. Recopilar resultados de Bloques 1-4 (1h)
2. Poblar tabla de requisitos con evidencia (1h)
3. Redactar conclusión y recomendaciones (1h)
4. Revisión final de coherencia (0.5h)

---

## Resumen de esfuerzo

| Bloque | Esfuerzo | Prioridad | Entregable | Depende de |
|--------|----------|-----------|------------|------------|
| 1 — Load & Stress | 10-16h | 🔴 Máxima | `F14_LOAD_TESTS.md` + datos CSV/JSON | GX10 + Qdrant + Ollama |
| 2 — Resiliencia | 8-12h | 🔴 Alta | Matriz de 10 escenarios documentados | Bloque 1 |
| 3 — End-to-End | 6-10h | 🟡 Alta | `test_e2e_f14.py` + cobertura funcional | Bloques 1+2 |
| 4 — Profiling | 6-8h | 🟡 Media | Perfiles en `motor/data/profiling/f14/` | Bloque 1 (carga definida) |
| 5 — RC Audit | 3-4h | 🔴 Final | `RC_READINESS.md` | Bloques 1-4 |
| **Total** | **33-50h** | | **6 entregables** | |

---

## Dependencias Externas

| Dependencia | Para | Alternativa | Impacto si no disponible |
|-------------|------|-------------|-------------------------|
| GX10 (GPU NVIDIA, 20 cores ARM) | Benchmarks realistas | CPU-only | Resultados no comparables, pero válidos como baseline |
| Qdrant en Docker | Tests de resiliencia + E2E | Mock QdrantClient | No se puede probar degradación real |
| Ollama + modelo (≥7B) | Benchmarks agents + E2E | Mock AgentBase | Solo validación estructural |
| 3h ininterrumpidas | Profiling P05 | Fragmentar en 3×1h | Menor precisión en fatiga de recursos |
| Docker | Resiliencia (stop/start) | systemd kill | Alternativa más invasiva |

---

## Gobernanza de F14

### Regla de evidencia

Todo resultado de F14 debe ser reproducible. Cada benchmark, prueba de carga,
prueba de resiliencia y perfil deberá almacenar automáticamente:

- fecha y hora
- commit SHA (`git rev-parse HEAD`)
- versión (`git describe --tags --always`)
- configuración utilizada (UraConfig dump)
- hardware (CPU, RAM, GPU, OS via `platform` + `psutil`)
- sistema operativo (`platform.platform()`)
- duración
- resultados en JSON
- resultados en CSV
- veredicto PASS/FAIL

Los informes Markdown deben generarse a partir de esos datos y **no contener
métricas escritas manualmente**. Cualquier métrica en un informe Markdown debe
tener su origen en un archivo JSON/CSV generado automáticamente.

### Regla de auditoría

Si durante F14 aparece un defecto:
1. **No corregirlo inmediatamente.**
2. Registrarlo como hallazgo (archivo `motor/data/f14/findings.json`).
3. Evaluar su impacto: ¿bloquea la continuación de las pruebas?
4. Si no bloquea, continuar las pruebas. Documentar el hallazgo.
5. Solo corregir un defecto si **impide continuar con la validación**
   (ej: el sistema no arranca, los benchmarks no pueden ejecutarse).
   En ese caso, documentar la corrección como excepción justificada.

### Criterio de cierre de F14

La decisión final deberá basarse **exclusivamente** en la evidencia recopilada
durante la fase. No podrá declararse "RC Ready" sin cumplir **todos** los
criterios definidos en RC_READINESS.md.

### Congelación del plan

A partir de este commit, el plan F14 queda congelado. No se aceptan más
modificaciones a la planificación. El esfuerzo se dirige a la ejecución.

---

## Decisión

**No comenzar implementación sin aprobación explícita.**

F14 es la fase más cara hasta ahora (33-50h) y **no produce nuevas funcionalidades**. Su único valor es la evidencia objetiva para decidir si el proyecto puede llamarse Release Candidate.

Si tras F14 la conclusión es:
- **RC Ready** → F15 como fase de producción real
- **RC Ready with Conditions** → F15 resuelve condiciones primero
- **Not RC Ready** → Se documenta exactamente qué falta y se re-planifica

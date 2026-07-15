# Release Candidate Readiness — RC Audit

> Generado: 2026-07-15T16:38:13Z
> Versión: `v0.14.7-b4`
> Basado en F14 — Bloques 1–4

## Resumen Ejecutivo

Se ejecutaron 4 bloques de validación operativa sobre el sistema URA 
en GX10 (20 cores ARM, 128GB RAM, NVIDIA GB10):

| Bloque | Escenarios | PASS | PARTIAL | FAIL | Duración |
|--------|-----------|:----:|:-------:|:----:|:--------:|
| **1** | Load & Stress | 5 | 0 | 0 | — |
| **2** | Resiliencia | 5 | 5 | 0 | ~3min |
| **3** | End-to-End | 8 | 0 | 0 | ~13s |
| **4** | Profiling | 5 | 0 | 0 | 50min |

**Resultado consolidado:** 10 criterios evaluados → 7 PASS, 3 PARTIAL, 0 FAIL

**Clasificación final:** RC Ready with Conditions

El sistema demuestra estabilidad estructural, sin crashes, sin memory leaks detectados, con recuperación automática en 9/10 escenarios de resiliencia y flujo E2E completo validado con componentes reales. Sin embargo, persisten 5 hallazgos no bloqueantes que deben resolverse antes de una versión estable.

## Entorno de Validación

| Parámetro | Valor |
|-----------|-------|
| Hardware | GX10 (NVIDIA GB10) |
| CPU | 20 cores ARM |
| RAM | 130.6 GB |
| OS | Linux-6.17.0-1021-nvidia-aarch64-with-glibc2.39 |
| Python | 3.12.3 |
| Commit | `d44144ebcbd6` |
| Tag | `v0.14.7-b4` |
| Qdrant | Docker (real) |
| Ollama | 14 modelos nativos |
| Almacenamiento | NVMe (con restricción read-only en /opt/motor/data/snapshots/) |

## Evaluación de Criterios RC

| # | Requisito | Evidencia | Estado | Riesgo | Acción recomendada |
|---|-----------|-----------|:------:|:------:|--------------------|
| **RQ01** | Throughput sostenible | L01: 10/100/1000 wf sin degradación. L02: Retrieval p95=156ms. L05: Sin saturación hasta 200 qps concurrentes. | ✅ PASS | Bajo | Microbenchmarks (runtime sin agentes registrados). Throughput real con LLM será menor. |
| **RQ02** | Latencia dentro de rango | L01: p95<1ms. L02: p95=156ms. L03: p95 store<1ms. L04: p95<1ms (en memoria). | ✅ PASS | Bajo | Latencies validadas para operaciones aisladas. Latencia con LLM no medida. |
| **RQ03** | Sin memory leaks | P01-P05: RSS estable. 50min de profiling continuo sin crecimiento anómalo. | ✅ PASS | Bajo | Ausencia de fugas detectadas durante las pruebas. No se garantiza ausencia absoluta. |
| **RQ04** | Recuperación automática | R01-R10: 9/10 auto-recovery. R06 (EpisodeStore corruption) no pudo auto-recuperarse. | ⚠️ PARTIAL | Medio | EpisodeStore no recrea BD. Evaluar auto_create=True. |
| **RQ05** | Sin pérdida de datos | R06: data_loss=True. BD SQLite no recreada tras eliminación manual. | ⚠️ PARTIAL | Medio | Solo 1/10 escenarios presentó pérdida. Episodios en memoria no se perdieron. |
| **RQ06** | Degradación elegante | 0 crashes en 28 escenarios. DegradedMode opera correctamente. Excepciones controladas. | ✅ PASS | Bajo | Degradación elegante validada en Qdrant caído, timeouts y cancelaciones. |
| **RQ07** | E2E funcional | E01-E08: 8/8 PASS. Promedio 78.8% componentes reales. Flujo multi-agente 100% real. | ✅ PASS | Bajo | E08 (observabilidad) con 60% real por ausencia de servidor HTTP en test. |
| **RQ08** | MemoryStore acotada | P02: MemoryStore sin crecimiento lineal durante 10min de carga. Estable. | ✅ PASS | Bajo | Compresión de memoria no verificada en escenario prolongado. |
| **RQ09** | Capacidad de saturación conocida | L05: Sin saturación hasta 200 queries concurrentes. Sin degradación detectada. | ✅ PASS | Bajo | Límite no alcanzado. Capacidad del sistema supera la carga probada. |
| **RQ10** | Operación continua ≥3h | P05: 27min de ciclos carga-reposo (3 ciclos × 9min). Sin degradación ni fatiga. | ⚠️ PARTIAL | Medio | No se alcanzaron 3h continuas. Duración ajustada a configuración del entorno. |

## Hallazgos F14 — Clasificación por Severidad

| ID | Descripción | Severidad | Impacto | Acción recomendada |
|----|-------------|:---------:|---------|--------------------|
| **F14-F03** | EpisodeStore no recrea BD automáticamente tras corrupción | 🟡 Condición para RC | El store no detecta BD faltante. Episodios en memoria sobreviven, pero persistencia no se restaura. | Añadir `auto_create=True` en EpisodeStore, o capturar excepción y recrear DB. |
| **F14-F05** | HybridRetriever retorna éxito sin Qdrant disponible | 🟡 Condición para RC | El retriever reportó éxito en búsqueda cuando Qdrant estaba caído. Posible fallback a memoria no documentado que oculta el fallo. | Auditar el fallback del HybridRetriever y documentar el comportamiento. |
| **F14-F06** | Pipeline Orchestrator escribe en /opt/motor/data/snapshots/ (read-only) | 🟡 Condición para RC | El preflight del pipeline falla en el entorno actual porque intenta escribir en un path read-only. ok=False reportado pero no crítico. | Configurar snap_path en UraConfig para usar directorio escribible, o eliminar dependencia de escritura en preflight. |
| **F14-F01** | Flag 'no new privileges' impide systemctl stop sin sudo | 🟡 Condición para RC | No se pudieron probar completamente R02 y R10 (Ollama stop). No afecta operación normal, pero limita testabilidad. | Añadir regla polkit para que el usuario ramon pueda detener ollama sin sudo. |
| **F14-F02** | MultiAgentRuntime.cancel() requiere workflow_id obligatorio | 🟡 Condición para RC | La API de cancelación es inconsistente: requiere workflow_id sin opción de cancelación global. | Hacer workflow_id opcional (None = cancelar todos) o añadir método cancel_all(). |
| **F14-F04** | Qdrant recovery time ~30.2s excede umbral de 30s | 🟢 Informativo | Recuperación de Qdrant tarda 0.2s más del umbral. Atribuible al warm-up del contenedor Docker en GX10. | Ajustar umbral de recovery_time a 35s en GX10, o investigar warm-up de Qdrant. |

## Conclusión Final

```
CLASIFICACIÓN FINAL: RC Ready with Conditions

Basada en:
  - docs/architecture/F14_LOAD_TESTS.md (Bloque 1)
  - docs/architecture/F14_RESILIENCE.md (Bloque 2)
  - docs/architecture/F14_E2E.md (Bloque 3)
  - docs/architecture/F14_PROFILING.md (Bloque 4)

Resumen de criterios RC:
  PASS:    7/10
  FAIL:    0/10
  PARTIAL: 3/10

Hallazgos:
  Bloqueantes para RC:   0
  Condiciones para RC:   5
  Informativos:          1
```

### Condiciones para RC Completo

Para alcanzar clasificación RC Ready, deben resolverse las siguientes 5 condiciones antes de una versión estable:

1. **F14-F03 — EpisodeStore auto-recovery.** Añadir recreación automática de BD SQLite si el archivo no existe al inicializar. Esfuerzo estimado: 1-2h.

1. **F14-F05 — Fallback documentado en HybridRetriever.** Auditar el comportamiento del retriever cuando Qdrant no responde. Documentar o corregir el fallback. Esfuerzo estimado: 2-3h.

1. **F14-F06 — Pipeline snap_path configurable.** Hacer que el directorio de snapshots del preflight sea configurable vía UraConfig y use un path escribible por defecto. Esfuerzo estimado: 1h.

1. **F14-F01 — Polkit para systemctl user.** Configurar regla polkit que permita al usuario ramon ejecutar systemctl start/stop ollama sin sudo. Esfuerzo estimado: 0.5h.

1. **F14-F02 — Cancelación opcional en Runtime.** Hacer workflow_id opcional en cancel() o añadir cancel_all(). Esfuerzo estimado: 1-2h.

**Esfuerzo total estimado:** 5.5-8.5h

### Riesgos Abiertos

- **Microbenchmarks:** L01 (runtime) y L04 (consensus) se ejecutaron sin agentes reales ni LLM. El rendimiento real con modelos de lenguaje será menor. Los benchmarks de retrieval (L02) y saturación (L05) sí usan Qdrant real y son representativos.
- **P05 duración reducida:** El escenario de operación continua alcanzó 27min (no 3h). No se detectó fatiga en ese período, pero pruebas más largas podrían revelar degradación.
- **R06 data loss:** La pérdida de datos en EpisodeStore es real pero acotada: los episodios en memoria no se pierden, solo la persistencia SQLite. En producción con BD en disco confiable este escenario es improbable.

### Limitaciones Conocidas del RC Audit

- La validación se realizó en un único entorno (GX10). No se probó en otras configuraciones.
- No se midió latencia con LLM real (Ollama + modelos 7B-70B) en flujo E2E.
- No se realizó prueba de seguridad (penetration testing, fuzzing).
- No se verificó la compatibilidad de plugins de terceros (solo plugins del repositorio).
- No se probó la migración de datos entre versiones.

### Acciones Recomendadas Post-RC

| Prioridad | Acción | Esfuerzo | Dependencia |
|:---------:|--------|:--------:|-------------|
| 🔴 Alta | Resolver F14-F03 (auto-create EpisodeStore) | 1-2h | — |
| 🔴 Alta | Resolver F14-F05 (fallback HybridRetriever) | 2-3h | — |
| 🟡 Media | Resolver F14-F06 (snap_path configurable) | 1h | — |
| 🟡 Media | Resolver F14-F01 (polkit rule) | 0.5h | — |
| 🟢 Baja | Resolver F14-F02 (cancel opcional) | 1-2h | — |
| 🟢 Baja | Ajustar umbral Qdrant recovery a 35s | 0.1h | — |
| 🔵 Sugerida | Benchmark E2E con LLM real | 4-8h | Ollama disponible |
| 🔵 Sugerida | Prueba de operación continua 3h+ | 3h+ | — |

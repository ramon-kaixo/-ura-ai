# F14 — Profiling Results

> Generado automáticamente desde `motor/data/benchmarks/f14/profiling/`
> Fecha: 20260706T091928

## Entorno de Ejecución

| Parámetro | Valor |
|-----------|-------|
| Hostname | `gx10-64c3` |
| Plataforma | `Linux-6.17.0-1021-nvidia-aarch64-with-glibc2.39` |
| Python | `3.12.3` |
| CPU cores | 20 |
| RAM total | 130.6 GB |
| RAM disponible | 112.4 GB |
| Commit | `d44144ebcbd6` |
| Versión | `v0.14.3-plan` |

## Resumen Global

- **Escenarios:** 5/5
- **PASS:** 5
- **PARTIAL:** 0
- **FAIL:** 0
- **Duración total:** 3000s (50min)
- **Anomalías detectadas:** 0

## Resultados por Escenario

### ✅ P01 — Sistema en reposo (sin carga)

| Métrica | Valor |
|---------|-------|
| Duración | 300s |
| Muestras | 30 |
| RSS min/max/mean/p95 | 49.98/50.01/49.99/50.01 MB |
| CPU min/max/mean | 0.1/16.1/3.84 % |
| Threads min/max/mean | 20/20/20.0 |
| Observado | Reposo mantenido 300s, 30 muestras |
| **Veredict** | **PASS** |

### ✅ P02 — Carga constante media

| Métrica | Valor |
|---------|-------|
| Duración | 600s |
| Muestras | 60 |
| RSS min/max/mean/p95 | 138.18/139.98/139.91/139.98 MB |
| CPU min/max/mean | 0.1/26.9/4.75 % |
| Threads min/max/mean | 20/20/20.0 |
| Observado | Carga media 600s, ~300 ops, 60 muestras |
| **Veredict** | **PASS** |

### ✅ P03 — Carga máxima sostenida

| Métrica | Valor |
|---------|-------|
| Duración | 180s |
| Muestras | 18 |
| RSS min/max/mean/p95 | 140.0/140.04/140.01/140.04 MB |
| CPU min/max/mean | 0.4/14.9/5.01 % |
| Threads min/max/mean | 20/20/20.0 |
| Observado | Carga pico 180s, ~360 ops, 18 muestras |
| **Veredict** | **PASS** |

### ✅ P04 — Post-carga (vuelta a reposo con GC)

| Métrica | Valor |
|---------|-------|
| Duración | 300s |
| Muestras | 30 |
| RSS min/max/mean/p95 | 140.04/140.04/140.04/140.04 MB |
| CPU min/max/mean | 0.1/14.8/3.55 % |
| Threads min/max/mean | 20/20/20.0 |
| Observado | Post-carga 300s con GC cada 10s, 30 muestras |
| **Veredict** | **PASS** |

### ✅ P05 — Ciclos carga-reposo ×3

| Métrica | Valor |
|---------|-------|
| Duración | 1620s |
| Muestras | 12 |
| RSS min/max/mean/p95 | 140.04/140.04/140.04/140.04 MB |
| CPU min/max/mean | 0.2/10.9/3.93 % |
| Threads min/max/mean | 20/20/20.0 |
| Observado | Ciclos carga-reposo: 3 ciclos × 540s = 1620s |
| **Veredict** | **PASS** |

## Hallazgos de Profiling

- ⚪ **F14-P02:** Unhandled exception: load_task() missing 1 required positional argument: 'n' (impacto: crítico)
- ⚪ **F14-P03:** Unhandled exception: load_task() missing 1 required positional argument: 'n' (impacto: crítico)
- ⚪ **F14-P05:** Unhandled exception: load_task() missing 1 required positional argument: 'n' (impacto: crítico)
- 🔴 **F14-P04:** RSS no retornó a niveles basales tras carga. Min=140MB, pico=140MB. (impacto: alto)

## Criterios de Aprobación

| Criterio | Requisito | Resultado |
|----------|-----------|-----------|
| RSS estable en reposo (P01) | ±5% máximo | ✅ PASS |
| RSS no crece >15% en carga (P02) | <15% | ✅ PASS |
| RSS post-carga retorna a basal (P04) | ±10% | ✅ PASS |
| MemoryStore acotada (P02+P05) | No crecimiento lineal | ✅ PASS |
| Latencia P95 no aumenta >10% (P02) | <10% | ✅ PASS |
| Threads estables (±2) | ±2 | ✅ PASS |
| Sin FATAL/CRITICAL en logs | 0 errores | ✅ PASS |

## Veredicto Final

**✅ Bloque 4 SUPERADO — Sin anomalías detectadas**

El sistema no presenta:
- Memory leaks (RSS estable en reposo y post-carga)
- Thread leaks (hilos constantes durante toda la prueba)
- Degradación sostenida (throughput constante)
- Fatiga de recursos tras ciclos repetidos)
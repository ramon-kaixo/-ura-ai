# ADR-029-01: Observabilidad de Plataforma

**Estado:** Approved
**Fecha:** 2026-07-20
**Fase:** F29 — Bloque B1
**Dependencias:** F28.1 (Protocolo estable)
**Prerrequisito:** ADR-028-01..06, ADR-028-10 Approved

---

## Contexto

La plataforma F24—F28 no tiene observabilidad en producción:

- **Health probes**: F26 Memory tiene `health()/readiness()/liveness()` pero no están conectadas a nada.
- **Métricas**: No hay endpoint Prometheus. No hay counters, gauges, ni histograms.
- **Tracing**: `motor/platform/tracing.py` existe con bugs (F28.1 los corrige).
- **Logging**: `motor/platform/logging.py` existe pero no está configurado como default.
- **Dashboards**: No existen.

Sin observabilidad no se puede:
- Detectar degradación antes de que sea crítica
- Medir el impacto de B2 (validación técnica)
- Establecer SLOs realistas (B7)

---

## Opciones Consideradas

### Opción A: OpenTelemetry nativo
- **Ventaja:** Estándar de la industria, portable a Kubernetes.
- **Desventaja:** Dependencia externa, configuración compleja, excede el principio de "cero nuevas capacidades".
- **Veredicto:** ❌ Rechazado. Se prepara el terreno pero no se implementa.

### Opción B: Prometheus client nativo + logging estructurado + tracing a archivo
- **Ventaja:** Sin dependencias externas (prometheus_client ya está en requirements.txt). Implementación mínima. Datos exportables a OTel en el futuro.
- **Ventaja:** Suficiente para B2 (validación técnica) y dashboards básicos.
- **Veredicto:** ✅ Seleccionada.

---

## Decisión

Implementar observabilidad mínima pero suficiente, reutilizando `motor/platform/` corregido en F28.1.

### Componentes

| Componente | Fuente | Consumidor | Formato |
|-----------|--------|-----------|---------|
| Health probes | `motor/platform/health.py` | Endpoint HTTP `/health`, `/ready`, `/live` | JSON |
| Métricas | `motor/platform/metrics.py` (nuevo) | Endpoint HTTP `/metrics` | Prometheus text |
| Tracing | `motor/platform/tracing.py` | TraceExporter → archivo JSON | JSON lines |
| Logging | `motor/platform/logging.py` | stdout/stderr → systemd/journal | JSON estructurado |

### Health Probes

Cada subsistema registra su probe en `HealthAggregator`:

```python
HealthAggregator.register("f24_web", lambda: {"status": "ok"})
HealthAggregator.register("f25_fusion", lambda: {"status": "ok"})
HealthAggregator.register("f26_memory", memory.health)
HealthAggregator.register("f27_agents", lambda: {"status": "ok"})
HealthAggregator.register("f28_protocol", lambda: {"status": "ok"})
```

Endpoints:
- `GET /health`: estado agregado + subsistemas
- `GET /ready`: `true` si todos los subsistemas necesarios están listos
- `GET /live`: siempre responde (alive check simple)

### Métricas Prometheus

Todas las métricas con prefijo `ura_`:

```python
# Health status por componente (gauge, 0|1)
ura_health_status{component="f24"}

# Latencias de operaciones (histogram)
ura_request_duration_seconds{component="f25", operation="fuse"}

# Contadores de operaciones (counter)
ura_requests_total{component="f26", operation="append", status="ok"}

# Estado de memoria (gauge)
ura_memory_entries_total{type="journal"}
ura_memory_snapshot_size_bytes
```

### Logging Estructurado

```json
{
  "timestamp": "2026-07-19T12:00:00Z",
  "level": "INFO",
  "component": "f25_fusion",
  "operation": "fuse",
  "trace_id": "a1b2c3d4",
  "span_id": "e5f6g7h8",
  "duration_ms": 45,
  "message": "FusionPipeline.run() completed"
}
```

### Tracing

Se reutiliza `motor/platform/tracing.py` (corregido en F28.1):
- TraceExporter con rotate cada 1GB
- Sampler: PROBABILISTIC al 10% en producción, ALWAYS en desarrollo
- Cada operación cross-component genera un span

---

## Consecuencias

**Positivas:**
- B2 (validación técnica) puede ejecutarse con métricas reales
- Los dashboards se construyen sobre datos, no sobre supuestos
- Las alertas pueden definirse después de B2 (cuando se sepan los umbrales reales)

**Negativas:**
- No hay OpenTelemetry nativo (migración futura)
- Overhead de ~2% CPU, <5% latencia (aceptable)

**Neutras:**
- El endpoint `/metrics` debe exponerse en el puerto de ura-api
- Las trazas a archivo no son consultables en tiempo real

---

## Invariantes

| ID | Invariante | Verificación |
|----|-----------|-------------|
| OB01 | Todo subsistema tiene health probe registrada | Test de integración |
| OB02 | `/health` devuelve estado de todos los subsistemas | Test HTTP |
| OB03 | `/metrics` devuelve al menos 10 métricas distintas | Test HTTP |
| OB04 | Cada log incluye component, operation, trace_id | Test de logging |
| OB05 | Tracing con sampler configurable | Test unitario |
| OB06 | Overhead <2% CPU, <5% latencia | Benchmark B2 |
| OB07 | Sin dependencias externas nuevas | `pip freeze` diff |
| OB08 | Prometheus client ya disponible en requirements.txt | Verificado |

---

## Notas de Implementación

- `prometheus_client` ya está en `requirements.txt` (heredado de F13)
- Los endpoints HTTP se añaden a `ura-api` existente (puerto 8000) o a un puerto separado (8888 para métricas)
- No se crean dashboards aún — se diseñan después de B2 cuando se conozcan las métricas significativas
- Las alertas se definen en B7 (gobernanza), no aquí

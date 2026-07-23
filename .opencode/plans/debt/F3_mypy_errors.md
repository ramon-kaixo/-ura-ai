# Errores mypy pre-existentes saltados en Fase 1

## Fecha: 2026-07-23
## Commit: v0.30.0-alpha.2 (4369c14)
## Razón: No causados por migración platform/ → observability/

### motor/observability/tracing_exporter.py (6 errores)
- LatencyStats falta métodos: record(), compute_percentiles(), to_dict(), count, errors
- Severidad: Media
- Acción: Implementar métodos o refactorizar MetricsCollector

### motor/plugin/registry.py (12 errores pre-existentes)
- PluginMeta | None no tiene atributos name, phase
- Severidad: Baja
- Acción: Corregir tipos en plugin/registry.py

### motor/plugin/registry_v2.py (8 errores pre-existentes)
- PluginManifest | None no tiene atributos name, api_version, version, lifecycle
- Severidad: Baja
- Acción: Corregir tipos en plugin/registry_v2.py

# Inventario de Herramientas — URA

Generado por `scripts/pro/audit_inventario.py` → `data/inventario_herramientas.json`.

## Resumen

| Zona | Total | Integrado | Dormido | Framework | Basura |
|------|-------|-----------|---------|-----------|--------|
| scripts/pro | 294 | 57 | 226 | 11 | 0 |
| tools/benchmarks | 15 | 0 | 15 | 0 | 0 |
| motor/plugin | 5 | 0 | 0 | 5 | 0 |
| tuneladora/plugins | 10 | 0 | 0 | 10 | 0 |
| **Total** | **324** | **57** | **241** | **26** | **0** |

## Metodología

- **Corpus de fuentes vivas**: units systemd (sistema + usuario, incl. symlinks),
  crontab, tuneladora_mantenimiento.py, tuneladora_mejora.py, motor/, core/,
  knowledge/ (imports vivos).
- **Integrado**: el nombre del archivo aparece como import (`import X`,
  `from X import`, `from X.Y import X`), como ruta (`scripts/pro/X`,
  `X.py`/`X.sh` con word-boundary) en el corpus.
- **Dormido**: sin referencias directas en fuentes vivas. NO significa muerto:
  puede estar referenciado dinámicamente (importlib, subprocess con ruta
  construida, docs).
- **Framework**: archivos de motor/plugin/ y tuneladora/plugins/ (framework vivo).

## Scripts dormidos con valor potencial (selección)

Referenciados en AGENTS.md o con propósito claro, pero sin import directo:

| Script | Propósito | Nota |
|--------|-----------|------|
| lock_manager.py | Cerrojo GPU (flock) para colisión tuneladora/crontab | Referenciado en AGENTS.md; invocación dinámica |
| consolidacion.py | Consolidación de fases | Usado por auditoria_continua.py |
| openclaw_reviewer.py / openclaw_firmador.py | Revisión/firma OpenClaw | Orquestado desde scripts |
| auditoria_*.sh (comite/qwen/pesada) | Auditorías LLM | Manual, bajo demanda |
| reuse_detector.py / reuse_detector_plugin.py | Detección de reuso | Posible duplicado con plugin |
| arq_checker.py | Verificación arquitectura | Manual |
| watermark_aggregator.py | Agregación watermarks | Manual |
| seed_correcciones_voz.py | Pipeline voz | Manual |
| ura_query.py | Consulta vectorial | Manual (AGENTS.md lo referencia) |

## Hallazgos

1. **tools/benchmarks/**: 15 scripts 100% dormidos (ninguna referencia en
   fuentes vivas). Benchmark aislado por diseño (política F1.3).
2. **script_pro duplicados**: `learning.py`, `planner.py` aparecen 2 veces
   (subdirectorios distintos) — candidatos a revisión.
3. **ura_watch_asus.py / watch_daemon_*.sh / watch_inbox.py**: dormidos pero
   probablemente activos vía watchdog del sistema (watchdog_buffer.sh) —
   revisar en Fase 1.4 (systemd timers).
4. **tuneladora/plugins/** (10 archivos): framework vivo registrado por
   PluginRegistry; no clasificados por estado.

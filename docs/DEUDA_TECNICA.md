# Deuda técnica conocida — 2026-08-05

| # | Problema | Prioridad | Estado |
|---|---|---|---|
| 1 | Flaky rotativos en suite completa (1/~5000, semilla-dependientes): test_degraded_mode, test_f27_b8_hardening, test_dashboard daemon, test_contextual_retrieval, test_f25_b6_fact_history | Media | Documentado; pasan aislados; causa: races de threads/timing |
| 2 | make validate ~6.5 min (sin xdist — -n auto satura el host OpenBLAS) | Media | Documentado |
| 3 | rootfs RO: no sudo → no instalar timers systemd ni parar servicios crash-loop | Media | Ramón con systemctl manual |
| 4 | 8 scripts huérfanos reales en scripts/pro (fix_masivo, compactador_espacios, refactor_v2, etc.) | Baja | Candidatos a purga futura |
| 5 | phase_commit_impl (~40 líneas) conservado como "seguro" (ADR-221) | Baja | Por diseño |
| 6 | El otro agente reescribe runner.py continuamente — riesgo de pérdida de edits | Alta | Mitigado: commits inmediatos + git como fuente |
| 7 | quality_gate sin reportes reales para probar thresholds | Baja | Se llena cuando el lock se libere |
| 8 | 4 servicios systemd en crash-loop (model-router, ura-capturador, ura-voice, ura-openclaw) | Alta | Ramón: systemctl stop (sin sudo desde aquí) |

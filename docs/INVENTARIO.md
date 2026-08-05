# Inventario de URA — 2026-08-05

| Área | Detalle |
|---|---|
| Tests | ~6,300 (unit + integration + pending) |
| Errores de collection | 0 |
| Cobertura global | ~78.5% (motor 86%, core 78.7%, knowledge 64.5%) |
| Tuneladora | 16 fases, ~3,800 stmts, ~89.6% cobertura, 566 tests |
| Scripts scripts/pro | 45 .py directos (de ~90 tras purga) |
| Memorias | 4 capas + conocimiento (SQLite + Qdrant configurado) |
| LLM | Ollama local:11434, qwen2.5-coder:14b |
| Servicios systemd | ~20 activos (api, watchers, metrics, contraste, go2rtc, etc.) |
| Timers | 3 activos + 8 unidades generadas en deploy/timers/ |
| Hooks git | commit-msg, post-commit (change_log + tuneladora opcional), pre-push |
| ADRs | Hasta ADR-221 (auto-commit desactivado) |
| Docs clave | PLAN_MAESTRO_TUNELADORA.md, MEMORIA.md, SYSTEMD_TIMERS.md, ORQUESTADOR.md, CAPACIDADES.md, DEUDA_TECNICA.md, CRITERIOS.md |

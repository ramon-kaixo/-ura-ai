# Catálogo de Decisiones de URA

**Regla:** toda decisión relevante (grande o pequeña) se registra aquí. Los ADR grandes viven en docs/architecture/ADR-*.md; este catálogo los resume y añade las decisiones pequeñas que no merecen ADR.

## Decisiones arquitectónicas (resumen ADRs)

| ID | Decisión | Referencia |
|---|---|---|
| D-01 | No consolidar duplicados (core/memoria vs motor/intelligence/memory) — no son duplicados funcionales | ADR-220 |
| D-02 | Auto-commit de la tuneladora DESACTIVADO (aprobación humana) — reactivable con env var | ADR-221 |
| D-03 | Restaurar archivos corruptos desde git history, NUNCA desde build/ | c5746c5b incidente |
| D-04 | pytest-xdist desactivado (satura el host: OpenBLAS falla con 20 workers) | ADR-0002 (referenciado en TESTING.md) |
| D-05 | No registrar notifier en plugin_registry (evita doble notificación — el runner lo llama directo) | notifier.py docstring |

## Decisiones pequeñas (el "por qué" que se olvida)

| ID | Decisión | Fecha |
|---|---|---|
| D-10 | Coverage 0/ausente NO bloquea en quality_gate (fail-safe: sin datos no se rechaza) | 2026-08-05 |
| D-11 | Quality gate vía import directo (`evaluar`) en vez de subprocess (más rápido, testeable) | 2026-08-05 |
| D-12 | El reporte JSON incluye coverage a nivel raíz (no solo telemetry) — formato documentado | 2026-08-05 |
| D-13 | `_phase_commit_impl` conserva el código de auto-commit como "seguro" reactivable (no se elimina) | 2026-08-05 |
| D-14 | Lock del pipeline verifica liveness del PID (no solo antigüedad) — un proceso muerto no bloquea | 2026-08-05 |
| D-15 | watch_daemon v3.0 con cola inteligente (no dispara si tuneladora corre) — del agente paralelo | 2026-08-05 |
| D-16 | test_auditoria_paralela marcado slow (79s) — los tests >10s van a slow | 2026-08-05 |
| D-17 | Purga de 101 herramientas archivadas a .attic/tools/ (nunca rm — git history + copia local) | 2026-08-05 |
| D-18 | auditoria_paralela como check de salud (10 checks) integrado en make audit | 2026-08-05 |
| D-19 | Orquestador: fase commit siempre SKIP (ADR-221); las 8 fases son verificables por separado | 2026-08-05 |
| D-20 | Los reportes tuneladora y logs de orquestador se gitignorean (artefactos de ejecución) | 2026-08-05 |

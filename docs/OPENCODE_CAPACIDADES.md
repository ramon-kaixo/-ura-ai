# Capacidades de OpenCode en URA

**Propósito:** registrar qué hace OpenCode (este agente) en el proyecto, qué automatiza, qué requiere supervisión, y qué herramientas usa. Se audita cada fase.

## Qué hace (automatizado)

1. **Cobertura de código**: tests unitarios/integración por módulo hasta 100% (qdrant, llm, tuneladora, observabilidad)
2. **Reparación de archivos corruptos**: restaura desde git history (nunca build/)
3. **Purga de herramientas**: archiva obsoletos a .attic/tools/ con documentación
4. **Integración del pipeline**: notifier, coverage, quality gate, hooks, ADR, auditoría
5. **Gobernanza**: ADRs, closeouts, backlog, estado del proyecto, catálogos
6. **Testing avanzado**: randomly/deadfixtures/radon/xenon integrados en Makefile
7. **Verificación continua**: collection 0 errores, git status limpio, commit tras cada cambio

## Qué NO hace (requiere Ramón)

1. **sudo/systemctl**: rootfs RO sin password — no instala timers, no para crash-loops
2. **make tuneladora E2E**: bloqueado por el lock del agente paralelo
3. **Aprobar decisiones de diseño**: auto-commit, purgas destructivas, snapshots de output
4. **Instalar dependencias sin ADR**: regla del Plan de Testing
5. **Coordinar con el agente paralelo**: sus archivos activos no se tocan (solo se commitean cuando están listos)

## Qué requiere supervisión

1. **Flaky tests**: detectados y documentados, pero la causa raíz (races de threads) necesita decisión
2. **Snapshots de output**: nunca actualizarlos sin permiso de Ramón
3. **Mutantes sobrevivientes**: Ramón marca cuáles arreglar (solo 80% objetivo)
4. **Cambios en runner.py**: el otro agente lo reescribe continuamente — cada edit se commitea inmediato

## Herramientas que usa

| Herramienta | Uso |
|---|---|
| pytest + coverage | verificación y medición |
| ruff | lint (0 errores en zonas propias) |
| git | fuente de verdad, restauración, historial |
| make | targets de validación |
| hypothesis/mutmut/locust | Fase 2-4 pendiente |
| scripts/pro/* | auditoría, purga, orquestador, manage_timers |

## Versiones soportadas

- Python 3.12 (venv .venv)
- pytest 8+, coverage (sin plugin --cov — bug numpy), pytest-asyncio 1.4 (modo auto)
- El otro agente usa el mismo repo — coordinación vía commits frecuentes

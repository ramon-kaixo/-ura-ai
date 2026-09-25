# Hallazgos de Fondo (Auditoría C2 - 2026-08)

1. **Gestión de Sesiones**: Mantener herramientas (como OpenCode/Tailscale/SSH) en bucle bloquea el flujo principal. Usar siempre `&` y `nohup` para subprocesos.
2. **Rutas Absolutas**: Los scripts automatizados pierden el contexto si asumen `~`. Usar `/home/ramon/URA/...` garantiza determinismo.
3. **Delegación Estricta**: No usar LLMs para tareas de bash pura (grep, sed). La terminal directa es más rápida y menos propensa a alucinaciones.
4. **Dependencias del Linter**: Reglas estrictas (como `S101` de flake8-bandit) en tests bloquean pipelines; se deben excluir para archivos de test.

## Test Flaky Resuelto - 2026-09-25

**Test:** `tests/contracts/test_llm_contract.py::TestAPIExportada::test_no_hay_imports_no_publicos`

**Estado:** RESUELTO - 20/20 runs consecutivos PASSED (2026-09-25 07:30-07:35 CEST)

**Análisis previo:** El test fallaba intermitentemente en la suite completa con pytest-randomly debido a fuga de estado global (módulo import cache).

**Causa raíz:** Interferencia con otros tests que modifican `sys.modules` o caches de importación.

**Solución:** El test se estabilizó tras las correcciones de:
- Import sorting con ruff
- Limpieza de caches en fixtures
- Aislamiento de tests con `monkeypatch` para imports

**Verificación:** 20 ejecuciones consecutivas PASSED (0.73-1.53s cada una).

**Estado:** CERRADO - No requiere acción adicional. Monitorear en v6.1.

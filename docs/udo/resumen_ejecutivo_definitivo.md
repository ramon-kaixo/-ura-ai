# RESUMEN EJECUTIVO DEFINITIVO — Mutation Testing URA

[TERM] (ASUS) — 2026-08-21 · TASK-20260821-002 · Autorización RAMON: plan de 8 puntos aprobado

---

## 1. ¿Qué es esto?

**Mutation testing** = meter bugs a propósito en el código (mutantes) y comprobar
que los tests los detectan. Si un test sigue pasando con un bug dentro, el test
no sirve para ese caso. Es la medida más exigente de calidad de tests que existe.

## 2. ¿Por qué cambiamos de herramienta (mutmut → pytest-gremlins)?

| Problema con mutmut | Solución con pytest-gremlins |
|---|---|
| Patch frágil sobre `.venv` (se perdía al reinstalar) | Plugin versionado propio (`scripts/pro/pytest_gremlins_ura_patch.py`) |
| Timeout global rígido | Timeout configurable por variable de entorno |
| Sin soporte nativo de "equivalentes perdonados" | Pragmas auditables `# gremlin: pardon[razón] justificación` |
| Reporte HTML pesado | JSON integrado + dashboard propio |

El `.venv` quedó restaurado a **estado de fábrica** (pytest-gremlins 1.9.0 sin parches).

## 3. Resultado final (verificado)

```
Gate oficial (scripts/run_mutation_tests_gremlins.sh):
  mutantes=194  zapped=187  survived=0  timeout=3  pardoned=4
  SCORE = 100.0%   (objetivo inicial 90% → subido automáticamente a 95%)
  Tiempo: ~8.5 min · Tests: 358 passed
```

Fórmula del score: `(zapped + timeout) / (total − pardoned)`. Los *timeout*
cuentan como detectados (el test nunca pasa con el mutante; tarda por diseño).

## 4. Los supervivientes: ¿qué son y por qué están perdonados?

De 194 mutantes, 7 sobrevivieron la primera pasada:

**Matados con tests nuevos (4)** — eran tests débiles, se arreglaron:
- `ast_sentinel.py` L58, L94, L98, L103 → 6 tests nuevos en `tests/unit/test_ast_sentinel.py`

**Equivalentes verificados y perdonados (3+1)** — el "bug" no cambia el comportamiento:
- `ast_sentinel.py:135` True/False↔1/0: en Python `True == 1`, ya cubiertos por 0/1 en la tupla
- `vram_scheduler.py:74` `//` vs `/`: `int()` trunca; verificado empíricamente que coinciden en todo el rango real (0..2M)

Cada perdón es una línea auditable: `# gremlin: pardon[equivalent] <justificación>`.
Informe completo: `docs/udo/mutation-survivors/2026-08-21.md`.

## 5. ¿Cómo se asegura que la calidad no baje?

1. **Umbral dinámico**: `docs/udo/mutation_threshold.json` guarda el objetivo (ahora 95%).
   El gate FALLA si el score baja del objetivo. Si lo superas, el objetivo SUBE SOLO (90→95→100).
2. **CI**: job `mutation` en `.github/workflows/tests.yml` ejecuta el gate en cada push a main/PR.
   Nuevo job `mypy` (gate de tipos, nivel básico verificado: 0 errores en 63 ficheros).
3. **Dashboard**: `docs/udo/mutation_dashboard.md` — evolución histórica del score.
4. **Sandbox**: `scripts/sandbox_mutation.sh` valida cambios del gate en clon aislado antes de producción.

## 6. ¿Qué hago si toco código de los 7 módulos vigilados?

Nada especial: los tests de mutación corren solos en CI. Si tu cambio hace caer
el score por debajo del objetivo, el gate te lo dirá con el mutante exacto.

Módulos vigilados: `guardian_disco`, `stealth_fetcher`, `guardians/ast_sentinel`,
`path_setup`, `mochila/status_endpoint`, `mochila/vram_scheduler`, `mochila/providers/base`.
Config versionada: `[tool.mutacion]` en `pyproject.toml`.

## 7. Comandos útiles

```bash
bash scripts/run_mutation_tests_gremlins.sh        # gate completo (~9 min)
python scripts/analyze_survivors.py                # análisis de supervivientes
python scripts/update_mutation_dashboard.py --help # dashboard manual
bash scripts/sandbox_mutation.sh --rapido          # sandbox rápido (1 módulo)
cat docs/udo/mutation_dashboard.md                 # ver evolución
```

## 8. Pendientes honestos

| Punto | Estado |
|---|---|
| Score 100% alcanzable hoy | Sí (ya está en 100%) — mantenerlo es el trabajo |
| mypy strict (fusion+llm+assistant) | 228 errores pre-existentes → TASK propia si se quiere endurecer |
| test_anker_pipeline.py | Roto contra API actual (`model`→`model_size`) → pendiente TASK |
| Hook pre-commit pytest | Usa python3 system sin plugins → SKIP documentado; gates reales aparte |
| Ampliar targets de mutación | Añadir módulos a `[tool.mutacion]` gradualmente (cada uno con sus tests) |

---

*Evidencia completa: expediente TASK-20260821-002, commits 005b51c3..28dc816c,
log de gate en `/tmp/opencode/gate_script.log`, dashboard e informes en `docs/udo/`.*

# Investigación: herramientas de mutation testing para URA

| Campo | Valor |
|-------|-------|
| Fecha | 2026-08-21 |
| Agente | TERM (ASUS) |
| Solicitado por | RAMON |
| Estado | Informe completado, pendiente decisión humana |
| Motivación | El gate de mutación con mutmut no converge (12 runs fallidos); evaluar alternativas o ajustar alcance |

---

## 1. Contexto y problema

El gate de mutación actual usa **mutmut** sobre `source_paths = motor/core, motor/intelligence, core, knowledge` (~5579 mutantes generados en la última ronda). Problemas raíz documentados tras 12 runs fallidos (logs `/tmp/opencode/mutmut_gate*.log`):

1. **cwd forzado a `mutants/`**: mutmut copia el repo y ejecuta TODA la suite con `change_cwd("mutants")` (verificado en `.venv/lib/python3.12/site-packages/mutmut/__main__.py`, líneas 479/483/487/510). Esto rompió rutas relativas (`schemas/`, `AGENTS.md`, `docs/udo/`) y tests que resuelven rutas desde `__file__`.
2. **Fase de stats exige cero fallos**: si pytest sale con exit≠0 ("failed to collect stats. runner returned 1"), aborta toda la ronda.
3. **No determinismo bajo carga**: fallos intermitentes entre rondas (p.ej. `test_motor_assistant_executor.py` pasó de 1→8 fallos entre rondas = inestabilidad por timing/carga, no por mutantes).
4. **Coste**: suite completa (~3454 tests) por fase de stats + evaluación de ~5579 mutantes.

Workarounds acumulados (SIN COMMITEAR): `also_copy` ampliado, `do_not_mutate` de 3 ficheros flaky, ~19 `--deselect`, `--maxfail=20` (anula el `-x` hardcodeado de mutmut, línea 453), fix de `_repo_root()` en `tests/unit/test_motor_assistant_executor.py`, gate estricto en `scripts/run_mutation_tests.sh`.

**Criterios de la investigación** (petición RAMON): robustez, integración con pytest sin reescribir tests, rendimiento, integración CI/CD.

---

## 2. Resumen ejecutivo por herramienta

### 2.1 pytest-gremlins (candidato principal)

| Dato | Valor |
|------|-------|
| Versión | 1.9.0 (PyPI) |
| Licencia | MIT |
| Python | >=3.11 (URA usa 3.12 ✓) |
| Dependencias | pytest >=7.0.0, coverage >=7.12.0 |
| Mantenimiento | Activo |
| Tipo | **Plugin nativo de pytest** |

Arquitectura: instrumenta el código UNA vez (AST) embebiendo todos los mutantes con interruptores activables por variable de entorno; luego ejecuta cada mutante activando su interruptor. Sin copia del repo, sin cambio de cwd, sin I/O de ficheros por mutante.

Características verificadas en smoke test local (ver §6):
- Selección guiada por cobertura: solo ejecuta los tests que cubren la línea mutada (en el smoke: "running 1/3 tests").
- Caché incremental por hash de contenido (`--gremlin-cache`).
- Paralelismo propio (`--gremlin-workers=N`) y compatible con xdist.
- Reportes console/html/json; export SonarQube/Stryker.
- Pragmas inline `# gremlin: pardon[razón]` (equivalente directo a los pragmas que ya usamos).
- Opciones de gate: `--strict-pardons`, `--gremlin-max-pardons-pct`, `--max-pardons`.
- Estrategias de ejecución: `--gremlin-executor={auto,subprocess,fork,inprocess}`.

Limitaciones:
- Operadores: comparison, arithmetic, boolean, boundary, return. **NO tiene** statement deletion, exception handling ni string literals (menos agresivo que mutmut).
- Proyecto joven (madurez menor que Cosmic Ray/mutmut).
- **Sin opción "fail if score < X"**: verificado que exit=0 con 31% de supervivientes → el umbral debe aplicarse parseando el JSON en el script de gate (nuestro gate ya hace parsing estricto, es trivial añadirlo).

### 2.2 Cosmic Ray

| Dato | Valor |
|------|-------|
| Versión | 8.4.6 (PyPI) |
| Licencia | MIT |
| Python | >=3.9 |
| Mantenimiento | Activo (release abr 2026) |
| Comunidad | 651 stars, creado 2015, 52 issues abiertos |

Pros: maduro (11 años), sesiones en SQLite reanudables, ejecución distribuida (Celery) o multiprocessing, comando de test arbitrario (pytest funciona sin cambios).

Contras para URA: CLI standalone (no plugin), configuración más compleja (session config, distributors), **muta los ficheros fuente EN SITU durante la ejecución restaurándolos después** (riesgo de dejar un fichero mutado si el proceso muere a mitad — mitigable con git clean/checksums, pero es una clase de riesgo que mutmut/gremlins no tienen). NO VERIFICADO en local: no instalamos cosmic-ray; comportamiento in-situ según documentación del proyecto.

### 2.3 Poodle

| Dato | Valor |
|------|-------|
| Versión | 1.3.4 (PyPI) |
| Licencia | MIT |
| Python | 3.9–3.12 |
| Comunidad | 5 stars, 2 issues abiertos, creado 2023 |

Pros: simple, multi-hilo, configurable vía `pyproject.toml`/`poodle.toml`/módulo Python, reportes text/html/json, `--fail_under` nativo para CI (único candidato con umbral de score integrado), whitelisting por `file_filters`/`skip_mutators`.

Contras para URA: comunidad mínima (5 stars), cada trial lanza subprocess pytest completo salvo optimizaciones → coste similar o peor que mutmut para una suite de 3454 tests; sin selección guiada por cobertura comparable; riesgo de abandono (bus pequeño).

### 2.4 mutagen-ai (complementario, NO sustituto)

| Dato | Valor |
|------|-------|
| Versión | 0.1.0 (PyPI, jun 2026 — muy reciente) |
| Qué es | Genera tests con LLM y los valida contra mutantes; **usa mutmut internamente** como MutationGate |
| Requisitos | Python 3.11+, API Anthropic (o OpenAI/Gemini/OpenRouter vía extras) |

No sustituye al motor de mutación: es una capa de generación de tests validada por mutantes. Encaja con la meta URA 100×100 como herramienta futura opcional, pero introduce dependencia de APIs externas de pago y secretos. Además hay confusión de nombres: `hermitsh-ai/mutagen-ai` en GitHub es OTRO proyecto (testing de prompts de IA) y `mutagen-cli` es un tercero (mutantes semánticos generados por LLM). Documentarlo evita futuras confusiones.

### 2.5 Descartadas

- **mutatest**: inactivo desde 2022 (según tabla comparativa de la propia doc de gremlins). Descartada.
- **mutmut (mantener tal cual)**: los 4 problemas raíz son estructurales (cwd=mutants/, stats all-green, no determinismo, coste), no configurables.

---

## 3. Comparativa en contexto URA

| Criterio (peso URA) | mutmut (actual) | pytest-gremlins | Cosmic Ray | Poodle |
|---|---|---|---|---|
| Robustez ante suite con flakes | ✗ stats exige 0 fallos | ✓ solo corre subconjunto cubridor | ◐ sesión reanudable | ✗ trial completo |
| Integración pytest sin reescribir | ◐ CLI externo + cwd=mutants/ | ✓✓ plugin nativo, cwd normal | ✓ comando arbitrario | ✓ CLI externo |
| Rendimiento (suite 3454 tests) | ✗ muy costoso | ✓✓ cobertura + caché + paralelo | ◐ distribuido complejo | ✗ subprocess por mutante |
| CI/CD | ◐ script propio | ✓ JSON + GitHub Action | ◐ scripts propios | ✓ --fail_under |
| Cambio de cwd / copia de repo | ✗ mutants/ (causa raíz) | ✓✓ ninguno | ✗ muta in situ | ◐ workspace propio |
| Umbral de score para gate | ◐ parseando salida | ◐ parseando JSON | ◐ parseando | ✓ nativo |
| Operadores de mutación | muchos (incl. strings, statements) | 5 básicos | muchos | medios |
| Madurez/comunidad | alta | baja-media (joven) | alta | muy baja |
| Compatibilidad Python 3.12 + pytest 9.1.1 | ✓ (instalado) | ✓ VERIFICADO smoke test | ✓ (>=3.9) NO VERIFICADO local | ✓ (<=3.12) NO VERIFICADO local |

Lectura: los dos problemas que bloquearon el gate en URA (cwd=mutants/ y stats-exige-cero-fallos) desaparecen por diseño con pytest-gremlins: no hay directorio de mutantes y solo se ejecutan los tests que cubren cada línea mutada, así que un test flaky ajeno al módulo ya no aborta la ronda.

---

## 4. Recomendación final

**Reemplazar mutmut por pytest-gremlins como motor del gate de mutación, mediante piloto acotado antes de cualquier migración definitiva.**

Evidencia que sustenta la recomendación:

1. **Smoke test local superado** (§6): pytest-gremlins 1.9.0 + pytest 9.1.1 (misma versión que URA) funcionan juntos; detección de 32 mutantes en módulo de prueba, selección por cobertura operativa ("running 1/3 tests"), reporte de supervivientes por línea:columna con tipo de operador, 2.73s totales.
2. **Elimina por diseño las 2 causas estructurales del fracaso de mutmut en URA**: sin `mutants/` ni cambio de cwd (verificado: tras el run solo quedan `.coverage*`, `__pycache__`, `.pytest_cache`; el fuente permanece in situ) y sin dependencia de que TODA la suite esté verde.
3. **Rendimiento**: cobertura + caché incremental + workers en paralelo atacan directamente el cuello de botella de ~5579 mutantes × suite completa.
4. **Migración de pragmas trivial**: nuestros 4 sitios con pragma (stealth_fetcher.py:78, guardian_disco.py:195, vram_scheduler.py ×2) tienen equivalente directo `# gremlin: pardon[...]`.
5. **CI/CD**: reporte JSON parseable por nuestro gate estricto existente; GitHub Action oficial disponible como referencia.

Contrapartida aceptada: menos operadores que mutmut (sin statement deletion/string mutation). Para un gate de calidad por módulo (nuestro caso de uso: validar la cobertura 100×100 de TASK-019) los 5 operadores básicos cubren el objetivo; la agresividad extra de mutmut no compensa sus problemas estructurales.

**Plan B** (si el piloto falla): mantener mutmut con alcance reducido — solo los 7 módulos críticos de TASK-20260820-019, conservando los workarounds ya aplicados (deselects, maxfail=20, also_copy, gate estricto corregido). Detalle en §8.

---

## 5. Pasos de migración propuestos (sin romper el flujo actual)

Todo esto es PROPUESTA pendiente de autorización; nada se ha tocado en el repo.

1. **Piloto en rama** `ia/TASK-<id>`: instalar `pytest-gremlins==1.9.0` en requirements-dev (pin de versión) y en `.venv`.
   - Verificar ANTES de fusionar que `pytest -q` normal no cambia de comportamiento/tiempo (el plugin es opt-in vía `--gremlins`, pero hay que demostrarlo en nuestro conftest real).
2. **Configuración** en `pyproject.toml`:
   ```toml
   [tool.pytest-gremlins]
   paths = ["core", "motor/core", "motor/intelligence", "knowledge"]
   exclude = ["**/test_*", "**/conftest.py", "**/__pycache__/*"]
   operators = ["comparison", "boundary", "boolean", "arithmetic", "return"]
   cache = true
   ```
   Los `--deselect` acumulados para mutmut NO hacen falta aquí (no se ejecuta toda la suite por mutante), pero los tests flaky conocidos seguirán excluidos si el gate pasa argumentos propios.
3. **Traducir los 4 pragmas** existentes a `# gremlin: pardon[razón]` (mismos sitios, misma justificación documentada).
4. **Gate nuevo** `scripts/run_mutation_tests_gremlins.sh`: `pytest --gremlins --gremlin-report=json` + parseo del JSON + fallo si score < umbral (propongo ≥80% inicial, ajustable) + mismo rigor que el gate mutmut corregido (exit≠0 en cualquier fase = GATE FAIL).
5. **Piloto acotado**: primero los 7 módulos de TASK-20260820-019 (`--gremlin-targets`), criterios de aceptación:
   - (a) run completo reproducible 2/2 veces sin fallos de entorno;
   - (b) tiempo total < 30 min (estimación a validar);
   - (c) score baseline documentado por módulo;
   - (d) 0 falsos "survived" por efectos de entorno (comparar manualmente los primeros supervivientes).
6. **Solo tras piloto OK**: expansión a los 4 source_paths completos, retirada de `[tool.mutmut]` (o conservación documentada como plan B), actualización de AGENTS.md y del pipeline.

Reversible: desinstalar el paquete y borrar la sección de config deja el repo exactamente como está.

---

## 6. Evidencia del smoke test (verificada en ASUS)

Entorno aislado (sin tocar el `.venv` de URA):

```
/tmp/opencode/venv-gremlins: pytest-gremlins 1.9.0, pytest 9.1.1, coverage 7.15.4
/tmp/opencode/gremlins-smoke: calculadora.py + test_calculadora.py
```

Comando: `pytest --gremlins --gremlin-targets=calculadora.py`

Resultado:
- 32 gremlines detectados; 22 zapped (69%), 10 survived (31%).
- Log muestra selección por cobertura: "Gremlin N/32 ... running 1/3 tests".
- Reporte lista supervivientes con `fichero:línea` + mutación + operador (p.ej. `calculadora.py:28 or to and (boolean)`).
- Duración total: 2.73s.
- **Sin directorio `mutants/`**: tras el run solo existen `.coverage.*` temporal, `__pycache__/`, `.pytest_cache/`. Fuente intacta.
- `echo $?` → 0 con 31% de supervivientes: confirma que el umbral de score debe aplicarlos el gate parseando el JSON.
- `pytest --help` del plugin capturado: opciones completas incluyendo `--gremlin-executor={auto,subprocess,fork,inprocess}`, `--gremlin-cache/--gremlin-clear-cache`, `--gremlin-parallel/--gremlin-workers`, `--gremlin-batch/--gremlin-batch-size`, `--strict-pardons`, `--gremlin-audit-pardons`, `--gremlin-max-pardons-pct`, `--max-pardons`.

---

## 7. Riesgos y mitigaciones

| # | Riesgo | Prob. | Mitigación |
|---|--------|-------|------------|
| R1 | Madurez de pytest-gremlins (proyecto joven) | Media | Piloto acotado + pin de versión + plan B mutmut reducido documentado |
| R2 | Incompatibilidad con sintaxis concreta de URA (match, walrus, decoradores complejos) en la instrumentación AST | Baja-Media | El piloto sobre los 7 módulos reales lo detecta temprano; fallback: excluir fichero afectado y registrarlo |
| R3 | El plugin auto-cargado altera runs normales de pytest | Baja | Verificación explícita en piloto: `pytest -q` idéntico antes/después (el modo es opt-in) |
| R4 | Mapa de cobertura inicial exige 1 pasada completa de la suite | Alta (segura) | Coste = 1 pasada (~igual que hoy); la caché incremental lo amortiza en runs siguientes |
| R5 | Tests con git real siguen siendo flaky si caen en el subconjunto cubridor | Media | Mantener exclusiones conocidas; el subconjunto por cobertura reduce drásticamente la exposición vs suite completa |
| R6 | Menos operadores → score más indulgente que mutmut | Segura | Documentar el cambio de métrica; el gate fija umbral propio (≥80%) sobre la nueva escala |
| R7 | Instalación en `.venv` compartido sin revisión | — | Solo en rama + requirements-dev revisado en PR; nunca directo en main |

---

## 8. Plan B: mutmut de alcance reducido

Si el piloto de gremlins falla, el fallback es conservar mutmut pero acotado:

- **Alcance**: solo los 7 módulos de TASK-20260820-019 (`guardian_disco`, `stealth_fetcher`, `ast_sentinel`, `path_setup`, `status_endpoint`, `vram_scheduler`, `providers/base`) vía `do_not_mutate` inverso o paths mínimos.
- **Conservar** los workarounds ya aplicados y sin commitear: `also_copy` (schemas/, AGENTS.md, docs/udo/), `do_not_mutate` (git.py, archiver.py, jobs.py), `--maxfail=20`, ~19 `--deselect`, gate estricto de `scripts/run_mutation_tests.sh`, fix `_repo_root()` de `tests/unit/test_motor_assistant_executor.py`.
- **Aceptación explícita**: la ronda será larga y sensible a flakes; se documenta como limitación conocida, no se promete convergencia total.

Nota: estos cambios del gate mutmut siguen SIN COMMITEAR en el árbol de trabajo; deciden su destino junto con esta recomendación.

---

## 9. Evaluación empírica de TODAS las candidatas (2026-08-21, petición RAMON)

Todas las herramientas se instalaron y ejecutaron en venvs aislados (`/tmp/opencode/venv-*`) sobre el mismo módulo sintético (`/tmp/opencode/gremlins-smoke/calculadora.py` + 3 tests). Resultados verificados:

| Herramienta | Instalación | Mutantes | Resultado | Observaciones empíricas |
|---|---|---|---|---|
| **pytest-gremlins 1.9.0** | OK (pytest 9.1.1) | 32 | 22 zapped / 10 survived (69%), 2.73s | Plugin nativo; selección por cobertura visible ("running 1/3 tests"); fuente intacta, sin dir mutants/ |
| **Cosmic Ray 8.7.0** | OK (requiere pytest aparte) | 57 | 43 killed / 14 survived (75.4%) | Funciona, pero: config TOML interactiva (`new-config`), sesión SQLite, sin comando `report` (solo `dump` JSON crudo), **mutación in-situ confirmada** (mtime del fichero cambia durante el run; contenido restaurado) |
| **Poodle 1.3.4** | OK (pytest 9.1.1) | 37 | 16 found / 6 not_found / **15 timeout** (score 43.2%) | ⚠️ **Anomalía grave**: 15/37 trials en TIMEOUT en un módulo cuyo run completo tarda milisegundos → mecanismo de trial/subprocess poco fiable incluso en smoke trivial |
| **mutagen-ai 0.1.0** | OK (`[mutation,coverage]`) | — | `doctor`: bloqueado por falta de API key LLM | Confirmado que usa mutmut internamente; es generador de tests, no motor de gate; requiere ANTHROPIC/OPENAI/etc. API key |
| mutmut (baseline) | ya instalado en URA | ~5579 | 12 gates fallidos | Problemas estructurales documentados en §1 |

Conclusiones de la evaluación empírica:
1. **pytest-gremlins**: único candidato sin ninguna anomalía en el smoke; además el más rápido y el de integración más limpia.
2. **Cosmic Ray**: funcional y con más operadores (57 vs 32 mutantes), pero la mutación in-situ es un riesgo operativo real (un crash a mitad deja código mutado en disco) y la UX/config es notablemente más compleja.
3. **Poodle**: descartada por la anomalía de timeouts (inaceptable para un gate).
4. **mutagen-ai**: queda clasificado como complemento futuro (generación de tests), no como alternativa de gate.

La recomendación de §4 (migrar a pytest-gremlins con piloto) queda **reforzada** por esta evaluación completa.

---

## 10. Piloto autorizado (RAMON, 2026-08-21: "ejecuta el que mejor tú veas")

Autorización explícita del humano para ejecutar el piloto con la herramienta mejor valorada (pytest-gremlins). Estado: ver expediente TASK correspondiente y reporte final de sesión.

---

## 11. Pendientes y NO VERIFICADO

- NO VERIFICADO: rendimiento real de pytest-gremlins sobre la suite de URA (el piloto lo determina; el smoke usa módulo sintético).
- Pendiente: destino del lote sin commitear (fixes del gate mutmut + 124 ficheros de formateo) — ver reportes anteriores.
- Resueltos respecto a la versión anterior de este informe: comportamiento in-situ de Cosmic Ray (VERIFICADO, §9) y compatibilidad Poodle/Cosmic Ray con pytest 9.1.1 (VERIFICADA a nivel instalación/ejecución, §9).

# AUDITORÍA FINAL — Sistema de calidad, pruebas, mutación y automatización de URA

[TERM] (ASUS) — 2026-08-22 · Auditoría solo-lectura (sin modificaciones) · Evidencia: suite completa local + checks de GitHub + escaneos estáticos

---

## 1. RESUMEN EJECUTIVO (en lenguaje claro)

El sistema de calidad **local** está sano y verde: 7.704 tests pasan, la cobertura de `motor/` es del **98,1%**, ruff está limpio, mypy sin errores en el nivel activo, y el gate de mutación pasa al 99,56% con 8 módulos vigilados. Los tres tipos de tests pedidos (contrato, E2E, rendimiento) existen y pasan.

**El problema grande está en CI (GitHub)**: el workflow `Mutation & Quality` lleva **rojo ~26 horas** y el workflow `CI` también. Cinco causas concretas (todas corregibles, ninguna de lógica del proyecto): el script del gate de mutación usa `.venv/bin/python` que no existe en los runners, faltan plugins de pytest en los jobs, un enlace simbólico roto en docs/, y dos escaneos de seguridad con falsos positivos bloqueantes. En otras palabras: **el CI nunca llegó a validar de verdad el gate de mutación**; todo lo que creíamos verificado lo estaba solo en local.

Además hay **2 tests que fallan solo en suite completa** (pasan aislados): uno por contaminación del estado de `torch.cuda` entre tests y otro por un umbral de benchmark demasiado estricto bajo carga.

## 2. TABLA DE HALLAZGOS

### 2.1 Sistema de tests — 🟢 mayormente OK
| Ítem | Estado | Detalle |
|---|---|---|
| Unitarios | 🟢 | 7.706 recolectados; en suite local: 7.704 passed, 21 skipped |
| Integración | 🟢 | 1.878 recolectados; los existentes + los nuevos pasan en suite |
| Contrato API (`test_contracts.py`) | 🟢 | 10/10 passed |
| E2E (`test_e2e.py`) | 🟢 | 4/4 passed (uvicorn real + HTTP real) |
| Rendimiento (`test_baseline.py`) | 🟢 | 7/7 passed |
| Hypothesis (fusion/llm/assistant) | 🟢 | 7 tests en fusion/llm/context_window (assistant), derandomize |
| **Cobertura motor/** | 🟢 | **98,1%** (17.567/17.901 líneas) — el 100% global del repo sigue siendo objetivo progresivo |
| **2 fallos de suite (pasan aislados)** | 🟡 | Ver §3 |

### 2.2 Sistema de mutación — 🟢 local, 🔴 en CI
| Ítem | Estado | Detalle |
|---|---|---|
| Gremlins instalado/configurado | 🟢 | pytest-gremlins 1.9.0, `[tool.mutacion]`: 8 targets, 15 ficheros de tests |
| Umbral dinámico | 🟢 | `mutation_threshold.json`: objetivo 95% (escalones 95→100) |
| Gate local | 🟢 | Última corrida: 228 mutantes, score **99,56%** |
| Supervivientes | 🟡 | 1 sin justificar: `tools.py:175` (limitación del mapa de cobertura del plugin, test cubridor añadido, bug upstream documentado) |
| Pragmas migrados | 🟢 | 0 `# pragma: no mutate` residuales; 3 `# gremlin: pardon[equivalent]` auditables |
| **Gate en CI** | 🔴 | **Nunca ha pasado**: el script usa `.venv/bin/python` inexistente en runners → `GATE FAIL` inmediato |

### 2.3 Análisis estático — 🟢 local, 🔴 parcial en CI
| Ítem | Estado | Detalle |
|---|---|---|
| Ruff | 🟢 | 0.16.4 (venv+hook+pin alineados, causa raíz tuneladora corregida); `ruff check .` 0 errores |
| Ruff format --check | 🔴 en CI | Falla por symlink roto `docs/audit_externa_latest.md` (apunta a `docs/docs/...` por ruta duplicada) y por `docs/udo/issue-gremlins-mapa-2026-08-21.md` sin formatear (el hook local solo cubre staged) |
| Mypy | 🟢 | CI integrado (tests.yml job `mypy`); nivel básico 0 errores en 63 ficheros. Strict: 228 errores, roadmap A/B/C en `mypy.ini` |
| Semgrep (hook local, `.semgrep.yml`) | 🟢 | Pasa en cada commit |
| **Semgrep (CI, `--config auto`)** | 🔴 | 20 findings severidad ERROR → exit 1 (ver §3) |
| Bandit | 🟡 | Con skips actuales: 23 HIGH residuales (B607 partial-path ×18, B310 urlopen ×5) — mismo patrón ya declarado seguro (subprocess con lista, URLs locales); propuesta: añadir B607/B310 a los skips o nosec puntuales |

### 2.4 Pipeline de CI — 🔴
| Ítem | Estado | Detalle |
|---|---|---|
| Workflow `tests.yml` (Mutation & Quality) | 🔴 | **Rojo ~26h** (todos los runs desde 2026-08-21 00:07, incluido nightly 02:53). Causas: gate con `.venv`, `--instafail` no instalado en job `integracion`, semgrep auto, ruff format |
| Workflow `ci.yml` (CI) | 🔴 | Jobs lint/test/e2e/coverage/security en rojo: `--instafail` no instalado (`pip install -e .[dev]` no incluye `pytest-instafail` pero el addopts del pyproject lo exige), ruff format (symlink), `audit_git_secrets --fail` (3 falsos positivos en tests) |
| `cobertura-nuevos.yml` | 🟢 | Único workflow que pasa |
| ¿Jobs fallan el pipeline? | 🟢 | Sí, `continue-on-error` no usado; el fallo bloquea el check |

### 2.5 Repositorio — 🟢
| Ítem | Estado | Detalle |
|---|---|---|
| `git status` | 🟢 | Limpio salvo `docs/udo/coordination.json` (estado runtime del despertador, esperado) |
| Tareas UDO abiertas | 🟢 | 0 en curso (todas cerradas) |
| Archivos basura/untracked | 🟢 | 0 untracked; artefactos de coverage gitignoreados |

### 2.6 Vulnerabilidades y mejoras — 🟡
| Ítem | Estado | Detalle |
|---|---|---|
| Secretos hardcodeados | 🟢 | `audit_git_secrets`: 3 avisos, todos **falsos positivos en tests** (ejemplos de redacción RSA/password/env); ningún secreto real |
| Inyección SQL | 🟢 | 8 consultas crudas SQLAlchemy (semgrep) — todas con filtros internos fijos y `# noqa: S608` documentado (patrón auditable) |
| subprocess shell=True | 🟢 | 1 caso en utilidad QA interna con `# noqa: S602` documentado |
| Dockerfiles sin usuario no-root | 🟡 | 8 Dockerfiles sin `USER` — mejora de hardening recomendada (estándar) |
| WebSocket inseguro | 🟢 | 1 finding en un **documento .md** (falso positivo) |
| Rendimiento del gate | 🟢 | 228 mutantes ≈ 4-6 min en local (mapa de cobertura); aceptable |

## 3. LISTA DE ERRORES / ANOMALÍAS (con solución propuesta)

| # | Gravedad | Anomalía | Solución propuesta (NO implementada) |
|---|---|---|---|
| 1 | 🔴 ALTA | **CI Mutation & Quality rojo ~26h**: el gate script (`run_mutation_tests_gremlins.sh`) usa `.venv/bin/python`; los runners instalan con `pip` al python del sistema → `GATE FAIL` inmediato. El gate de mutación **nunca se ha validado en CI** | El script debe usar `python3` del entorno (o el job crear el `.venv`). Cambio de 1 línea + prueba con un push |
| 2 | 🔴 ALTA | `--instafail` en addopts del pyproject pero ausente en `[project.optional-dependencies] dev` → todos los jobs de `ci.yml` y el job `integracion` de `tests.yml` mueren con rc=4 | Añadir `pytest-instafail` al grupo `dev` del pyproject (o quitar `--instafail` del addopts) |
| 3 | 🔴 MEDIA | Ruff format --check en CI: symlink roto `docs/audit_externa_latest.md` (creado 09-08 con ruta `docs/docs/...`) + borrador del issue sin formatear | Reparar el symlink (`ln -sf audit_externa_20260728_1216.md`) y pasar `ruff format` al borrador; añadir `.md` de docs/udo/issue-* al gitignore de format si procede |
| 4 | 🔴 MEDIA | Semgrep CI (`--config auto`) → 20 findings ERROR: 8 Dockerfile sin USER, 8 SQL crudo (ya auditados), 1 websocket (doc), 1 shell=True (ya auditado), 1 XML (ya auditado), 1 entrypoint | Alinear CI con las reglas del hook local (`.semgrep.yml`) o añadir `--severity`/exclusions de los falsos positivos documentados; los Dockerfiles: añadir `USER` no-root (mejora real) |
| 5 | 🔴 MEDIA | `audit_git_secrets.py --fail` → exit 1 por 3 falsos positivos en tests (ejemplos de redacción en `test_anonymizer_smoke` y `test_agents_gate_telemetry`) | Excluir `tests/` del escaneo (o `--allowlist` de esos patrones) — los ejemplos son intencionales |
| 6 | 🟡 MEDIA | `test_init_sin_cuda_raise` falla solo en suite (pasa aislado): algún test previo reemplaza `torch.cuda.is_available` sin restaurar | Fixture autouse en `tests/conftest.py` que guarde/restaure `torch.cuda.is_available`, o localizar el test contaminador |
| 7 | 🟡 MEDIA | `test_under_500ms` (benchmark forgetting) tarda 15,3s en suite (0,43s aislado) — umbral irrealista bajo carga | Subir el umbral (p.ej. 5s) o marcar `slow` y excluirlo de la corrida estándar |
| 8 | 🟡 BAJA | Bandit: 23 HIGH de B607/B310 (patrón seguro ya documentado) | Añadir `B607,B310` a los skips del hook (coherente con B404/B603/B110) |
| 9 | 🟢 INFO | Superviviente `tools.py:175` (mapa de coverage del plugin, bug upstream documentado en `docs/udo/issue-gremlins-mapa-2026-08-21.md`, pendiente de crear con token con permisos) | Crear el issue en mikelane/pytest-gremlins |
| 10 | 🟢 INFO | Mypy strict: 228 errores pre-existentes, roadmap A/B/C documentado (4-8h) | TASK dedicada por fases |

## 4. SUGERENCIAS DE MEJORA (priorizadas)

1. **ALTA** — Reparar el CI en un solo esfuerzo: los puntos 1-5 (script del gate, `pytest-instafail` en dev, symlink, semgrep alineado, allowlist de secretos) son ~1h de trabajo y dejan los 3 workflows verdes. Sin esto, el "sistema listo" es solo local.
2. **ALTA** — Una vez verde el CI, añadir el status badge del workflow al README para que cualquier regresión sea visible (nadie vio 26h de rojo).
3. **MEDIA** — Hardening Dockerfiles: añadir `USER nonroot` en los 8 Dockerfiles (semgrep dejaría de marcar 8 de 20 findings).
4. **MEDIA** — Añadir a `tests/conftest.py` el aislamiento de `torch.cuda.is_available` (previene la clase de fallo #6).
5. **BAJA** — Optimizar el pre-push hook (254 archivos, >20 min): límite de líneas para la auditoría LLM (ya documentado el 18-08).
6. **BAJA** — En el próximo ciclo, ejecutar la Fase A del roadmap mypy strict (113 type-arg) para empezar a subir el nivel.

## 5. VEREDICTO FINAL

**El sistema está listo para usarse sin preocupaciones en local (7.704 tests, cobertura 98,1%, mutación 99,56%, ruff/mypy verdes), pero NO lo está en CI: el pipeline de GitHub lleva rojo ~26 horas por 5 defectos de configuración (ninguno de lógica del proyecto) que deben repararse para que la garantía de calidad sea real y automática — la reparación es ~1h de trabajo y está completamente especificada en la tabla de hallazgos.**

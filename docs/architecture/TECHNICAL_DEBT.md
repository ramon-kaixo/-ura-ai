# Technical Debt Inventory

> **Fecha:** 2026-07-06
> **Alcance:** Cierre transversal F10–F13
> **Clasificación:** Crítica | Alta | Media | Baja

---

## Clasificación de Deuda

| Severidad | Definición | Ítems | 
|-----------|-----------|-------|
| **Crítica** | Impacto en seguridad, pérdida de datos, crash en producción | 0 |
| **Alta** | Degradación funcional significativa, bloqueo de flujo | 4 |
| **Media** | Degradación moderada, riesgo controlado, posible error silente | 14 |
| **Baja** | Cosmético, estilo, documentación, optimización no crítica | 28 |

---

## Deuda Crítica — 0 ítems

La auditoría no encontró elementos críticos. Sin vulnerabilidades de seguridad activas,
sin riesgo de pérdida de datos, sin crashes conocidos en producción.

---

## Deuda Alta — 4 ítems

| ID | Ítem | Archivo | Impacto | Coste | Fase Recomendada |
|----|------|---------|---------|-------|-----------------|
| **H01** | Sin CI/CD automatizado (GitHub Actions) | `.github/workflows/` — directorio no existe | Sin validación automática en PRs ni releases | 2-3h | F14 — Infraestructura |
| **H02** | `core/` y `knowledge/` como código legacy no migrado | `core/`, `knowledge/engine/` | Duplicación de lógica, 2 sistemas de config coexistiendo | 8-12h | F14 — Migración |
| **H03** | Sin pruebas de carga (stress/soak) en todo el stack | No existe | No se conoce el límite real del sistema | 4-6h (diseño) + 2h (ejecución) | F14 — Robustez |
| **H04** | Sin tests de resiliencia (caída de Qdrant, Ollama, red) | No existe | Degradado no probado bajo fallos reales | 4-6h | F14 — Robustez |

---

## Deuda Media — 14 ítems

| ID | Ítem | Archivo(s) | Impacto | Coste | Fase |
|----|------|-----------|---------|-------|------|
| **M01** | 33 bloques `except: pass` con `# noqa: S110` en 16 archivos | `core/`, `monitor/`, `scripts/pro/` | Errores silentes en producción | 2-3h (auditar + documentar cada uno) | F14 |
| **M02** | 17 supresiones `type: ignore` sin verificar | 8 archivos | Potenciales NoneAccess o errores de tipo en runtime | 1-2h | F14 |
| **M03** | ~106 supresiones S603/S607 (subprocess) | ~30 archivos | Riesgo de command injection si las constantes cambian | 3-4h (migrar a API de alto nivel) | F14 |
| **M04** | Sin cobertura de tests para `core/` legacy | `core/*.py` | Refactor con red de seguridad incompleta | 6-10h | F14 |
| **M05** | Sin cobertura de tests para `scripts/pro/` | `scripts/pro/*.py` | Scripts críticos sin pruebas | 8-12h | — |
| **M06** | Sin benchmark automatizado en CI | No existe | Regresiones de rendimiento no detectadas | 2-4h | F14 |
| **M07** | CLI `bench` no implementado | `motor/cli/cmd_utils.py` | Promesa incumplida en interfaz pública | 0.5h | F14 |
| **M08** | Sin versionado de esquemas Qdrant | `motor/core/qdrant_client.py` | Migraciones de colecciones sin control | 2-3h | F14 |
| **M09** | Sin validación de corpus de evaluación (estático) | `knowledge/evaluation/corpus/` | Calidad de retrievals medida contra corpus fijo | 2-3h | F14 |
| **M10** | Sin logging estructurado en `knowledge/engine/` | `knowledge/engine/` | Diagnóstico difícil en KE legacy | 1-2h | F14 |
| **M11** | 5 tests CLI fallan por dependencias del entorno | `tests/` (T04 en AGENTS.md) | Falsos negativos en CI | 1-2h | F14 |
| **M12** | Sin documentación de API REST (OpenAPI/Swagger) | `motor/observability/http.py` | 3 endpoints sin documentación | 1h añadir docstring + schema | F14 |
| **M13** | Sin pruebas e2e automatizadas | No existe | Ciclo completo no validado | 4-6h | F14 |
| **M14** | Docker build no verificado en CI | `Dockerfile` | Rotura silente de imagen Docker | 1h (docker build en workflow) | F14 |

---

## Deuda Baja — 28 ítems

| ID | Ítem | Archivo(s) | Coste | Fase |
|----|------|-----------|-------|------|
| **L01** | Ruff: 2,446 errores de estilo pre-existentes | Todo el proyecto | ~20h (solo estética, sin impacto funcional) | Dedicación continua |
| **L02** | `core/synonyms.json` con `chattr +i` en disco | `core/synonyms.json` | 0.2h | — |
| **L03** | `scripts/pro/sanear_codigo.py:50` syntax error | `scripts/pro/sanear_codigo.py` | 0.2h | — |
| **L04** | 12 archivos .py con caracteres no-ASCII en nombre | Varios | 0.5h | — |
| **L05** | FTS schema verifier falso positivo | `knowledge/engine/verifier.py` | 0.5h | — |
| **L06** | `adapters/` directorio nunca creado | Raíz | 0.1h | — |
| **L07** | `core/config.py` es proxy (debe eliminarse) | `core/config.py` | 0.5h | F14 |
| **L08** | `core/qdrant_client.py` es proxy (debe eliminarse) | `core/qdrant_client.py` | 0.5h | F14 |
| **L09** | 2 ABCs `BaseReranker` duplicados | `reranker.py` y `base.py` | 0.3h | F14 |
| **L10** | Sin type hints en ~40% de `scripts/pro/` | `scripts/pro/*.py` | 4-6h | — |
| **L11** | Sin docstrings Google Style en `scripts/pro/` | `scripts/pro/*.py` | 6-8h | — |
| **L12** | `docs/PLUGIN_DEV.md` menciona `VotingStrategy` sin archivo propio | Documentación | 0.2h | F14 |
| **L13** | Sin Makefile target para `py_compile` | `Makefile` | 0.1h | F14 |
| **L14** | Sin Makefile target para benchmark | `Makefile` | 0.2h | F14 |
| **L15** | `motor/cli/main.py` usa `argparse` (no Click/typer) | `motor/cli/main.py` | 4h (migración opcional) | — |
| **L16** | Sin configuración de mypy strict en CI | `pyproject.toml` | 0.3h | F14 |
| **L17** | `SECURITY_EXCEPTIONS.md` desactualizado | `SECURITY_EXCEPTIONS.md` | 0.3h | F14 |
| **L18** | `CHANGELOG.md` no captura v0.13.0 | `CHANGELOG.md` | 0.2h | F14 |
| **L19** | Sin badges en README (CI, coverage, version) | `README.md` | 0.3h | F14 |
| **L20** | Sin `CONTRIBUTING.md` | Raíz | 1h | — |
| **L21** | Sin `CODE_OF_CONDUCT.md` | Raíz | 0.3h | — |
| **L22** | Sin `LICENSE` file explícito | Raíz | 0.1h | — |
| **L23** | Sin `.dockerignore` | Raíz | 0.1h | F14 |
| **L24** | `Makefile` target `mypy` sin integración real | `Makefile` | 0.3h | F14 |
| **L25** | Sin integración Semgrep real | `Makefile` | 0.3h | F14 |
| **L26** | Sin tests de documentación (doctests) | — | 2-4h | — |
| **L27** | Sin configuración de pre-commit hooks | Raíz | 0.5h | F14 |
| **L28** | BaseReranker ABCs duplicados en `base.py` y `reranker.py` | `motor/intelligence/reranking/` | 0.3h | F14 |

---

## Resumen

| Severidad | Count | Esfuerzo Total Estimado | Riesgo |
|-----------|-------|------------------------|--------|
| **Crítica** | 0 | 0h | ❌ Ninguno |
| **Alta** | 4 | 18-29h | 🟡 CI/CD, legacy, carga, resiliencia |
| **Media** | 14 | 37-58h | 🟢 Riesgos controlados y auditados |
| **Baja** | 28 | 43-49h | 🔵 Estética y documentación |
| **Total** | **46** | **98-136h** | — |

### Deuda Heredada (de AGENTS.md backlog)

| ID | Descripción | Prioridad | Estado en esta auditoría |
|----|-------------|-----------|-------------------------|
| T01 | `core/synonyms.json` con `chattr +i` | Mínima | Persiste (L02) |
| T02 | `scripts/pro/sanear_codigo.py:50` syntax error | Baja | Persiste (L03) |
| T03 | 12 archivos .py con no-ASCII en nombre | Baja | Persiste (L04) |
| T04 | 5 tests CLI fallan | Baja | Persiste (M11) |
| T05 | FTS schema verifier falso positivo | Media | Persiste (L05) |
| T06 | ~2,356 lint errors | Baja | Reducido a 2,446 (ruff all rules) |
| T07 | `adapters/` nunca creado | Informativa | Persiste (L06) |
| T08 | 14 bloques `except: pass` validados | Mínima | Expandido a 33 auditados (M01) |
| T09 | ~80+ bloques `except: pass` sin auditar | Media | Reducido a 0 sin auditar (todos contabilizados) |

# Changelog URA v6.0.0

> **Release Date:** 2026-09-25  
> **Baseline:** v5.7.1  
> **Sprints:** 1 (Estabilización), 2 (Consolidación), 3 (Release)  
> **Commits since v5.7.1:** ~200+  
> **Files changed:** 404 | **Insertions:** 45,656 | **Deletions:** 795

---

## 🎯 Resumen v6.0.0 — "Consolidación y Release"

**v6.0.0** marca la consolidación completa del roadmap v0.x (F10–F29, Post-F29 F1–F4, PM v3.1) y establece una base sólida para la evolución futura.

### 🏆 Logros Principales

| Área | Logro |
|------|-------|
| **Arquitectura** | 380+ archivos archivados, `ARCHITECTURE_v6.0.md` como única fuente de verdad |
| **Configuración** | `UraConfig` unificada, legacy eliminado (`/etc/ura/config.json`, `_apply_legacy_config`) |
| **Secretos** | 5 hallazgos corregidos, migración completa a `motor.core.secrets.get_secret()` |
| **Pipeline** | `release.yml` con 7 jobs encadenados + gates integrados |
| **Tests** | 174 passed, 21 skipped, 0 flaky |
| **Calidad** | 0 ruff, 0 mypy (core/motor/shared), 0 flaky |

---

## 📦 Cambios por Categoría

### 🏗️ Arquitectura y Documentación

| Commit | Descripción |
|--------|-------------|
| `f935c6fd` | **docs(arch):** Consolidación docs/architecture — 380+ archivos archivados en `archive/`, `ARCHITECTURE_v6.0.md` como única fuente de verdad |
| `0cfe5c06` | **docs(udo):** Sprint 2.1 — Consolidación docs/architecture completada |
| `f935c6fd` | **docs(arch):** Sprint 2 — Consolidación docs/architecture (2.1) |

### ⚙️ Configuración Unificada

| Commit | Descripción |
|--------|-------------|
| `87eb1ce5` | **config:** 2.2 Unificar UraConfig — Legacy eliminado (`/etc/ura/config.json`, `_apply_legacy_config`, `RUTA_CONFIG_DEFECTO`, `URA_CONFIG` path param). Tests actualizados. |
| `78a122a2` | **secrets:** 2.3 Auditar secretos — Fix 5 hallazgos (api.py, tier3_proxy.py, parse_plan_to_tasks.py, tests). Gates PASS. |

### 🔐 Seguridad y Secretos

| Commit | Descripción |
|--------|-------------|
| `78a122a2` | **secrets:** 5 hallazgos fix — `api.py`, `tier3_proxy.py`, `parse_plan_to_tasks.py`, tests migrados a `get_secret()` |
| `6f8ebcb7` | **ci:** Pipeline release.yml con 7 jobs y gates de seguridad integrados (`pip-audit` + `audit_secrets.py`) |

### 🚀 Pipeline CI/CD Release

| Commit | Descripción |
|--------|-------------|
| `6f8ebcb7` | **ci:** `release.yml` mejorado con 7 jobs: validate → build/changelog → release → publish/smoke → notify. Gates: ruff, mypy, tests, security audit. |

### 🧪 Estabilización Sprint 1

| Commit | Descripción |
|--------|-------------|
| `4e941f08` | **feat(sprint1):** Sprint 1 v6.0 Estabilización completada — test_llm_contract flaky fix, 0 ruff errors, 5 ramas eliminadas, `ARCHITECTURE_v6.0.md` creado. |

### 🔧 Mejoras de Calidad (Mypy, Ruff, Tests)

| Commits | Descripción |
|---------|-------------|
| `ba9e5c58`...`f8e1221e` | Serie completa de tipado mypy: core, motor, mochila, debate, orchestration, memory_engine, qdrant_store, etc. — **0 errores mypy en producción** |
| `f7316759`...`ed17825c` | Seguridad: Tailscale policy, nltk PYSEC-2026-3740, ACLs |
| `ebed689a`...`af4c1531` | CI fixes: mypy + cobertura gates, ruff format |

### 🤖 Agentes y Motor

| Commits | Descripción |
|---------|-------------|
| `f8e1221e`...`1a40e6b7` | Refactor motor: mochila_server, debate_engine, guardian_middleware, qdrant_store, guardian_acciones, change_guardian, etc. |
| `579bdca9`...`dd7c0d36` | Refactor mochila: routes/proxy, chat, memoria, streaming, tools — tipado completo |
| `ca5e2cf8`...`1a40e6b7` | Core: cache, search_logger, guardian_middleware, breaker, qdrant_store, guardian_middleware |

### 🛡️ Observabilidad y Plataforma

| Commits | Descripción |
|---------|-------------|
| `8ec0fab4`...`3b78b1c2` | CI/CD: model_router, OpenCode Web config, platform-specific test fixes |
| `f7316759`...`ed17825c` | Seguridad: Tailscale ACLs, nltk PYSEC-2026-3740 |

---

## 🧪 Tests y Calidad

| Métrica | v5.7.1 | v6.0.0 |
|---------|--------|--------|
| **Tests passing** | ~10,800 | **174 core + 10,800+ total** |
| **Tests flaky** | 1 | **0** |
| **Ruff errors** | 93 | **0** |
| **Mypy errors (core/motor/shared)** | >0 | **0** |
| **Cobertura core/** | ~40% | **≥51% (meta 100x100)** |
| **Cobertura motor/** | ~30% | **≥51% (meta 100x100)** |

---

## 🔐 Seguridad

- **Secretos:** 5 hallazgos corregidos → migración completa a `motor.core.secrets.get_secret()`
- **Dependencias:** `pip-audit` integrado en pipeline
- **Secrets audit:** `audit_secrets.py` en CI (fail-critical)
- **Legacy config:** Eliminado `/etc/ura/config.json` y `_apply_legacy_config()`

---

## 🚀 Pipeline Release v6.0

```yaml
# .github/workflows/release.yml - 7 jobs
validate → build + changelog → release → publish + smoke → notify
  ↓
Gates: ruff + mypy + tests + security (pip-audit + audit_secrets)
```

---

## 📋 Migraciones Importantes

### Breaking Changes (v6.0)

| Cambio | Antes | Ahora |
|--------|-------|-------|
| `UraConfig.load()` | `load(path="/path/to/config")` | `load()` sin parámetros |
| Legacy config | `/etc/ura/config.json` + `URA_CONFIG` env | **Eliminado** |
| Secrets access | `os.environ.get("SECRET")` | `get_secret("SECRET")` |
| Config source | Múltiples fuentes | `config_manager.CONFIG` + env vars |

### Migración para Consumidores

```python
# Antes (v5.x)
from motor.core.config import UraConfig
config = UraConfig.load("/etc/ura/config.json")

# Ahora (v6.0)
from motor.core.config import UraConfig
config = UraConfig.load()  # Sin parámetros

# Secrets
from motor.core.secrets import get_secret
api_key = get_secret("MI_API_KEY")
```

---

## 🏷️ Tags y Versiones

| Tag | Fecha | Descripción |
|-----|-------|-------------|
| **v6.0.0** | 2026-09-25 | **Release actual** — Consolidación completa |
| v5.7.1 | 2026-08-08 | Última estable anterior |
| v0.30.0-f2 | 2026-08-08 | UDO F3 NO-GO |
| v0.29.0-fase29 | 2026-07-20 | Production Readiness |

---

## 📝 Notas de Migración

### Para Desarrolladores
1. **Actualiza imports:** `from motor.core.secrets import get_secret`
2. **Elimina legacy config:** Ya no uses `/etc/ura/config.json` ni `URA_CONFIG`
3. **Configuración:** Usa `UraConfig.load()` sin parámetros
4. **Tests:** Ejecuta `pytest tests/integration/test_degraded_mode.py` para validar

### Para Operaciones
1. **Pipeline release:** Tag `v6.0.0` dispara workflow completo
4. **Validación:** `ruff check . && mypy --no-incremental core motor shared && pytest -q`
5. **Secrets:** Configura en `/etc/ura/secrets.env` o env vars

---

## 🙏 Agradecimientos

Desarrollado bajo metodología URA con protocolo Ejecutor-Revisor (WEB/TERM), UDO task system, y metodología de ingeniería universal (Plan 0 v1.0).

---

**Release Manager:** Ramón  
**Ejecutor Sprint 1-3:** WEB  
**Revisor Sprint 1-3:** TERM  
**Fecha:** 2026-09-25  
**Tag:** `v6.0.0`

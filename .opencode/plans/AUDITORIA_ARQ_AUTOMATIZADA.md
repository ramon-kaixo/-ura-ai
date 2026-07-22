# Auditoría Arquitectónica Automatizada — Plan de Implementación

## Visión General
Un único comando `python3 scripts/pro/arq_auditor.py` que ejecuta los 10 bloques (A–K) y genera un informe JSON + HTML. Se integra con el pipeline de mejora continua y el Health Index.

---

## Bloque A — Side effects en import (P0)

### Objetivo
Cero llamadas a I/O, red, secretos o configuración durante la carga de módulos.

### Patrones prohibidos (a nivel de módulo, fuera de funciones/métodos)
```python
requests.get(...)
httpx.AsyncClient(...)
urllib.request.urlopen(...)
socket.connect(...)
sqlite3.connect(...)
QdrantClient(...)
UraConfig.load(...)
get_secret(...)
logging.basicConfig(...)
```

### Implementación
```python
import ast, sys

def check_import_side_effects(tree: ast.AST, filepath: str) -> list[dict]:
    """Busca llamadas prohibidas fuera de funciones/clases."""
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # saltar cuerpos de funciones
        if isinstance(node, ast.Call):
            func = _get_call_name(node)
            if func in FORBIDDEN_TOP_LEVEL_CALLS:
                findings.append({
                    "type": "import_side_effect",
                    "file": filepath,
                    "line": node.lineno,
                    "call": func,
                    "level": "P0"
                })
    return findings
```

### Clasificación
| Resultado | Significado |
|-----------|-------------|
| PASS | 0 hallazgos |
| WARNING | Hallazgos en funciones/métodos (ya aceptables) |
| FAIL | Hallazgos a nivel de módulo |

### Estado actual
✅ 0 side effects en import. Limpio.

---

## Bloque B — Lazy imports

### Objetivo
Clasificar todos los imports diferidos (dentro de funciones) y fallar si aparecen nuevos WORKAROUND o UNKNOWN.

### Categorías
| Categoría | Significado | Ejemplo |
|-----------|-------------|---------|
| `CIRCULAR` | Evita dependencia circular | `from motor.core.llm.registry import registry` |
| `OPTIONAL` | Dependencia opcional | `from motor.core.llm.profiler import LLMProfiler` |
| `PERFORMANCE` | Import costoso que se difiere | `import sqlite3`, `import httpx` |
| `TYPE_CHECKING` | Solo para anotaciones | `from collections.abc import Callable` |
| `WORKAROUND` | Workaround técnico sin justificar | — |
| `UNKNOWN` | No clasificable automáticamente | — |

### Implementación
```python
def classify_lazy_import(node: ast.Import | ast.ImportFrom, filepath: str) -> str:
    module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
    names = [a.name for a in node.names]
    
    if module in sys.stdlib_modules:
        return "PERFORMANCE"
    if any(n.endswith("TYPE_CHECKING") for n in names):
        return "TYPE_CHECKING"
    if _is_circular(module, filepath):
        return "CIRCULAR"
    if _is_optional(module):
        return "OPTIONAL"
    return "UNKNOWN"
```

### Reglas
- `WORKAROUND` y `UNKNOWN` nuevos → FAIL
- `CIRCULAR` existente → WARNING (documentar)
- `TYPE_CHECKING` y `OPTIONAL` → PASS

### Estado actual
~20 lazy imports, mayoría `CIRCULAR` y `TYPE_CHECKING`. 0 WORKAROUND. 0 UNKNOWN.

---

## Bloque C — Estado global

### Objetivo
Detectar y clasificar singletons instanciados a nivel de módulo.

### Clasificación
| Clase | Clasificación | Razón |
|-------|-------------|-------|
| `SubprocessExecutor()` | 🟡 Singleton permitido | Wrapper ligero sin estado |
| `ProviderRegistry()` | 🟡 Singleton permitido | Registry thread-safe |
| `CircuitBreaker(...)` | 🔴 Singleton pendiente | Debería estar en _state.py |
| `HybridMemory(...)` | 🔴 Singleton pendiente | Debería estar en _state.py |
| `QdrantClient(...)` | ❌ Singleton prohibido | Conexión a BD, debe ser lazy |

### Implementación
```python
SINGLETON_ALLOWED = {"SubprocessExecutor", "ProviderRegistry"}
SINGLETON_PENDING = {"CircuitBreaker", "HybridMemory", "HealthRegistry"}
SINGLETON_FORBIDDEN = {"QdrantClient", "httpx.AsyncClient", "requests.Session"}

def check_global_state(tree: ast.AST, filepath: str) -> list[dict]:
    findings = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                    name = _get_call_name(node.value)
                    if name in SINGLETON_FORBIDDEN:
                        findings.append({
                            "type": "singleton_forbidden",
                            "file": filepath,
                            "line": node.lineno,
                            "class": name,
                            "level": "P0"
                        })
    return findings
```

### Estado actual
- 9 `SubprocessExecutor()` — ✅ Permitidos
- 1 `ProviderRegistry()` — ✅ Permitido
- 0 prohibidos — ✅ Limpio

---

## Bloque D — _state.py

### Objetivo
Garantizar que `_state.py` solo contenga: dataclasses, NamedTuples, TypedDicts, factories (`build_*`), constantes y tipos.

### Permitido
```python
@dataclass(frozen=True)
class SomeState: ...
def build_some_state(...) -> SomeState: ...
CONSTANTE = "valor"
type Alias = ...
```

### Prohibido
```python
requests.get(...), provider.chat(...), await, for, while,
thread, asyncio, router.route(...), .execute(...)
```

### Implementación
```python
FORBIDDEN_STATE_PATTERNS = [
    "requests.", "httpx.", "router.route", ".chat(",
    ".execute(", "await ", "for ", "while ", "thread", "asyncio."
]

def check_state_file(filepath: str) -> list[dict]:
    findings = []
    if not filepath.endswith("_state.py"):
        return findings
    content = Path(filepath).read_text()
    for pattern in FORBIDDEN_STATE_PATTERNS:
        if pattern in content:
            findings.append({
                "type": "state_business_logic",
                "file": filepath,
                "pattern": pattern,
                "level": "FAIL"
            })
    return findings
```

### Estado actual
| Archivo | Business Logic? | Veredicto |
|---------|----------------|-----------|
| `motor/core/llm/_state.py` | ✅ `for _prov_cls in ...` (loop menor) | ⚠️ WARNING |
| `motor/diagnostico/_state.py` | ✅ Limpio | ✅ PASS |
| `motor/scanner/_state.py` | ✅ Limpio | ✅ PASS |
| `core/mochila/_state.py` | ✅ Limpio | ✅ PASS |

---

## Bloque E — Factories

### Objetivo
Verificar la convención: `build_*` no cachea, `get_*` puede cachear, `create_*` compone.

### Convención
| Prefijo | Caché? | Uso | Ejemplo |
|---------|--------|-----|---------|
| `build_*` | ❌ No | Crear objetos de infraestructura | `build_llm_state()` |
| `create_*` | ❌ No | Componer aplicaciones/servicios | `create_app()` |
| `get_*` | ✅ Sí | Instancias existentes o lazy init | `get_secret()` |

### Detección de anomalías
```python
def check_factory_naming(filepath: str, tree: ast.AST) -> list[dict]:
    findings = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("build_") and _has_cache_pattern(node):
                findings.append({
                    "type": "factory_caching",
                    "file": filepath,
                    "function": node.name,
                    "detail": "build_* no debería cachear",
                    "level": "WARNING"
                })
    return findings
```

### Estado actual
- `build_*`: 2 funciones, ninguna cachea ✅
- `get_*`: 25 funciones, muchas cachean (correcto) ✅
- `create_*`: 0 funciones ✅

---

## Bloque F — API pública

### Objetivo
Los scripts solo importan desde `motor.cli.public_api`. No desde `motor.core.*`, `motor.internal.*`.

### Regla
```python
ALLOWED_SCRIPT_IMPORTS = {"motor.cli.public_api"}
BENCHMARK_EXCEPTIONS = {"motor.core.llm.router", "motor.intelligence.retrieval", "motor.core.evaluation"}
```

### Implementación
```python
def check_script_imports(filepath: str) -> list[dict]:
    findings = []
    if not filepath.startswith("scripts/"):
        return findings
    if any(p in filepath for p in ["benchmark_", "test_", "soak_", "demo_", "generate_"]):
        return findings  # benchmarks/herramientas exentas
    
    content = Path(filepath).read_text()
    for match in re.finditer(r"^from (motor\.\w+) import|^import (motor\.\w+)", content, re.MULTILINE):
        imported = match.group(1) or match.group(2)
        if not imported.startswith("motor.cli.public_api"):
            findings.append({
                "type": "script_import_violation",
                "file": filepath,
                "import": imported,
                "level": "FAIL"
            })
    return findings
```

### Estado actual
| Script | Importa | Veredicto |
|--------|---------|-----------|
| `scripts/seed_transacciones.py` | `motor.core.config`, `motor.core.qdrant_client` | ❌ FAIL |
| `scripts/soak_test.py` | `motor.platform.health`, `motor.platform.tracing` | ❌ FAIL |
| `scripts/pro/f14_load_test.py` | `motor.core.config`, `motor.core.qdrant_client` | ⚠️ Benchmark, exento |
| `scripts/generate_synthetic_data.py` | `motor.core.fusion.*` | ⚠️ Benchmark, exento |
| `scripts/demo_full_pipeline.py` | `motor.core.fusion.*` | ⚠️ Demo, exento |

---

## Bloque G — Protocolos

### Objetivo
`core/` no importa implementaciones de `motor/`. Solo `Protocol`, `interfaces`, `typing`.

### Permitido
```python
from core.interfaces import IConfigProvider  # ✅
from typing import Protocol                    # ✅
```

### Prohibido
```python
from motor.core.config import UraConfig  # ❌
from motor.core.llm import generate      # ❌
```

### Excepciones documentadas actuales
| Archivo | Import | Razón |
|---------|--------|-------|
| `core/infra/heartbeat.py` | `motor.observability.*` | Logging + HealthRegistry (infraestructura) |
| `core/model_router/cli.py` | `motor.core.secrets` | Preflight security check |
| `core/auto_reindex.py` | `motor.core.config` | Constante module-level |
| `core/json_logger.py` | `motor.observability.logging` | Wrapper JSONFormatter (deprecado) |
| `core/memoria/qdrant_store.py` | `motor.core.qdrant_client` | Construcción de cliente |

### Implementación
```python
EXEMPTED_CORE_IMPORTS = {
    "core/infra/heartbeat.py", "core/model_router/cli.py",
    "core/auto_reindex.py", "core/json_logger.py",
    "core/memoria/qdrant_store.py",
}

def check_core_imports(filepath: str) -> list[dict]:
    if not filepath.startswith("core/") or filepath in EXEMPTED_CORE_IMPORTS:
        return []
    if filepath.endswith("_state.py"):
        return []  # _state.py puede construir con imports
    findings = []
    content = Path(filepath).read_text()
    for match in re.finditer(r"^from motor\.|^import motor\.", content, re.MULTILINE):
        findings.append({
            "type": "core_import_motor",
            "file": filepath,
            "import": match.group(),
            "level": "FAIL"
        })
    return findings
```

### Estado actual
6 imports en 5 archivos, todos exentos documentados. ✅

---

## Bloque H — Compatibilidad

### Objetivo
Detectar `__getattr__` a nivel de módulo y verificar que tenga `DeprecationWarning`.

### Regla
```python
def check_compat_shims(tree: ast.AST, filepath: str) -> list[dict]:
    findings = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
            has_warning = any(
                isinstance(n, ast.Call) and 
                getattr(n.func, 'attr', None) == 'warn'
                for n in ast.walk(node)
            )
            if not has_warning:
                findings.append({
                    "type": "compat_shim_without_warning",
                    "file": filepath,
                    "line": node.lineno,
                    "detail": "__getattr__ sin DeprecationWarning",
                    "level": "FAIL"
                })
    return findings
```

### Estado actual
0 `__getattr__` en motor/ o core/. ✅ Limpio.

---

## Bloque I — Archivos grandes

### Objetivo
Ranking compuesto de archivos por: líneas + funciones + complejidad + dependencias + estado global.

### Fórmula
```
prioridad = (líneas / 100) * 0.3 + 
            (funciones / 10) * 0.2 + 
            (complejidad_promedio / 10) * 0.3 +
            (dependencias / 5) * 0.1 +
            (singletons / 3) * 0.1
```

Donde `complejidad_promedio` usa complejidad ciclomática (McCabe) calculada con `ast`.

### Rangos
| Prioridad | Rango | Acción |
|-----------|-------|--------|
| Alta | >5.0 | Refactorizar |
| Media | 2.0–5.0 | Revisar |
| Baja | <2.0 | Monitorear |

### Estado actual
| Archivo | Líneas | Prioridad |
|---------|--------|-----------|
| `motor/platform/tracing.py` | 903 | Alta |
| `motor/core/fusion/stages/entity_resolver.py` | 764 | Alta |
| `motor/core/qdrant_client.py` | 603 | Alta |
| `motor/core/llm/router.py` | 535 | Media |
| `motor/assistant/api.py` | 488 | Media |
| `motor/core/fusion/models.py` | 443 | Media |
| `motor/assistant/executor.py` | 443 | Media |
| `motor/cli/cmd_ura.py` | 421 | Media |

---

## Bloque J — Tendencias

### Objetivo
Serie temporal automatizada actualizada en cada commit relevante.

### Métricas
| Métrica | Objetivo | v3.5.3 | v4.10.0 |
|---------|----------|--------|---------|
| Side effects en import | 0 | 0 | 0 |
| Lazy imports WORKAROUND | 0 | 0 | 0 |
| Lazy imports totales | ↓ | 488 | ~400 |
| Singletons prohibidos | 0 | 2 | 0 |
| Módulos >500 líneas | ↓ | 6 | 4 |
| Complejidad C o peor | ↓ | — | — |
| Tiempo medio de import | ↓ | 353ms | ~300ms |
| Protocolos implementados | ↑ | 3 | 5 |
| Cobertura de reglas automáticas | ↑ | 0% | 100% |

### Implementación
```python
def update_trends(result: dict) -> None:
    """Actualiza METRICAS_BASELINE.md con los valores actuales."""
    trends_path = Path("docs/architecture/METRICAS_BASELINE.md")
    # Añadir fila a la tabla de serie temporal
    # ...
```

---

## Bloque K — ADR Enforcement

### Objetivo
Cada ADR importante tiene una comprobación automatizada.

### ADRs verificables
| ADR | Comprobación | Implementación |
|-----|-------------|----------------|
| ADR-007 — Core Modification Rule | Verificar que modificaciones a core/ tienen ADR | Buscar cambios en core/ sin ADR asociado |
| ADR-030 — Infra congelada v2.3 | PipelineEngine no ha sido modificado | Checksum del archivo engine.py |
| ADR-031 — Reuso ≥85% | Reuse detector se ejecutó antes del commit | Verificar archivo de caché de reuse |
| AGENTS.md — _state.py policy | _state.py no tiene lógica de negocio | Bloque D |
| AGENTS.md — Factory convention | build_*/create_*/get_* siguen convención | Bloque E |
| AGENTS.md — Deprecation policy | __getattr__ tiene DeprecationWarning | Bloque H |

### Implementación
```python
ADR_CHECKS = {
    "ADR-030": lambda: _check_file_unchanged("scripts/pro/tuneladora/engine.py", "v3.5.2"),
    "ADR-031": lambda: _check_reuse_cache_exists(),
    "AGENTS.md:state": lambda: check_state_files(),
    "AGENTS.md:factories": lambda: check_factory_naming(),
}

def run_adr_checks() -> list[dict]:
    results = []
    for name, check in ADR_CHECKS.items():
        results.append({"adr": name, "result": check()})
    return results
```

---

## Integración

### Script Único
```bash
python3 scripts/pro/arq_auditor.py [--json] [--html] [--check]
```

### Frecuencia
- Pre-commit (gancho de git)
- CI (GitHub Actions)
- Pipeline de mejora continua (tuneladora)

### Salida
```json
{
  "version": "v4.10.0",
  "timestamp": "2026-07-21T19:00:00Z",
  "blocks": {
    "A": {"status": "PASS", "findings": [], "score": 100},
    "B": {"status": "PASS", "findings": [], "score": 100},
    ...
  },
  "global_score": 92,
  "health_index": 92,
  "trends": { ... },
  "adr": { "ADR-030": "PASS", ... }
}
```

### HTML Dashboard
El HTML generado incluye:
- Score global (0–100)
- Semáforo por bloque (verde/amarillo/rojo)
- Ranking de archivos grandes
- Serie temporal de métricas
- Estado de ADRs

---

## Orden de Implementación

| Fase | Bloques | Esfuerzo | Depende de |
|------|---------|----------|------------|
| 1 | **A** (Side effects) + **H** (Compatibilidad) | 2h | — |
| 2 | **F** (API pública) + **G** (Protocolos) | 2h | — |
| 3 | **D** (_state.py) + **E** (Factories) | 1.5h | — |
| 4 | **B** (Lazy imports) + **C** (Estado global) | 3h | — |
| 5 | **I** (Archivos grandes) + **J** (Tendencias) | 2h | Bloques A–H |
| 6 | **K** (ADR Enforcement) + HTML Dashboard | 2h | Bloques A–J |
| **Total** | **10 bloques** | **~12.5h** | |

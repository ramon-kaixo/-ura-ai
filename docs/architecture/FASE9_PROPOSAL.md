# Propuesta — Fase 9: Impacto Funcional y Consolidación Arquitectónica

> **Versión:** 2.0 (refinada tras revisión de codebase)
> **Fecha:** 2026-07-04
> **Estado:** ✅ Aprobada
> **Fase anterior:** Auditoría Arquitectónica Post-Fase 8 (`v0.7.1-audit-fase8`)

---

## Principio Rector

Solo trabajo con **impacto funcional o arquitectónico demostrable**.  
La deuda técnica residual (lint, FTS, tests dependientes del entorno,
archivos Unicode, limpieza menor) queda en backlog independiente y
no bloquea ni se mezcla con esta fase.

---

## Stream A — Consolidación de Test Runners (Arquitectura)

**Problema:** `tests/test_unit.py` (481) y `tests/unit_test_runner.py` (490)
son ~95% duplicados con divergencia menor. Ambos usan runner inline
(`check()` → global `PASS`/`FAIL`), no pytest. 4 runners legacy más no
tienen `test_` prefijo.

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `tests/test_unit.py` | 481 | Runner inline con 56 checks |
| `tests/unit_test_runner.py` | 490 | Casi idéntico, 2 checks extra |
| `tests/test_integration.py` | 16 | Smoke test inline |
| `tests/test_config.py` | 34 | Config smoke test inline |
| `tests/benchmark_fase7.py` | ~150 | Benchmark, no pytest |
| `tests/e2e_fase7.py` | ~200 | E2E, no pytest |

**Análisis de divergencia entre `test_unit.py` y `unit_test_runner.py`:**
- `test_unit.py` testea `obtener_modelos_disponibles`, `_chunk_text`,
  `_sha256`, manifest io, `chromadb` check inline
- `unit_test_runner.py` testea `_chromadb_available`, no `obtener_modelos_disponibles`
- Modelos esperados difieren ligeramente (qwen2.5:7b vs qwen2.5-coder:14b-instruct-q8_0)
- Assertions del SNC ligeramente distintas ("version >= 1.0" vs "version = 2.0")
- PromptCache tests: unit_test_runner tiene 4 checks, test_unit tiene 5

**Acción:**
1. Unificar ambos en un solo `tests/test_unit.py` con el superset de checks
   (incluyendo `_chromadb_available` y `obtener_modelos_disponibles`)
2. Convertir `check()` inline → test functions pytest con `assert`
3. Mover benchmarks a `tests/benchmarks/benchmark_fase7.py`
4. Asegurar que `pytest tests/` cubre todos los tests sin excluir archivos
5. Marcar tests dependientes del entorno con `@pytest.mark.skipif`

**Impacto:** Cobertura pytest fiable, 0 archivos excluidos, eliminación de
duplicación. **Prerrequisito para refactorizar ura.py con confianza.**

**Riesgos detectados:** Ninguno. Trabajo mecánico de consolidación.

---

## Stream B — Sistema de Plugins en Pipeline (Arquitectura)

**Problema:** `scripts/pro/plugin_registry.py` (133 líneas) existe y
funciona (descubrimiento por AST scanning de `PLUGIN = {...}` en scripts,
fases con blocking/timeout) pero no es llamado desde ningún pipeline.

**Análisis:** `plugin_registry` usa `subprocess.run` con `sys.executable`
para cada plugin en fase. Esto da aislamiento pero no es eficiente para
plugins ligeros. La integración debe ser por import, no subprocess.

**Acción:**
1. **Eliminar `subprocess.run`** del sistema de plugins. Sustituir por
   `importlib` dinámico: cada plugin expone una función `run(ctx)`, el
   registry la importa y ejecuta en el mismo proceso.
2. El plugin registry adopta un mecanismo de carga directa:
   - Escanea `scripts/pro/plugins/` por módulos `.py` con función
     `plugin(ctx) -> dict`
   - Importa cada uno con `importlib.import_module()`
   - Ejecuta en el proceso actual (sin subprocess overhead)
   - Captura excepciones por plugin (aislamiento sin subprocess)
3. Integrar hook opcional en `tuneladora_mantenimiento.py` post-inspectores
4. El hook es NO-bloqueante: si falla el import de plugin_registry, el
   pipeline continúa normalmente (degradación graceful)
5. Documentar interfaz de plugin y directorio `scripts/pro/plugins/`
   (referencia: `PLUGIN_TEMPLATE.py`)

**Impacto:** Pipeline extensible sin modificar tuneladora. Cero riesgo de
regresión.

**Riesgo resuelto:** `subprocess.run` eliminado. Carga directa con
importlib mantiene aislamiento vía captura de excepciones por plugin.

---

## Stream C — Modo Degradado Explícito y Observable (Funcional)

**Problema:** El sistema de degradación graceful existe (Qdrant, Ollama
fallan silenciosamente con `except: pass`) pero no hay forma de saber en
runtime qué subsistemas están degradados.

**Análisis:**
- `motor/core/state.py` (76 líneas) ya existe con dataclasses de estado.
  No es necesario crear un módulo `global_state` nuevo — se puede extender
  `state.py` con un `GlobalState` singleton thread-safe.
- `ejecutor_api.py` ya sirve en puerto 4096 como systemd.

**Acción:**
1. Añadir a `motor/core/state.py` clase `DegradedMode(set[str])` o
   `global_state: dict[str, bool]` thread-safe con RLock
2. Integrar en puntos de falla conocidos: `motor/core/qdrant_client.py`,
   `core/mochila/providers/`, `knowledge/engine/qdrant_sync.py`
3. Exponer GET `/api/v1/status` en `ejecutor_api.py` que serializa
   `global_state`
4. Loggear WARNING en cada transición (normal→degradado, degradado→normal)
5. Documentar en `docs/architecture/DEGRADED_MODE.md`

**Objetos de estado observables:**
```json
{
  "status": "degraded",
  "degraded_subsystems": ["qdrant"],
  "since": "2026-07-04T12:00:00Z",
  "healthy_subsystems": ["ollama", "fts", "router"]
}
```

**Impacto:** Visibilidad operativa inmediata. Sin cambios de comportamiento.

**Riesgos detectados:** Ninguno. Trabajo independiente y bien acotado.

---

## Stream D — Refactor de `ura.py` (Arquitectura)

**⚠️ CORRECCIÓN RESPECTO A VERSIÓN 1.0**

**Problema real:** `ura.py` (583 líneas) expone 16 comandos: `finalize`,
`test`, `maintenance`, `rotate`, `snc`, `health`, `alerts`, `index`, `ask`,
`memory`, `snapshot`, `doctor`, `metrics`, `status`, `deploy`, `inspect`.
Tiene 15+ branches en `main()` y usa `import lazy` condicional dentro de
funciones.

**Análisis de la propuesta original (V1):** Decía "extraer CLI a
`motor/cli/` (ya existe `cmd_pipeline.py`, `cmd_diag.py`, etc.) y que
`ura.py` delegue en `motor.cli.main`".

**Problema:** `ura.py` y `motor.cli.main` tienen comandos
**completamente diferentes**:

| motor.cli.main | ura.py |
|----------------|--------|
| pipeline, scan, diagnose, calibrate | finalize, test, deploy, index, ask, memory, doctor, metrics, status, snc, health, alerts, rotate, snapshot, inspect, maintenance |

No hay solapamiento. "Delegar en motor.cli.main" NO funcionaría sin portar
16 comandos.

**Acción refinada:**
1. Extraer las funciones comando (`cmd_*`) de `ura.py` a un nuevo módulo
   `motor/cli/cmd_ura.py`, manteniendo firmas y comportamiento intactos
2. `ura.py` queda como entrypoint mínimo (~50 líneas): parsea argv y
   delega en `cmd_ura.cmd_finalize()`, `cmd_ura.cmd_test()`, etc.
3. `main()` deja de tener 15+ branches inline → tabla de despacho
4. 0 cambios de comportamiento observable
5. Tests: la consolidación de Stream A da cobertura base para verificar
   que no hay regresiones

**Impacto:** `ura.py` de 583→~50 líneas. Cluster de 16 funciones
portado a módulo dedicado. Separación clara de responsabilidades.

**Riesgos detectados:**
- Los 16 comandos no tienen tests pytest dedicados (solo inline
  subprocess en `cmd_finalize` y `cmd_doctor`)
- Stream A (test consolidation) es prerrequisito para refactorizar
  con confianza
- Los SSH/network commands tardan en fallar (timeout 30-60s) →
  ralentizan el ciclo test/feedback
- **Propuesta:** implementar D DESPUÉS de A, y escribir tests
  unitarios para cada `cmd_*` con mocking de subprocess

---

## Orden de Ejecución Definitivo (Aprobado)

```
Stream C ──► Stream A ──► Stream B ──► Stream D
   ↓            ↓              ↓              ↓
independ.   fundación     subprocess→      último,
             para D     importlib previo  test coverage
```

### Secuencia
1. **C** — Modo degradado explícito: sin dependencias, menor riesgo, aporta
   visibilidad operativa inmediata. Se ejecuta primero.
2. **A** — Consolidación de test runners: prerrequisito estructural para D.
   Sin pytest consolidado, refactorizar ura.py no es verificable.
3. **B** — Sistema de plugins: **antes de integrar en pipeline**, eliminar
   la dependencia de `subprocess.run` y sustituir por carga directa con
   `importlib` o registro de plugins en memoria. Solo entonces integrar
   en `tuneladora_mantenimiento.py`.
4. **D** — Refactor de ura.py: último, con test coverage ya consolidado
   (Stream A) y sin dependencia pendiente de B o C.

---

## Regla de Validación Obligatoria (Fase 9)

**Ningún stream se da por finalizado hasta superar su validación completa:**

```
┌─────────────────────────────────────────────┐
│ 1. Tests: pytest -q sobre el código afectado │
│ 2. Lint: ruff check sobre archivos tocados  │
│ 3. Docs: AGENTS.md actualizado si aplica     │
│ 4. Regresiones: 0 tests rotos pre-existentes │
│ 5. Commit: --no-verify, push a origin        │
└─────────────────────────────────────────────┘
```

Cada stream produce un commit independiente y verificable. No se avanza
al siguiente stream hasta que el anterior está validado y pusheado.

---

## Criterios de Aceptación (Refinados)

| Stream | Criterio | Verificación |
|--------|----------|-------------|
| A | `pytest tests/ -q` ejecuta todos los tests legacy + nuevos sin excluir archivos | `coverage run -m pytest tests/ -q` no omite ningún archivo .py en tests/ |
| B | `plugin_registry` es invocado por tuneladora en modo seco (`--dry-run`) | Log en modo seco: `"Plugins: 0 encontrados"` |
| C | `GET /api/v1/status` retorna JSON con campos `status`, `degraded_subsystems`, `healthy_subsystems` | `curl http://localhost:4096/api/v1/status \| jq .status` |
| D | Todos los comandos de `ura.py --help` funcionan igual que antes del refactor | Script de regresión: ejecuta cada comando con `--help` y compara output textual |

---

## Dependencias Reales entre Streams

```
       ┌───┐
       │ C │ ← sin dependencias
       └───┘
         
       ┌───┐
       │ A │ ← sin dependencias
       └──┬┘
          │ soft dependency
       ┌──▼┐    ┌───┐
       │ B │    │ D │ ← A es prerequisito (tests)
       └───┘    └───┘
```

- **A → B**: Débil. B requiere integración en tuneladora, que se prueba
  mejor con tests consolidados. No es bloqueante.
- **A → D**: Fuerte. Sin pytest coverage, refactorizar ura.py sin romper
  nada no es verificable.
- **C** es completamente independiente. Se puede ejecutar en cualquier
  momento, incluso en paralelo.

---

## Backlog de Deuda Técnica (No Bloqueante, No Incluido en Fase 9)

| ID | Ítem | Prioridad | Notas |
|----|------|-----------|-------|
| T01 | `core/synonyms.json` chattr +i | Mínima | `sudo chattr -i && rm` |
| T02 | `sanear_codigo.py:50` syntax error | Baja | String no cerrado |
| T03 | 12 archivos .py con caracteres no-ASCII | Baja | Renombrar (coverage puede parsear) |
| T04 | 5 tests CLI fallan (deps entorno) | Baja | Instalar deps o `@pytest.mark.skipif` |
| T05 | FTS schema verifier falso positivo | Media | Ignorar tablas FTS en verifier |
| T06 | ~2.356 lint errors (ruff all rules) | Baja | Refactor progresivo |
| T07 | `adapters/` nunca creado | Informativa | Decidir crear o remover de docs |
| T08 | ~80+ `except: pass` sin auditar | Media | Auditoría de seguridad postergada |

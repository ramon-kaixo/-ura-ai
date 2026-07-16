# Fase 17 — Unificación del Sistema de Configuración

> **Estado:** Propuesta aprobada
> **Depende de:** Cierre de F16 (`v0.16.0-fase16`)
> **Objetivo:** Unificar la configuración en una sola fuente de verdad (`system_config.json` → `CONFIG` → `UraConfig` como vista tipada), eliminando la deuda técnica acumulada en F14–F16.
> **Regla cardinal:** No añadir funcionalidades. No cambiar comportamiento observable. Cada bloque se valida individualmente antes de pasar al siguiente.

---

## Regla de Rollback por Bloque

Si cualquier bloque introduce una regresión en `py_compile`, `ruff` o `pytest`, el bloque **no se considera completado**. Se corrige o se revierte antes de comenzar el siguiente. No se acumulan cambios pendientes entre bloques.

Excepción: errores pre-existentes documentados en el baseline del bloque. Solo se exigen 0 errores **nuevos**.

---

## Prerrequisito — Resolver F14-F01 (fuera de F17)

**No forma parte de la fase.** Es un prerrequisito operativo que debe ejecutarse antes o durante F17, pero no bloquea el plan.

### Acciones
1. Ejecutar `sudo chattr -i config/system_config.json config/schema.json` en GX10.
2. Verificar que ambos archivos son editables: `lsattr config/system_config.json`.
3. Confirmar que `core/config_manager.py` puede leer y validar `system_config.json` sin depender de `config.local.json`.

### Si no puede realizarse
F17 continúa utilizando el mecanismo temporal documentado (`config.local.json` como deprecated, ver B2). La eliminación completa se difiere a F18 o hasta que el entorno lo permita.

---

## Contexto

Tras F15 y F16, la inferencia está centralizada en `motor/core/llm/`. Sin embargo, el sistema de configuración arrastra deuda de tres fases:

| Origen | Deuda |
|--------|-------|
| **F14-F01** | `config/system_config.json` y `config/schema.json` con `chattr +i`. Imposibilidad de modificar la configuración sin `sudo`. |
| **F15** | `config.local.json` como workaround. Sección `llm` añadida a `_REQUIRED_KEYS`. Carga en `config_manager.py:74-80`. |
| **F16-B4.2** | `_ollama_url()` en `ura_multi_agent.py` replica lógica de `get_ollama_url()`. |

Además, coexisten **dos sistemas de configuración independientes**:

| Sistema | Módulo | Archivo | Ámbito | Consumidores |
|---------|--------|---------|--------|-------------|
| **Config Manager** | `core/config_manager.py` | `config/system_config.json` + `config.local.json` | Config operativa (~50+ claves: Ollama, rutas, modelos, mantenimiento) | 13 módulos |
| **UraConfig** | `motor/core/config.py` (dataclass) | `/etc/ura/config.json` o `URA_CONFIG` env var | Config del motor (Qdrant, deploy, logging, timer, failover, 15 campos) | 42 imports |

Ambos se solapan parcialmente (Qdrant host/port, paths, log_level) pero difieren en estructura, valores por defecto y mecanismo de carga. No hay un mecanismo claro de prioridad entre ellos.

---

## Arquitectura Objetivo

```
config/system_config.json        ← única fuente de verdad en disco
            │
   core/config_manager.py         ← carga, fusión de perfiles, validación
            │
      CONFIG (dict)               ← API de acceso para todo el proyecto
            │
     motor/core/config.py         ← typed view (no loader independiente)
      UraConfig (dataclass)       ← construido desde CONFIG, no desde JSON/env
            │
       Resto del proyecto         ← consume UraConfig o CONFIG según necesidad
```

**Principios:**
- `system_config.json` es la única fuente de verdad persistente.
- `UraConfig` se convierte en una **vista tipada** de `CONFIG`, no en un cargador independiente.
- No se añaden nuevos parámetros de configuración.
- No cambia el comportamiento observable de ninguna función.

---

## Fuera de Alcance

- Cambios funcionales en cualquier módulo.
- Nuevos parámetros de configuración.
- Refactorizaciones no relacionadas con configuración.
- `core/mochila/*` y subsistemas que no dependan de `CONFIG` o `UraConfig` (salvo que el inventario B1 demuestre dependencia directa).
- `scripts/pro/*` (excepto aquellas referencias que bloqueen la migración).

---

## Bloques

### B1 — Auditoría Completa de Configuración

**Objetivo:** Inventariar todos los consumidores, parámetros duplicados y diferencias entre `CONFIG` y `UraConfig` antes de cualquier modificación.

**Alcance:**
- Listar los 13 consumidores de `core/config_manager.py` y los 42 imports de `UraConfig` desde `motor.core.config`.
- Mapear cada campo de `UraConfig` contra su equivalente en `CONFIG` (o documentar que no existe).
- Identificar parámetros duplicados con valores distintos o defaults incompatibles.
- Identificar claves en `CONFIG` que ningún consumidor utiliza (candidatas a poda).
- Documentar el flujo de carga de ambos sistemas y el orden de prioridad actual.

**Archivos afectados:** Ninguno (solo lectura y documentación).

**Entregable:** `docs/architecture/CONFIG_AUDIT.md` con:
- Tabla de consumidores por módulo.
- Matriz de solapamiento `UraConfig` ↔ `CONFIG`.
- Inventario de parámetros huérfanos o duplicados.
- Diagrama de flujo de carga actual.

**Riesgos:** Bajo. Solo lectura. Puede revelar dependencias inesperadas.

**Validación:** Revisión humana del documento.

---

### B2 — Deprecación de `config.local.json`

**Objetivo:** Eliminar la dependencia funcional de `config.local.json` sin romper despliegues que todavía lo tengan presente.

**Alcance:**
1. En `core/config_manager.py`:
   - Añadir `logging.warning("config.local.json encontrado — DEPRECATED. Será eliminado en F18.")` cuando el archivo exista y se cargue.
   - El archivo se sigue cargando (compatibilidad), pero con aviso.
2. Documentar la deprecación en el docstring de `load_config()` y en el closeout de F15.
3. No eliminar `_LOCAL_CONFIG_PATH` ni la lógica de carga — eso ocurre en B6.

**Archivos afectados:**
- `core/config_manager.py` — añadir warning de deprecación.

**Riesgos:** Muy bajo. No cambia comportamiento funcional.

**Criterios de aceptación:**
- Si `config.local.json` existe: se carga y se emite warning.
- Si `config.local.json` no existe: carga normal sin warning.
- 0 cambios en valores de configuración resultantes.

**Validación:** `py_compile`, `ruff`, `pytest -q`.

---

### B3 — Corrección de Inconsistencias

**Objetivo:** Resolver defectos concretos de configuración sin cambiar la arquitectura.

**Alcance:**
1. **`get_ollama_urls` (plural):** `core/model_router.py:83` hace `from core.config_manager import get_ollama_urls` — esta función no existe en `config_manager.py`. Solución: añadir alias en `config_manager.py` o cambiar la importación en `model_router.py` a `get_ollama_url`.
2. **`_ollama_url()` duplicada:** `core/ura_multi_agent.py:55` define `_ollama_url()` que replica la lógica de `core.config_manager.get_ollama_url()`. Solución: reemplazar internamente por `get_ollama_url()`.
3. **Helpers duplicados:** Verificar si existen otras funciones sueltas que construyan URLs de Ollama fuera de `config_manager.py`.
4. **Defaults distintos:** Comparar valores por defecto de `os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434")` en `core/ura_multi_agent.py` (versión antigua) vs `get_ollama_url()` que lee de `CONFIG["ollama"]["host:port"]`. Unificar criterio.

**Archivos afectados:**
- `core/config_manager.py` — añadir `get_ollama_urls` como alias si procede.
- `core/model_router.py` — corregir import.
- `core/ura_multi_agent.py` — reemplazar `_ollama_url()` → `get_ollama_url()`.

**Riesgos:** Bajo. Cambios localizados. Ninguno toca lógica de negocio.

**Criterios de aceptación:**
- `get_ollama_urls` ya no falla en tiempo de importación.
- `ura_multi_agent.py` usa `get_ollama_url()` y elimina `_ollama_url()`.
- 0 funciones auxiliares de URL de Ollama duplicadas.

**Validación:** `py_compile`, `ruff`, `pytest -q`.

---

### B4 — Diseño de Convergencia

**Objetivo:** Decidir y documentar el modelo de convergencia antes de migrar.

**Alcance:**
1. Analizar los hallazgos de B1 para determinar:
   - Qué campos de `UraConfig` existen también en `CONFIG` (candidatos a unificación directa).
   - Qué campos de `UraConfig` no existen en `CONFIG` (habrá que añadirlos a `system_config.json` o dejarlos como env/archivo independiente).
   - Qué campos de `CONFIG` no son necesarios en `UraConfig`.
2. Decidir el mecanismo: `UraConfig.from_config(CONFIG)` o `UraConfig.load()` internamente llama a `config_manager.load_config()`.
3. Documentar la matriz de mapeo y el plan de migración por consumidor.

**Opción seleccionada (A):**
```
UraConfig se construye desde CONFIG.
motor.core.config.load() ya no lee JSON/env directamente.
Los 15 campos de UraConfig pasan a ser derivados de CONFIG.
Los campos que no existan en CONFIG se añaden a system_config.json.
```

**Archivos afectados:** Solo documentación (`CONFIG_AUDIT.md` se actualiza con la decisión y el plan de migración).

**Entregable:** Sección "Plan de Migración" en `CONFIG_AUDIT.md` con:
- Matriz campo a campo.
- Orden de migración de consumidores (priorizando los más sencillos).
- Estrategia de compatibilidad hacia atrás.

**Riesgos:** Ninguno (solo diseño).

**Validación:** Revisión humana.

---

### B5.1 — Refactor de `UraConfig`

**Objetivo:** Modificar `motor/core/config.py` para que `UraConfig` se construya desde `CONFIG` en lugar de leer JSON/env directamente.

**Alcance:**
1. Modificar `UraConfig.load()`:
   - Ya no lee JSON/env directamente.
   - Internamente llama a `config_manager.load_config()` para obtener `CONFIG`.
   - Construye la dataclass desde el dict.
   - Mantener compatibilidad hacia atrás: `UraConfig.load()` sin argumentos devuelve los mismos valores que antes.
   - El parámetro `path` y la env var `URA_CONFIG` se mantienen como compatibilidad (se emitirá deprecation warning si se usan).
2. Para cada campo de `UraConfig`:
   - Si existe en `CONFIG`, tomarlo de ahí.
   - Si no existe, mantener el default actual documentado.
3. Añadir test parametrizado: `UraConfig.xxx == CONFIG["xxx"]` para todos los campos compartidos.

**Archivos afectados:**
- `motor/core/config.py` — refactor de `load()` y posiblemente del constructor.

**Riesgos:** Medio. 42 consumidores dependen de que `UraConfig.load()` devuelva exactamente los mismos valores.

**Criterios de aceptación:**
- `UraConfig.load()` sin argumentos produce los mismos valores que antes en todos los campos.
- `UraConfig.load(path=algo)` funciona y emite deprecation warning.
- Test de consistencia `UraConfig == CONFIG` pasa.

**Validación:** `py_compile`, `ruff`, `pytest -q`.

---

### B5.2 — Migración Progresiva de Consumidores

**Objetivo:** Migrar los 42 consumidores de `UraConfig` para que usen la fuente unificada, grupo por grupo.

**Alcance:**
Migrar en el siguiente orden, validando cada grupo antes de pasar al siguiente:

| Orden | Grupo | Módulos | Imports | Riesgo |
|:-----:|-------|---------|:-------:|:------:|
| 1 | **guard** | `motor/guard/preflight.py`, `motor/guard/verifier.py` | 2 | Bajo |
| 2 | **scanner** | `motor/scanner/__init__.py`, `motor/scanner/collector_red.py`, `motor/diagnostico/__init__.py` | 3 | Bajo |
| 3 | **pipeline** | `motor/pipeline/orchestrator.py` | 1 | Bajo |
| 4 | **cli** | `motor/cli/cmd_pipeline.py`, `cmd_status.py`, `cmd_ura.py`, `cmd_diag.py`, `cmd_utils.py`, `main.py` | 6 | Medio |
| 5 | **knowledge** | `knowledge/engine/qdrant_sync.py` (import diferido) | 1 | Bajo |
| 6 | **scripts** | 17 archivos en `scripts/pro/` y `core/memory_engine.py`, `core/auto_reindex.py`, `core/infra/heartbeat.py` | 20 | Alto |

**Regla:** Cada grupo se valida individualmente antes de migrar el siguiente. Si un grupo introduce regresión, se revierte ese grupo completo y se analiza la causa antes de reintentar.

**Archivos afectados:** Los consumidores migrados (sin cambiar su API externa, solo la procedencia de los datos).

**Riesgos:** Alto para el grupo `scripts` (17 archivos con lógica de inicialización potencialmente frágil). Mitigación: migrar scripts al final, después de validar que `motor/core/config.py` mantiene la compatibilidad.

**Criterios de aceptación:**
- Todos los tests existentes pasan después de cada grupo.
- `UraConfig.load()` devuelve los mismos valores que antes de la migración.
- 0 cambios en comportamiento observable.

**Validación:** `py_compile` + `ruff` + `pytest -q` después de cada grupo.

---

### B6 — Eliminación de Deuda Técnica

**Objetivo:** Cuando ya no existan consumidores de las rutas antiguas, eliminar el código legacy.

**Alcance:**
1. Eliminar carga duplicada de JSON en `motor/core/config.py` (el parámetro `path` y env var `URA_CONFIG` pueden eliminarse o dejarse como compatibilidad documentada).
2. Evaluar `config/loader.py` — si es redundante con `config_manager.py`, eliminarlo.
3. Eliminar workarounds documentados en F15 (referencias a `config.local.json` en docs).
4. Eliminar `_LOCAL_CONFIG_PATH` y la lógica de carga condicional en `config_manager.py`.
5. Actualizar `docs/architecture/CONFIGURATION.md`.
6. Actualizar `docs/architecture/FASE15_CLOSEOUT.md` para reflejar que el workaround ya no es necesario.
7. Actualizar `AGENTS.md` — eliminar referencias a `config.local.json`.
8. Verificar que `_REQUIRED_KEYS` en `config_manager.py` no contiene claves del workaround (`llm`).

**Archivos afectados:**
- `motor/core/config.py` — limpieza de código muerto.
- `config/loader.py` — evaluar y posiblemente eliminar.
- `core/config_manager.py` — eliminar `_LOCAL_CONFIG_PATH` y lógica de carga.
- Documentación variada.

**Riesgos:** Bajo (solo eliminación, después de que B5.2 haya migrado todos los consumidores).

**Criterios de aceptación:**
- 0 referencias a `config.local.json` en código y documentación.
- 0 código de carga duplicado.
- `CONFIGURATION.md` describe una sola fuente de verdad.

**Validación:** `py_compile`, `ruff`, `pytest -q`.

---

### B6.5 — Auditoría Automática

**Objetivo:** Dejar una evidencia reproducible y scripteable del estado de la configuración al cierre de F17.

**Alcance:**
Crear script `scripts/audit_config.py` que ejecute las siguientes comprobaciones y genere un informe:

| # | Comprobación | Método | Objetivo |
|---|-------------|--------|----------|
| 1 | `UraConfig.load()` directo | `grep -rn "UraConfig\.load("` en `motor/` `core/` `knowledge/` | 0 ocurrencias |
| 2 | `config.local.json` en código | `grep -rn "config\.local\.json"` en `*.py` | 0 ocurrencias |
| 3 | `system_config.json` directo | `grep -rn '"system_config\.json"'` en `*.py` (excluyendo `config_manager.py`) | 0 ocurrencias |
| 4 | `get_ollama_urls` erróneo | `grep -rn "get_ollama_urls"` en `*.py` | 0 ocurrencias (o solo definición) |
| 5 | `_ollama_url()` helper | `grep -rn "_ollama_url"` en `*.py` | 0 ocurrencias |
| 6 | `URA_CONFIG` env var | `grep -rn "URA_CONFIG"` en `*.py` | 0 ocurrencias (o solo en config_manager) |

El script retorna código 0 si todas las comprobaciones pasan, código 1 si alguna falla, e imprime un resumen.

**Archivos afectados:**
- `scripts/audit_config.py` — nuevo archivo.

**Riesgos:** Bajo. Solo añade un script de verificación.

**Criterios de aceptación:**
- El script se ejecuta sin errores.
- En estado final de F17, todas las comprobaciones pasan.

**Validación:** Ejecución manual: `python3 scripts/audit_config.py`.

---

### B7 — Validación Final y Cierre

**Objetivo:** Verificar que se cumple la Definition of Done completa y producir el tag de versión.

**Checklist:**

| # | Check | Criterio |
|---|-------|----------|
| 1 | Fuente única de verdad | `system_config.json` es el único archivo de configuración persistente. |
| 2 | `UraConfig` como typed view | Todos los campos de `UraConfig` se derivan de `CONFIG`. |
| 3 | `config.local.json` no tiene consumidores directos | 0 ocurrencias en `*.py` (verificado por B6.5). |
| 4 | Helpers de URL de Ollama duplicados | 0 ocurrencias (verificado por B6.5). |
| 5 | `UraConfig.load()` sin lectura JSON directa | 0 ocurrencias en `motor/` `core/` `knowledge/` (verificado por B6.5). |
| 6 | Tests de consistencia `UraConfig == CONFIG` | 100% pasan. |
| 7 | Nuevos errores Ruff | 0 (solo pre-existentes). |
| 8 | Regresiones Pytest | 0 (mismo resultado que baseline). |
| 9 | Documentación actualizada | `CONFIGURATION.md`, `AGENTS.md`, `FASE15_CLOSEOUT.md` reflejan estado real. |
| 10 | Working tree limpio | `git status` sin cambios sin commitear. |

**Métricas verificables de la Definition of Done:**

| Comprobación | Objetivo |
|-------------|----------|
| Consumidores directos de `config.local.json` | 0 |
| Helpers de URL de Ollama duplicados | 0 |
| `UraConfig.load()` leyendo JSON directamente | 0 |
| Tests de consistencia `UraConfig == CONFIG` | 100% pasan |
| Nuevos errores Ruff | 0 |
| Regresiones Pytest | 0 |

---

## Cronograma B1 → B7

| Bloque | Descripción | Esfuerzo estimado | Depende de |
|--------|-------------|:-----------------:|------------|
| **B1** | Auditoría completa | 2-3h | — |
| **B2** | Deprecación `config.local.json` | 0.5h | B1 |
| **B3** | Corrección de inconsistencias | 1h | B1 |
| **B4** | Diseño de convergencia | 1-2h | B1, B3 |
| **B5.1** | Refactor `UraConfig` | 2-3h | B4 |
| **B5.2** | Migración consumidores (6 grupos) | 4-8h | B5.1 |
| **B6** | Eliminación de deuda | 1-2h | B5.2 |
| **B6.5** | Auditoría automática | 0.5h | B6 |
| **B7** | Validación final y cierre | 1h | B6, B6.5 |
| **Total** | | **13-21h** | |

---

## Riesgos y Estrategia de Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|:-----------:|:-------:|------------|
| Alto número de consumidores de `UraConfig` (42) | Alta | Medio | B1 (inventario) antes de cualquier cambio. Migración progresiva en B5.2 por grupos con validación individual. |
| `NoNewPrivileges=yes` bloquea `sudo chattr -i` | Media | Alto | El prerrequisito está fuera de F17. Si no se puede desbloquear, se mantiene `config.local.json` como deprecated hasta F18. |
| Scripts en `scripts/pro/` con lógica de configuración frágil | Alta | Medio | Grupo de scripts migrado al final de B5.2. Validación individual. Posibilidad de excluir scripts problemáticos y documentarlos como deuda remanente. |
| Compatibilidad hacia atrás de `UraConfig.load()` | Media | Alto | Tests existentes deben pasar sin cambios. Si algún consumidor depende del comportamiento actual de `load()` (lectura directa de env/archivo), mantenerlo como fallback documentado. |
| Dependencias circulares entre `motor.core.config` y `core.config_manager` | Baja | Alto | Verificar en B4/B5.1 que no se introducen. Si ocurre, extraer la lógica compartida a un tercer módulo (`core/config_base.py`). |
| Regresión no detectada en un grupo de B5.2 | Media | Medio | Regla de rollback: el grupo se revierte antes de continuar. El error se documenta y se analiza antes de reintentar. |

---

## Definition of Done

1. **Una única fuente de verdad:** `system_config.json` es el único archivo de configuración persistente en el proyecto.
2. **UraConfig convertido en vista tipada:** Todos los campos se derivan de `CONFIG`. `UraConfig.load()` internamente llama a `config_manager.load_config()`.
3. **`config.local.json` sin consumidores directos:** 0 ocurrencias en código. El archivo puede existir en disco pero emite deprecation warning.
4. **Eliminados helpers duplicados:** `get_ollama_urls` corregido, `_ollama_url()` eliminada.
5. **Test de consistencia:** `UraConfig.xxx == CONFIG["xxx"]` parametrizado y pasando al 100%.
6. **Sin regresiones:** `py_compile` ✅, `ruff` ✅ (0 nuevos), `pytest -q` sin cambios respecto al baseline.
7. **Documentación actualizada:** `CONFIGURATION.md`, `AGENTS.md`, `CONFIG_AUDIT.md`, closeouts afectados.
8. **Auditoría automática:** `scripts/audit_config.py` con 6 comprobaciones, todas pasando.
9. **Tag:** `git tag -a v0.17.0-fase17 -m "F17 — Unificación del sistema de configuración"`.

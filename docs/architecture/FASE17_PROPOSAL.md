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
    - Añadir `logging.warning("config.local.json encontrado — DEPRECATED. Será eliminado en F23.")` cuando el archivo exista y se cargue.
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

---

## Roadmap Post-F17

F17 es la primera fase de un plan de siete fases para llevar el proyecto a v1.0.0-rc.
Cada fase produce una capacidad completa y verificable. No se solapan migraciones grandes entre fases.

### Criterios de Paso entre Fases

Toda fase debe cumplir lo siguiente antes de abrir la siguiente:

| # | Requisito | Método |
|---|-----------|--------|
| 1 | `py_compile` 0 errores | `python3 -m py_compile` en todos los módulos tocados |
| 2 | Ruff 0 errores nuevos | `ruff check` — comparar con baseline de la fase |
| 3 | Pytest sin regresiones | `pytest -q` — mismo resultado que baseline |
| 4 | Benchmarks dentro del umbral | `scripts/benchmark_*.py` contra baseline de la fase anterior |
| 5 | Documentación actualizada | AGENTS.md, ADRs, closeout de la fase reflejan estado real |
| 6 | Working tree limpio | `git status` sin cambios sin commitear |
| 7 | Acta de cierre y tag | `docs/architecture/FASEX_CLOSEOUT.md` + `git tag -a vX.Y.Z-faseN` |

---

### F17.5 — Gestión de Secretos (NUEVA)

> **Depende de:** F17

**Objetivo:** Proveer un mecanismo único de secretos (API keys, tokens, endpoints) para que F18 pueda autenticarse contra múltiples proveedores sin duplicar lógica.

**Problema:** `motor/core/llm/` no tiene gestión de secretos — usa variables de entorno sueltas. `core/mochila/providers/` ya resuelve autenticación para OpenAI, Gemini, etc. pero con un patrón distinto. Sin un mecanismo compartido, F18 duplicará código de autenticación.

**Alcance:**
1. Crear `core/secrets.py` con un loader único que soporte:
   - Variables de entorno (`URA_OPENAI_KEY`, `URA_ANTHROPIC_KEY`, etc.)
   - Archivo `.env` en `URA_ROOT` (opcional, para desarrollo)
   - Fallback documentado si una clave falta
2. Mapear proveedores existentes:
   - Ollama → no requiere clave (URL local)
   - OpenAI → `OPENAI_API_KEY` / `URA_OPENAI_KEY`
   - Anthropic → `ANTHROPIC_API_KEY` / `URA_ANTHROPIC_KEY`
   - Gemini → `GEMINI_API_KEY` / `URA_GEMINI_KEY`
   - OpenRouter → `OPENROUTER_API_KEY` / `URA_OPENROUTER_KEY`
   - LM Studio → no requiere clave (URL local)
   - vLLM → no requiere clave (URL local)
3. Integrar con `core/config_manager.py` para que la sección `secrets` opcional en `system_config.json` pueda referenciar variables de entorno.
4. No cambiar la API de `core/mochila/providers/` — solo asegurar que el nuevo mecanismo es consistente.

**Archivos afectados:**
- `core/secrets.py` — nuevo archivo.
- `core/config_manager.py` — posible integración opcional.

**Riesgos:** Bajo. Es un módulo nuevo sin dependencias del resto del proyecto.

**Criterios de aceptación:**
- `core/secrets.py` retorna la clave correcta para cada proveedor.
- Si una clave no existe, retorna `None` y emite warning.
- Si todas las claves existen, 0 warnings.
- 0 cambios en módulos existentes.

**Validación:** `py_compile`, `ruff`, `pytest -q`.

---

### F18 — Cliente LLM Multiproveedor (Ollama + OpenAI)

> **Depende de:** F17, F17.5

**Objetivo:** Convertir `motor.core.llm` de cliente exclusivo de Ollama a router de proveedores. En esta fase solo se implementan Ollama (ya existe) y OpenAI (el más usado). El resto de proveedores se añaden en F22.

**Alcance:**

**B1 — Contrato común:**
Definir ABC/Protocolo con los métodos que todo proveedor debe implementar:
- `generate(prompt, model, options) → str`
- `generate_stream(prompt, model, options) → Iterator[str]`
- `embed(texts, model) → list[list[float]]`
- `embed_async(texts, model) → list[list[float]]`
- `health() → dict`

**B2 — Refactor proveedor Ollama:**
El cliente actual (`motor/core/llm/ollama.py`) pasa a implementar el contrato. No cambia su comportamiento.

**B3 — Nuevo proveedor OpenAI:**
Implementar el contrato contra la API de OpenAI (`/v1/chat/completions`, `/v1/embeddings`). Leer clave de `core/secrets.py`.

**B4 — Router:**
`motor/core/llm/__init__.py` expone las mismas funciones `generate()`, `embed()`, etc. pero internamente seleccionan el proveedor según `CONFIG["llm"]["provider"]`. Sin fallback automático aún (se añade en F19).

**B5 — Actualizar configuración:**
Añadir sección `llm.providers` en `system_config.json` para configurar cada proveedor (modelo por defecto, timeout, etc.).

**B6 — Tests:**
- Test de contrato: todos los proveedores implementan todos los métodos.
- Test de integración con OpenAI (requiere clave, se salta si no existe).
- Test de router: `provider="ollama"` usa el proveedor correcto.

**No incluye:**
- Fallback automático entre proveedores (pasa a F19).
- Anthropic, Gemini, OpenRouter, LM Studio, vLLM (pasan a F22).
- Streaming completo (solo firma, implementación básica).
- Benchmarks comparativos (pasan a F20).

**Archivos afectados:**
- `motor/core/llm/` — refactor completo.
- `core/config_manager.py` — nuevas claves de configuración.
- `core/secrets.py` — si se requieren ajustes.

**Riesgos:** Alto. Cambia la estructura interna de `motor/core/llm/` que ya tiene 4 consumidores directos. Mitigación: el contrato ABC garantiza que la API pública no cambia. Los tests de F15/F16 validan compatibilidad.

**Criterios de aceptación:**
- `motor.core.llm.generate()` funciona con Ollama (mismos resultados que antes).
- `motor.core.llm.generate()` funciona con OpenAI (clave presente).
- `provider="ollama"` en config → usa Ollama.
- `provider="openai"` en config → usa OpenAI.
- 0 cambios en consumidores de `motor.core.llm`.

**Validación:** `py_compile`, `ruff`, `pytest -q`. Smoke test: cambiar `provider` en config y verificar que responde.

---

### A1 — Contrato Estable de `motor.core.llm` (Ampliación transversal)

> **Ampliación de:** F18–F23
> **Prioridad:** Alta
> **Ejecución:** Inmediatamente después de F18, antes de F19

**Objetivo:** Congelar la API pública de `motor.core.llm` antes de que F19 (observabilidad) y F22 (más proveedores) añadan superficie de contacto. Garantizar que ningún consumidor accede a implementaciones internas.

**Problema:** Sin un contrato explícito, cada nuevo proveedor puede introducir variaciones sutiles en la API (parámetros opcionales, órdenes distintos, tipos de retorno ligeramente diferentes). La observabilidad de F19 envolverá `motor.core.llm` — si la API no es estable, las métricas serán frágiles.

**Alcance:**

1. **API pública documentada:**
   - `generate(prompt: str, model: str, options: dict | None = None) -> str`
   - `generate_stream(prompt: str, model: str, options: dict | None = None) -> Iterator[str]`
   - `embed(texts: list[str], model: str) -> list[list[float]]`
   - `embed_async(texts: list[str], model: str) -> list[list[float]]`
   - `health() -> dict`
   - Documentar en `docs/api/motor-core-llm.md`.

2. **Tests de contrato:**
   - Test parametrizado que verifica que cada proveedor existente implementa exactamente la misma firma.
   - Test que verifica que ningún consumidor importa clases internas (ej: `from motor.core.llm.ollama import OllamaProvider`).

3. **Versionado del contrato:**
   - El contrato (ABC/Protocolo) tiene un `__version__ = "1.0"`.
   - Cualquier cambio en la API pública incrementa la versión.
   - Los consumidores pueden declarar `requires = "motor.core.llm >= 1.0"`.

4. **Compatibilidad hacia atrás:**
   - Si un consumidor usa la API antigua (ej: llama a `generate()` sin `model`), debe seguir funcionando al menos una versión.
   - Deprecation warning con `FutureWarning` para APIs obsoletas.

**Archivos afectados:**
- `motor/core/llm/__init__.py` — exportar el contrato y versión.
- `motor/core/llm/protocol.py` — nuevo archivo con el ABC/Protocolo.
- `docs/api/motor-core-llm.md` — nuevo archivo de documentación.
- Cada proveedor existente — implementar el protocolo explícitamente.

**Riesgos:** Bajo. Cambios solo en la capa de interfaz, no en lógica de negocio.

**Criterios de aceptación:**
- Ningún consumidor accede a implementaciones internas de `motor.core.llm` (verificado por grep).
- Toda inferencia pasa por `motor.core.llm.generate()` o `motor.core.llm.embed()`.
- Tests de contrato pasan para todos los proveedores existentes.
- `motor.core.llm.__version__` está definido y es `"1.0"`.

**Validación:** `py_compile`, `ruff`, `pytest -q`, `grep` de imports internos.

---

### A2 — API Pública del Proyecto (Ampliación transversal)

> **Ampliación de:** F18–F23
> **Prioridad:** Alta
> **Ejecución:** Después de A1, antes de F19

**Objetivo:** Definir explícitamente qué paquetes forman parte de la API pública y cuáles son internos. Evitar que consumidores externos (scripts, tests, integraciones) dependan de módulos que puedan cambiar sin aviso.

**Alcance:**

1. **PUBLIC_API.md:**
   - Lista de módulos públicos soportados: `motor.core.llm`, `motor.core.config`, `core.config_manager`, `motor.pipeline`, `motor.intelligence.retrieval`, `motor.intelligence.reranking`, etc.
   - Lista de módulos internos (sin garantía de estabilidad): `motor.intelligence.agents.*`, `knowledge.engine.*`, `core.memoria.*`, `core.mochila.*`, `scripts.*`, etc.
   - Criterio de clasificación: un módulo es público si tiene tests que verifican su API y documentación asociada.

2. **Política de compatibilidad:**
   - Los módulos públicos siguen SemVer: cambios incompatibles requieren major version bump.
   - Los módulos internos pueden cambiar en cualquier minor/patch sin aviso.
   - Un módulo interno puede promoverse a público mediante ADR.

3. **Tests de validación:**
   - Test que verifica que ningún test/script importa directamente módulos marcados como internos.
   - Si un script necesita un módulo interno, debe hacerlo con un comentario `# noqa: INTERNAL` explícito.

**Archivos afectados:**
- `docs/api/PUBLIC_API.md` — nuevo archivo.
- `pyproject.toml` — posible configuración de exportaciones públicas.

**Riesgos:** Bajo. Solo documentación y clasificación.

**Criterios de aceptación:**
- `PUBLIC_API.md` existe y lista todos los módulos del proyecto.
- Ningún consumidor externo depende de módulos internos (verificado por test).
- Toda documentación futura referencia únicamente la API pública.

**Validación:** Revisión humana, test de imports.

---

### A3 — Política de Deprecación (Ampliación transversal)

> **Ampliación de:** F17–F23
> **Prioridad:** Alta
> **Ejecución:** Durante F17, antes de B2, para que las decisiones de deprecación tengan marco de referencia desde el inicio.

**Objetivo:** Formalizar el ciclo de vida de eliminación de componentes legacy antes de que F17-B2 (deprecación de `config.local.json`) y F23 (limpieza) necesiten aplicarlo.

**Alcance:**

1. **Ciclo de deprecación documentado:**
   - **Fase 1 — Deprecated**: Se emite `DeprecationWarning` (o `FutureWarning`) en tiempo de uso. El componente sigue funcionando. Se anuncia en release notes y docstring. Duración: al menos 2 versiones minor.
   - **Fase 2 — Unmaintained**: El componente existe pero no recibe correcciones. Se emite warning más severo (`PendingDeprecationWarning`). Duración: 1 versión minor.
   - **Fase 3 — Removed**: El componente se elimina. Si alguien lo necesita, debe usar la versión anterior.

2. **Casos de aplicación inmediata en el roadmap:**
   | Elemento | Deprecated en | Eliminación |
   |----------|---------------|-------------|
   | `config.local.json` | F17-B2 | F23-B1 |
   | `get_ollama_urls` alias | F17-B3 | F23-B1 |
   | `_ollama_url()` helper | F17-B3 | F23-B1 |
   | `UraConfig.load(path=...)` | F17-B5.1 | F23-B1 |
   | `config/loader.py` | F17-B6 | F23-B2 |
   | `_REQUIRED_KEYS` legacy keys | F17-B6 | F23-B2 |

3. **Regla general:**
   - Ningún elemento pasa de "activo" a "eliminado" sin pasar por "deprecated" al menos una versión.
   - Excepción: seguridad (vulnerabilidades críticas) puede saltarse la fase deprecated con ADR urgente.

**Archivos afectados:**
- `docs/architecture/DEPRECATION_POLICY.md` — nuevo archivo.
- `AGENTS.md` — referencia a la política.

**Riesgos:** Bajo. Política documental.

**Criterios de aceptación:**
- `DEPRECATION_POLICY.md` existe y define las 3 fases.
- Cada elemento legacy del roadmap tiene una fecha/fase de deprecación y eliminación asignadas.
- Los warnings de deprecación usan la categoría correcta de `warnings`.

**Validación:** Revisión humana.

---

### A4 — Benchmarks Automáticos (Ampliación transversal)

> **Ampliación de:** F20–F23
> **Prioridad:** Alta
> **Ejecución:** Después de F20 (necesita baseline de rendimiento)

**Objetivo:** Convertir los benchmarks existentes en un criterio objetivo de aceptación para cada cambio. Cualquier modificación que degrade el rendimiento por encima del umbral se rechaza automáticamente.

**Alcance:**

1. **Benchmarks unificados:**
   - **RAG**: retrieval (recuperación) + reranking + generación. Métricas: latencia p50/p95/p99, throughput, Recall@k.
   - **LLM**: `generate()` con distintos modelos y tamaños de prompt. Métricas: tokens/s, latencia, tasa de error.
   - **Embeddings**: `embed()` con distintos lotes. Métricas: textos/s, latencia.

2. **Ejecución automática:**
   - Comando único: `ura benchmark` (o `python3 -m motor.benchmark`).
   - Almacena resultado en `motor/data/benchmarks/<commit-hash>.json`.
   - Compara automáticamente contra el baseline de la rama `main`.

3. **Umbrales máximos de regresión:**
   | Métrica | Regresión máxima permitida |
   |---------|:--------------------------:|
   | Latencia p50 (LLM) | +15% |
   | Latencia p95 (LLM) | +20% |
   | Latencia p50 (RAG) | +15% |
   | Throughput (RAG) | -10% |
   | Recall@10 (RAG) | -0.02 |
   | Textos/s (embeddings) | -15% |

4. **Integración en CI:**
   - Los benchmarks se ejecutan en cada PR (o al menos antes de mergear a main).
   - Si algún umbral se supera, el PR se marca como "performance regression" y requiere revisión.
   - El informe JSON se adjunta como artefacto.

**Archivos afectados:**
- `motor/benchmark/` — nuevo paquete con runners unificados.
- `motor/cli/cmd_benchmark.py` — nuevo comando `ura benchmark` (o integrar en CLI existente).
- `motor/data/benchmarks/` — directorio de resultados.
- `pyproject.toml` — posible script `benchmark` en `[project.scripts]`.

**Riesgos:** Medio. Los benchmarks pueden ser frágiles en entornos con GPU compartida o modelos variables.

**Criterios de aceptación:**
- `ura benchmark` se ejecuta sin errores y produce un JSON con todas las métricas.
- La comparación contra baseline funciona: si no hay baseline, lo crea.
- Los umbrales están documentados y son configurables.
- Al menos un benchmark de cada tipo (RAG, LLM, embeddings) se ejecuta correctamente.

**Validación:** Ejecución manual de `ura benchmark` + inspección del JSON.

---

### F19 — Observabilidad y Fallback Automático

> **Depende de:** F18, A1, A2

**Objetivo:** Poder explicar exactamente qué hace URA en cada petición: qué proveedor, qué modelo, latencia, tokens, coste, errores. Añadir circuit breaker para failover entre proveedores.

**Alcance:**

**B1 — Métricas de LLM:**
- `motor/core/llm/metrics.py` — decorador o wrapper que registra:
  - Proveedor, modelo, latencia (ms), tokens (prompt + completion), error (o None), timestamp
- Exponer vía `ura.metrics.llm` como dict o lista de registros recientes.

**B2 — Métricas de Embeddings:**
- Mismas métricas para `embed()` y `embed_async()`.
- Timing por llamada, throughput (textos/segundo).

**B3 — Métricas de RAG:**
- Instrumentar el pipeline RAG (retrieval → reranking → context → generate):
  - Tiempo individual de cada etapa.
  - Número de documentos recuperados.
  - Score de reranking.
  - Tamaño del contexto construido.

**B4 — Trazabilidad por petición:**
- Cada petición entrante recibe un `request_id` (UUID).
- Las métricas de LLM, Embeddings y RAG se etiquetan con ese `request_id`.
- Al final: `request_id → { llm: [...], embeddings: [...], rag: {...}, total_ms }`.

**B5 — Circuit Breaker y Fallback:**
- Implementar circuit breaker por proveedor: si N errores consecutivos en ventana de tiempo, marcar como "degradado".
- `motor.core.llm.generate()`: si el proveedor principal falla y hay un fallback configurado, probar el siguiente.
- Configuración en `system_config.json`:
  ```json
  {
    "llm": {
      "provider": "ollama",
      "fallbacks": ["openrouter", "openai"],
      "circuit_breaker": {
        "max_failures": 3,
        "window_seconds": 60,
        "cooldown_seconds": 30
      }
    }
  }
  ```

**B6 — Exportadores:**
- **Prometheus**: `llm_request_duration_ms`, `llm_tokens_total`, `llm_errors_total`, `llm_provider_active` con labels `provider`, `model`.
- **JSON logging**: cada petición completa se loguea como una línea JSON estructurado con `request_id`, tiempos, proveedor, modelo, tokens, error.
- **No incluir** OpenTelemetry (demasiada dependencia para el estado actual. Se evalúa post-v1.0.0).

**Archivos afectados:**
- `motor/core/llm/` — nuevo subpaquete `metrics.py`, refactor de `generate()` para soportar fallback.
- `core/config_manager.py` — nuevas claves `llm.fallbacks`, `llm.circuit_breaker`.
- `motor/observability/` — posible integración con exportadores existentes.

**Riesgos:** Medio. La instrumentación no cambia comportamiento, pero añade overhead. El circuit breaker cambia el flujo de `generate()` — riesgo de regression.

**Criterios de aceptación:**
- `ura.metrics.llm` contiene al menos 1 registro después de llamar a `generate()`.
- Cada registro tiene `provider`, `model`, `latency_ms`, `tokens`, `error`.
- Circuit breaker: si el proveedor principal falla N veces, se usa el fallback.
- Exportador Prometheus responde en `/metrics`.
- JSON logging produce una línea por petición.
- 0 regresiones en tests existentes.

**Validación:** `py_compile`, `ruff`, `pytest -q`. Smoke test: ejecutar pipeline, verificar métricas.

---

### F20 — Optimización de Rendimiento

> **Depende de:** F19

**Objetivo:** Reducir latencia sin modificar resultados. No optimizar sin medir primero — F19 proporciona las métricas baseline, F20 actúa sobre ellas.

**Alcance:**

**B1 — Profiling obligatorio:**
Antes de cualquier optimización, ejecutar:
- `cProfile` o `py-spy` en un pipeline completo (pregunta → respuesta).
- Identificar top 3 cuellos de botella por tiempo absoluto.
- Documentar baseline de latencia (p50, p95, p99) usando las métricas de F19.

**B2 — Caché:**
- **Caché de embeddings**: textos repetidos dentro de una ventana de tiempo no se re-embedden. TTL configurable.
- **Caché de contexto**: fragmentos de documentos ya recuperados no se recuperan de nuevo en la misma sesión.
- **Caché de respuestas deterministas**: misma pregunta + mismo contexto → misma respuesta (si `temperature=0.0`). Hash del prompt como clave.

**B3 — Batching:**
- Embeddings por lote (`embed( textos[:batch_size] )`) donde antes se hacían llamadas individuales.
- Si el proveedor lo soporta, enviar múltiples generaciones en paralelo (OpenAI permite varios `n` en una llamada).

**B4 — Streaming:**
Los consumidores que puedan recibir streaming (`generate_stream()`) deben hacerlo. No acumular la respuesta completa en memoria antes de entregarla.

**B5 — Paralelización:**
- Retrieval y reranking pueden ejecutarse en paralelo (sus entradas no dependen entre sí).
- Context builder puede empezar antes de que termine el reranking si se usa un índice parcial.

**B6 — Reducción de overhead:**
- Eliminar copias innecesarias de datos entre etapas del pipeline.
- Reducir serialización/deserialización JSON entre módulos que ya comparten memoria.
- Consolidar llamadas HTTP: si dos módulos necesitan el mismo embedding, usar el caché en lugar de llamar dos veces.

**Archivos afectados:**
- `motor/core/llm/` — añadir caché.
- `motor/intelligence/retrieval/` — paralelización.
- `motor/intelligence/reranking/` — paralelización.
- `motor/intelligence/memory/` — caché de contexto.
- `core/config_manager.py` — nueva sección `llm.cache`.

**Riesgos:** Medio. La caché puede servir respuestas stale si el TTL es incorrecto. Paralelización puede incrementar uso de recursos.

**Criterios de aceptación:**
- Las métricas de F19 muestran mejora de al menos 20% en p50 (o el objetivo concreto definido en profiling).
- Caché: llamada repetida dentro del TTL → 0 llamadas HTTP al proveedor.
- Batching: embeddings procesan N textos en 1/N llamadas.
- 0 cambios en resultados (verificado por golden tests de F21 o tests existentes).

**Validación:** `py_compile`, `ruff`, `pytest -q`. Benchmark contra baseline de F19.

---

### F21 — Calidad y Validación Continua

> **Depende de:** F19, F20

**Objetivo:** Evitar regresiones funcionales mediante un sistema de validación automática que compare cada cambio contra un baseline conocido.

**Alcance:**

**B1 — Golden Tests:**
- Conjunto de 20-50 preguntas de referencia con respuestas esperadas (o criterios de aceptación).
- Cada pregunta se ejecuta contra el pipeline completo.
- La respuesta se compara contra la respuesta de referencia usando un judge LLM (o métrica de similitud semántica).
- Falla si la respuesta se desvía más de un umbral configurable.

**B2 — Benchmarks Automáticos:**
- Integrar los benchmarks existentes (`scripts/pro/benchmark_*.py`) en un comando único: `ura benchmark`.
- Almacenar resultados en `motor/data/benchmarks/` con timestamp y commit hash.
- Comparar automáticamente contra el baseline de la fase anterior.

**B3 — Métricas de Calidad RAG:**
- **Recall@k**: fracción de documentos relevantes recuperados en top-k.
- **MRR** (Mean Reciprocal Rank): posición del primer documento relevante.
- **MAP** (Mean Average Precision): precisión promedio en todos los documentos relevantes.
- **nDCG** (Normalized Discounted Cumulative Gain): calidad del ranking con ganancia acumulada.
- Corpus de evaluación de ≥200 consultas con juicios de relevancia.

**B4 — Métricas de Calidad LLM:**
- **Consistencia**: misma pregunta con `temperature=0.0` produce la misma respuesta.
- **Alucinaciones**: el judge LLM verifica que la respuesta está soportada por el contexto recuperado.
- **Precisión factual**: comparación contra fuentes conocidas.

**B5 — Smoke Test E2E:**
- Un test que ejecuta el pipeline completo con cada proveedor disponible (Ollama, OpenAI).
- Verifica que respuesta no está vacía, no contiene errores, y cumple con el formato esperado.
- Se ejecuta en CI.

**B6 — Integración en CI:**
- Los golden tests se ejecutan en cada PR.
- Los benchmarks se ejecutan en cada merge a main.
- La comparación contra baseline se publica como comentario en el PR.

**Archivos afectados:**
- `tests/golden/` — nuevo directorio con preguntas de referencia.
- `motor/cli/cmd_benchmark.py` — nuevo comando `ura benchmark`.
- `.github/workflows/` — CI pipeline (o script equivalente).
- Varios módulos de test existentes que se actualizan para usar las nuevas métricas.

**Riesgos:** Medio. Depende de un judge LLM que puede ser costoso y tener sus propios falsos positivos. Los golden tests requieren mantenimiento.

**Criterios de aceptación:**
- `ura benchmark` se ejecuta sin errores y produce un informe.
- Golden tests: ≥90% de las preguntas pasan (o el umbral definido).
- Smoke test E2E pasa con Ollama y OpenAI.
- Corpus de evaluación de ≥200 consultas con juicios de relevancia.

**Validación:** Ejecutar `ura benchmark`, golden tests, smoke E2E.

---

### F22 — Proveedores Adicionales

> **Depende de:** F18, F19, F20

**Objetivo:** Añadir todos los proveedores del roadmap al cliente multiproveedor.

**Alcance:**
Implementar el contrato de F18 para:

| Proveedor | API | Autenticación | Prioridad |
|-----------|-----|---------------|:---------:|
| **Anthropic** | `/v1/messages` | `ANTHROPIC_API_KEY` vía `core/secrets.py` | Alta |
| **Gemini** | `/v1/models/{model}:generateContent` | `GEMINI_API_KEY` vía `core/secrets.py` | Alta |
| **OpenRouter** | `/v1/chat/completions` | `OPENROUTER_API_KEY` vía `core/secrets.py` | Media |
| **LM Studio** | `/v1/chat/completions` (local) | No requiere clave | Media |
| **vLLM** | `/v1/chat/completions` (local) | No requiere clave | Baja |

**Archivos afectados:**
- `motor/core/llm/providers/anthropic.py` — nuevo.
- `motor/core/llm/providers/gemini.py` — nuevo.
- `motor/core/llm/providers/openrouter.py` — nuevo.
- `motor/core/llm/providers/lm_studio.py` — nuevo.
- `motor/core/llm/providers/vllm.py` — nuevo.
- `core/secrets.py` — añadir mapeo para nuevos proveedores.

**Riesgos:** Bajo. Cada proveedor es un archivo nuevo que implementa un contrato conocido. No hay cambios en el resto del sistema.

**Criterios de aceptación:**
- Cada proveedor implementa el contrato completo (`generate`, `generate_stream`, `embed`, `embed_async`, `health`).
- Cada proveedor tiene test unitario (mockeando HTTP).
- Al menos 2 proveedores verificados con integración real.
- `provider="anthropic"` en config funciona.
- Fallback configurable entre cualquier par de proveedores.

**Validación:** `py_compile`, `ruff`, `pytest -q`. Smoke test con cada proveedor disponible.

---

### F23 — Limpieza y v1.0.0-rc

> **Depende de:** F17, F17.5, F18, F19, F20, F21, F22

**Objetivo:** Eliminar toda la deuda técnica restante y producir el primer Release Candidate.

**No es v1.0.0 final.** Es un RC para validación externa. Las correcciones posteriores determinan cuándo promover a v1.0.0 estable.

**Alcance:**

**B1 — Eliminar compatibilidad temporal:**
- Eliminar `config.local.json` completamente (estaba deprecated desde F17-B2).
- Eliminar alias `get_ollama_urls` si se añadió en F17-B3.
- Eliminar `_ollama_url()` si no se eliminó antes.
- Eliminar carga directa de JSON en `UraConfig.load()` (parámetro `path`, env var `URA_CONFIG`).

**B2 — Eliminar código muerto confirmado:**
- Revisar `config/loader.py` — si es redundante, eliminar.
- Eliminar cualquier helper de URL de Ollama duplicado.
- Eliminar `_REQUIRED_KEYS` legacy en `config_manager.py`.

**B3 — Actualizar documentación final:**
- `ARCHITECTURE.md` completo y actualizado.
- `AGENTS.md` refleja el estado real del proyecto.
- ADRs relevantes actualizados (especialmente ADR-007 sobre el core).
- `CONFIGURATION.md` describe la arquitectura final.
- `API.md` / `PUBLIC_API.md` documenta la API pública.
- `DEPRECATION_POLICY.md` describe el ciclo de vida legacy.

**B4 — Auditoría final automática:**
- Extender `scripts/audit_config.py` (de F17-B6.5) para que verifique:
  - 0 duplicación de configuración.
  - 0 imports muertos.
  - 0 HTTP directo a proveedores (todo pasa por `motor.core.llm`).
  - 0 constantes de URL duplicadas.
  - 0 código huérfano (módulos sin imports).

**B5 — Tag v1.0.0-rc:**
- `git tag -a v1.0.0-rc1 -m "v1.0.0-rc1 — Release Candidate"`
- Crear release notes con resumen de F17→F23.

**B6 — Criterios de salida hacia v1.0.0-rc:**
Antes de etiquetar la RC, deben cumplirse todos estos criterios:

| Área | Criterio | Verificado por |
|------|----------|----------------|
| Configuración | Fuente única de verdad (`system_config.json`) | B6.5, F23-B4 |
| LLM | API congelada y versionada (`motor.core.llm.__version__ == "1.0"`) | A1 |
| Observabilidad | Cobertura completa (LLM, embeddings, RAG, request_id) | F19-B1..B4 |
| Secretos | Sin credenciales en código (todo vía `core/secrets.py` o env vars) | F17.5 |
| Rendimiento | Sin regresiones frente a baseline (umbrales A4) | A4 |
| Calidad | Golden tests ≥90% passing, métricas RAG estables | F21 |
| Documentación | ADRs, `PUBLIC_API.md`, `DEPRECATION_POLICY.md`, `AGENTS.md` sincronizados | A2, A3, F23-B3 |
| Deuda técnica | Sin elementos legacy activos (`config.local.json`, loaders duplicados, helpers legacy) | F23-B1, B2, B4 |

Si algún criterio no se cumple, la RC se retrasa hasta que se corrija. No se etiqueta una RC con deuda técnica conocida.

**Archivos afectados:** Varios (limpieza).

**Riesgos:** Bajo. Solo eliminación. Todo debería funcionar sin el código legacy.

**Criterios de aceptación:**
- `config.local.json` no existe en disco ni en código.
- Auditoría automática: 6 comprobaciones pasan.
- 0 regresiones.
- Working tree limpio.
- Release notes publicadas.

**Validación:** `py_compile`, `ruff`, `pytest -q`, `scripts/audit_config.py`.

---

## Resumen del Roadmap

| Prioridad | Fase | Objetivo | Esfuerzo | Depende de | Estado |
|:---------:|------|---------|:--------:|------------|:------:|
| **Alta** | **F17** | Configuración unificada | 13-21h | F16 | Pendiente |
| **Alta** | **F17.5** | Gestión de secretos | 2-4h | F17 | Pendiente |
| **Alta** | **F18** | Cliente multiproveedor (Ollama + OpenAI) | 15-20h | F17, F17.5 | Pendiente |
| **Alta** | *A1* | *Contrato estable de motor.core.llm* | *4-6h* | *F18* | *Pendiente* |
| **Alta** | *A2* | *API pública del proyecto* | *3-5h* | *F18, A1* | *Pendiente* |
| **Alta** | *A3* | *Política de deprecación* | *2-3h* | *F17* | *Pendiente* |
| **Alta** | **F19** | Observabilidad, fallback y circuit breakers | 15-20h | F18, A1, A2 | Pendiente |
| **Media** | **F20** | Rendimiento y profiling | 15-25h | F19 | Pendiente |
| **Media** | *A4* | *Benchmarks automáticos* | *6-10h* | *F20* | *Pendiente* |
| **Media** | **F21** | Calidad RAG/LLM | 20-30h | F19, F20, A4 | Pendiente |
| **Media** | **F22** | Proveedores adicionales | 15-25h | F18, F19, F20, A1, A2 | Pendiente |
| **Baja** | **F23** | Limpieza y v1.0.0-rc | 8-15h | F17-F22, A3, A4 | Pendiente |
| | | **Total** | **118-184h** | | |

### Orden Estratégico

1. **F17 + F17.5 + A3**: Consolidar arquitectura, secretos y política de deprecación de una vez. A3 (política) debe ir antes de F17-B2 para que las decisiones de deprecación tengan marco de referencia desde el inicio. Las tres comparten dependencia de F16 y no requieren componentes posteriores.
2. **F18**: Router básico con los 2 proveedores más usados. Sin fallback, sin métricas.
3. **A1 + A2**: Congelar contrato de `motor.core.llm` (A1) y definir API pública del proyecto (A2) antes de que F19 y F22 añadan más superficie. Sin esto, observabilidad y nuevos proveedores introducirán API drifting.
4. **F19**: Observabilidad + circuit breaker (necesitas métricas para decidir fallback, contrato estable para instrumentar, y API pública documentada para exportar métricas).
5. **F20**: Rendimiento (necesitas métricas baseline de F19 para medir mejora).
6. **A4**: Benchmarks automáticos sobre el baseline de F20. Sin esto, F21 no tiene umbrales objetivos.
7. **F21**: Calidad (necesitas pipeline rápido de F20 + benchmarks de A4 para golden tests y detección de regresiones).
8. **F22**: Resto de proveedores (después de tener calidad + rendimiento estables).
9. **F23**: Limpieza final y RC (después de cerrar todas las fases funcionales, con criterios de salida verificados).

Este orden minimiza el riesgo: primero arquitectura + gobernanza, después capacidades, luego contratos, observabilidad, rendimiento, benchmarks, calidad, cobertura de proveedores, y finalmente limpieza pre-release con criterios objetivos.

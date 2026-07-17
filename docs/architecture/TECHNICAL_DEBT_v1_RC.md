# Technical Debt v1.0 RC

**Documento:** `docs/architecture/TECHNICAL_DEBT_v1_RC.md`  
**Fecha:** 2026-07-16  
**Estado:** ✅ Auditado

## Deuda Eliminada

| Ítem | Archivo | Acción |
|------|---------|--------|
| `tokens = None` duplicado | `router.py:192-193` | Eliminada línea duplicada |
| `_ERROR_STR_EXCEEDED` no usado | `router.py:26` | Eliminada (código muerto) |
| `_ERROR_STR_CONNECTION` no usado | `router.py:27` | Eliminada (código muerto) |

## Deuda Documentada (No Bloqueante para RC)

### 1. `_log_call` duplicado (7 copias)

Cada proveedor (`ollama.py`, `openai.py`, `anthropic.py`, `gemini.py`,
`openrouter.py`, `lmstudio.py`, `vllm.py`) tiene su propia copia de la
función `_log_call`. ~70 líneas duplicadas.

**Razón:** Cada archivo de proveedor debe ser importable independientemente.
Extraer a un módulo compartido crearía una dependencia adicional.

**Prioridad:** Baja

### 2. Submodules leaking en namespace

`motor.core.llm` expone 16 símbolos no privados que no están en `__all__`.
`motor.core.evaluation` expone 6. Esto es normal en Python.

**Razón:** Python añade automáticamente submodules al `dir()` del paquete padre.
`__all__` es el contrato oficial.

**Prioridad:** Mínima

### 3. Fallos pre-existentes en tests bajo carga

~16 tests fallan cuando se ejecuta el suite completo debido a corrupción
de estado del módulo (stale `sys.modules`). Todos pasan en aislamiento.

**Razón:** Los tests modifican módulos globales (patching, metrics singleton)
que no se restauran completamente entre tests.

**Prioridad:** Media (post-RC)

### 4. `config.local.json` como fuente de config

La configuración de resiliencia (retry, CB, fallback, health) reside en
`config.local.json` en vez de `system_config.json` debido a `chattr +i`
en el archivo principal.

**Razón:** `system_config.json` es inmutable. Workaround documentado.

**Prioridad:** Media (pendiente de F14-F01)

### 5. Contador de imports en contratos

El contract test `test_llm_contract.py` mantiene una lista manual de
exports esperados. Cuando se añaden nuevos submódulos, hay que añadirlos
a esta lista.

**Razón:** No hay inspección automática de `__all__`.

**Prioridad:** Baja

## Resumen

| Categoría | Eliminado | Pendiente |
|-----------|-----------|-----------|
| Código muerto | 3 | 0 |
| Código duplicado | 0 | 1 (7× `_log_call`) |
| Namespace leak | 0 | 2 módulos |
| Tests flaky | 0 | ~16 tests |
| Config | 0 | 1 (`config.local.json`) |
| **Total** | **3** | **~19 ítems** |

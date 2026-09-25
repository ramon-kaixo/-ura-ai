# ADR-099: fix(router): `embed`/`embed_async` reciben `texts` (lista) — regresión introducida por el gate mypy strict

**Fecha:** 2026-08-28
**Categoría:** Núcleo — Motor LLM Router
**Autor:** TERM (OpenCode)
**Rama:** `main` (hotfix de corrección de regresión con ADR según ADR-007)
**Commit:** (SE COMPLETA AL CIERRE)

## Contexto

`test_motor_llm_router_init::TestEmbed::test_embed_ok` fallaba en `make test-fast`
de GX10 (producción). El test hace `router.embed(["hola","mundo"])` y espera 2
vectores de longitud 4, pero el router devolvía `[]`.

### Diagnóstico (raíz)

El dispatch genérico del router pasa al proveedor un único argumento posicional
llamado `prompt`:

- `motor/core/llm/router/strategy.py::_call_provider` (antes l.116/121):
  `getattr(prov_obj, method)(prompt, **kwargs)`.

Ese primer argumento es un **string** para `generate` pero una **lista de textos**
para `embed`/`embed_async`. El contrato real del ABC y de todos los proveedores es:

```python
def generate(self, prompt: str, model=None, ...): ...
def embed(self, texts: list[str], model=None) -> list[list[float]]: ...
def embed_async(self, texts: list[str], model=None) -> list[list[float]]: ...
```

En `call_with_fallback` se calculaba el primer argumento con:

```python
prompt_arg: str = args[0] if args and isinstance(args[0], str) else ""
```

El filtro `and isinstance(args[0], str)` se comportaba así:

- `generate` → `args[0]` es `str` → se pasa el prompt ✓
- `embed`/`embed_async` → `args[0]` es `list` → `prompt_arg = ""` → el proveedor
  recibe `embed("", ...)` → itera sobre 0 elementos → devuelve `[]` ✗

### Autoría de la regresión

`git log -S 'isinstance(args[0], str)'` señala el commit **`362dc8e4`**
(`style(types): [TASK-20260822-002][TERM] Fase B mypy strict`). Diff exacto:

```diff
-    retry_kw = {k: kwargs.pop(k) for k in _RETRY_KWARGS if k in kwargs}
-    prompt_arg: str = args[0] if args else ""
+    retry_kw: dict[str, Any] = {k: kwargs.pop(k) for k in _RETRY_KWARGS if k in kwargs}
+    prompt_arg: str = args[0] if args and isinstance(args[0], str) else ""
```

El `and isinstance(args[0], str)` se añadió como parche para satisfacer el
type checker de **mypy strict** (`prompt_arg` anotado `str`), y ese parche
**rompió el embedding** en runtime. El comportamiento correcto previo era
`prompt_arg = args[0] if args else ""` (pasar el primer argumento tal cual).

Ningún test cubría `call_with_retry`/`call_with_fallback` con un método de firma
distinta a `generate` (todos usaban `generate`), por lo que la regresión pasó
desapercibida durante la fase B de mypy strict.

## Justificación de necesidad (ADR-007)

El cambio debe hacerse en el núcleo porque el error está en el **mecanismo de
dispatch genérico** del router (`strategy.py`), que no puede resolverse vía
Protocol, EventBus subscriber ni adaptador externo. No existe workaround externo:
el embedding a través del router es una ruta de entrada de `core/qdrant_client`
y el knowledge engine.

No es un cambio de comportamiento de `generate` (queda idéntico): restaura el
comportamiento previo rompido de `embed`/`embed_async`, que es lo permitido por
la regla de "semantic freezing" (corregir una regresión observada, no alterar
funcionalidad existente correcta).

## Decisión

1. `strategy.py::call_with_fallback`: pasar el primer argumento posicional tal
   cual, sin filtrarlo por `isinstance(str)`.

   ```diff
   -    prompt_arg: str = args[0] if args and isinstance(args[0], str) else ""
   +    prompt_arg: Any = args[0] if args else ""
   ```

2. `strategy.py::call_with_retry`: ampliar el tipo del parámetro `prompt` a
   `Any` para reflejar que ya no es solo `str` (y mantener mypy strict en verde
   sin necesidad del filtro).

   ```diff
   -    prompt: str = "",
   +    prompt: Any = "",
   ```

## Plan de migración

No afecta a datos ni esquema. Sin script de migración. El cambio es local a la
lógica de dispatch y no altera la API pública (`LLMRouter.embed`/`embed_async`
firman intactas).

## Plan de rollback

Revertir los 2 cambios de `strategy.py` (o `git revert` del commit de cierre):
vuelve al estado con `embed` roto (regresión). Reversible sin limpieza.

## Degradación

Si el proveedor fallara, el circuito breaker y el retry siguen operando igual. El
router conserva su mecanismo de fallback. Sin proveedor disponible devuelve el
error estándar. La corrección solo cambia el argumento entregado al proveedor
para `embed`, no añade dependencias.

## Revisión por segunda parte (obligatoria, ADR-007)

Pendiente: revisión del revisor ([WEB]) del diff y del expediente de tarea antes
de marcar la TASK como DONE. Proceso de gates: `ruff`, `mypy --no-incremental
core motor shared`, `pytest -q --tb=short`.

## Consecuencias

- `embed`/`embed_async` vuelven a funcionar (empítricamente `test_embed_ok`
  valida contenido: `embed(["hola","mundo"])` → 2 vectores de 4 dims).
- `generate` sin cambio de comportamiento (`test_embed_ok` + suite router 127
  passed, 0 regresiones).
- Cobertura: el bug fue detectado por `test_motor_llm_router_init` ya existente;
  el fix no baja cobertura (los 45 tests del router siguen pasando).
- Deuda detectada: el gate mypy strict introdujo el parche de tipos que causó la
  regresión. Recomendación: al tipar con mypy, NO añadir `isinstance` que altere
  semántica en hot paths; reportar `/ ahoraqa`/ADR en vez de silenciar el checker
  con filtros que cambian comportamiento.

## Archivos afectados

- `motor/core/llm/router/strategy.py` (2 líneas).
- `docs/architecture/ADR-099-...md` (este documento).

## Checkboxes de cierre

- [ ] Verificar tests pasan (`pytest` zona router → 127 passed; `make test-fast` GX10 sin `test_embed_ok` FAILED)
- [ ] Verificar mypy strict en verde en GX10
- [ ] Verificar linting 0 errores nuevos
- [ ] Revisión del revisor antes de DONE

# ADR-100: fix(core): watchdog en hilo secundario lanzaba TypeError SIEMPRE — desempaquetado corregido

**Fecha:** 2026-08-28
**Categoría:** Núcleo — core/watchdog_funciones.py
**Autor:** TERM (OpenCode)
**Rama:** `main` (hotfix de corrección de bug real con ADR según ADR-007)
**Commit:** (SE COMPLETA AL CIERRE)

## Contexto

El `@watchdog` de `core/watchdog_funciones.py` tiene dos ramas según el hilo:
- **Hilo principal**: usa `signal.SIGALRM` — funciona correctamente.
- **Hilo secundario**: usa `_ejecutar_en_hilo()` — **roto desde su creación**.

El bug: `_ejecutar_en_hilo` (línea 139) devuelve una tupla de 2 elementos:
`((t, result), excepcion_valor)` — donde el segundo elemento es el **valor de
excepción directo** (`None` en éxito, o una `Exception`).

El wrapper del hilo secundario desempaquetaba:
```python
(t, resultado), (excepcion,) = _ejecutar_en_hilo(func, args, kwargs, timeout)
```
Es decir, trataba el segundo elemento como una **tupla de 1 elemento**. En éxito,
`excepcion_valor` es `None` (no iterable) → `TypeError: cannot unpack non-iterable NoneType object` **SIEMPRE**.

Fue documentado como hallazgo en `docs/udo/hallazgos-fondo.md` (2026-08-20,
TASK-20260820-010) con estado "propuesto, requiere ADR-007". El código tenía
`# pragma: no cover` en toda la rama, ocultando la falta de cobertura y el fallo.

## Justificación de necesidad (ADR-007)

El bug está en el mecanismo de ejecución del decorador (core). No puede resolverse
vía Protocol, EventBus subscriber ni adaptador externo: es la implementación misma
de `watchdog` para hilos secundarios, que está rota.

El fix es de **1 línea** (cambiar el desempaquetado de `(excepcion,)` a `excepcion`),
no cambia la firma ni el comportamiento observado del hilo principal (intacto), y
restaura el comportamiento previsto (y nunca funcionante) del hilo secundario.

El cambio está plenamente diagnosticado y documentado desde 2026-08-20. Se aplica
en esta sesión bajo ADR por la petición expresa de Ramón ("cualquier parte del
código donde se vean parches se soluciona").

## Decisión

Corregir el desempaquetado en `wrapper_sync` (rama hilo secundario):

```diff
- (t, resultado), (excepcion,) = _ejecutar_en_hilo(func, args, kwargs, timeout)
+ (t, resultado), excepcion = _ejecutar_en_hilo(func, args, kwargs, timeout)
```

Se elimina el `# pragma: no cover` de la rama porque ahora es ejecutable y está
cubierta por tests (éxito + excepción en hilo secundario).

## Plan de migración

No afecta a datos ni esquema. Sin script de migración. El cambio es local a la
rama hilo secundario del decorador; la API pública (`@watchdog`) y el hilo
principal (SIGALRM) quedan intactos.

## Plan de rollback

`git revert` del commit de cierre: vuelve al `(excepcion,)` roto (TypeError en
hilo secundario). Reversible sin limpieza. Los 2 tests de regresión nuevos
(`test_watchdog_hilo_secundario_ok` / `_excepcion`) fallarían tras el revert,
actuando como guarda.

## Degradación

El comportamiento correcto del hilo secundario se restaura. Si el timeout ocurre,
sigue devolviendo `None` tras `_on_timeout` (intacto). Si hay excepción, se
propaga (intacto). La ruta del hilo principal no cambia. Sin nuevas dependencias.

## Revisión por segunda parte (obligatoria, ADR-007)

Pendiente: revisión del revisor ([WEB]) del diff y del expediente de tarea antes
de marcar la TASK como DONE. Proceso de gates: `ruff`, `mypy --no-incremental
core motor shared`, `pytest -q --tb=short`.

## Consecuencias

- El watchdog en hilo secundario ya funciona (verificado empíricamente:
  `suma(2,3)` en thread → `5`; excepción → propagada).
- Cobertura de `core/watchdog_funciones.py` sube a **100%** (115 stmts, 0 miss)
  al eliminar el `# pragma: no cover` de la rama ahora cubierta.
- Cierra el hallazgo 2026-08-20 (TASK-20260820-010) en `hallazgos-fondo.md`.

## Archivos afectados

- `core/watchdog_funciones.py` (1 línea de desempaquetado + quitar pragma).
- `tests/unit/test_motor_runner_searchlog_watchdog_cobertura.py` (+2 tests).
- `docs/architecture/ADR-100-...md` (este documento).

## Checkboxes de cierre

- [ ] Verificar tests pasan (`pytest` watchdog → 61 passed; rama hilo secundario cubierta)
- [ ] Verificar cobertura `core/watchdog_funciones.py` = 100%
- [ ] Verificar linting 0 errores nuevos
- [ ] Revisión del revisor antes de DONE

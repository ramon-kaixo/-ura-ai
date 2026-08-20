# ADR-038: División de tests de cobertura largos en submódulos (Consolidación Fase 4)

> **Fecha:** 2026-08-20
> **Propósito:** Reducir archivos de test >900 líneas manteniendo cobertura y no-regresión
> **Estado:** ✅ Aprobado (ejecutado, commits `59a0b56e`, `1a54bd65`, `64c2f45c`, `f9a716b9`)

## Contexto

4 archivos de test de cobertura superaban las 900 líneas (hasta 1189),
dificultando el mantenimiento y la revisión. El plan de consolidación exige
archivos de test razonables y legibles.

## Decisión

Dividir cada archivo en 2-3 archivos por dominio funcional + 1 módulo de
helpers compartido (`_<nombre>_helpers.py`), con estas reglas:

1. Los helpers/fixtures viven en el módulo `_*_helpers.py`.
2. Los splits importan solo los símbolos que usan (imports explícitos).
3. Fixtures importadas usadas como parámetros de test → `# noqa: F811`
   (patrón legítimo).
4. Los re-exports del módulo de helpers llevan `# noqa: F401` (los splits los
   usan, ruff no lo sabe).
5. La suma de tests de los splits debe ser EXACTAMENTE igual al original
   (no-regresión verificada por conteo de colección).

| Original | Líneas | Splits | Tests |
|----------|--------|--------|-------|
| test_fase7.py | 1026 | fts5/recovery/reconcile | 48 |
| test_mochila_server_cobertura.py | 1189 | scheduler/guardian/router | 84 |
| test_extraction_service_cobertura.py | 940 | queue/procesar/loop | 61 |
| test_motor_qdrant_client.py | 927 | conectar/buscar/instancia | 84 |

## Lecciones registradas (para futuros splits)

- `import *` no exporta nombres con underscore → import explícito de privados.
- El `--fix` de ruff sobre módulos de helpers BORRA re-exports → usar noqa F401.
- Cuidado con off-by-one al cortar por líneas; verificar con `--collect-only`.

## Impacto

- 277 tests en 12 splits, 0 regresiones (mismo conteo que los 4 originales).
- Ruff limpio, sin cambios en cobertura medida.

## Reversibilidad

`git revert` de los 4 commits restaura los archivos originales.
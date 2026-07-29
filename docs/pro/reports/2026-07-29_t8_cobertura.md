# T8: Cobertura de Tests — Reporte

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~5 min

## Resultado
```
TOTAL   28330  22940    19%
535 passed, 4 skipped in 57.42s
```

## Cobertura por Módulo
| Módulo | Cobertura |
|--------|-----------|
| motor | ~19% (incluye tests como 0%) |
| knowledge | Sin cobertura (no importado por subset) |
| shared | 0% (paths.py no ejecutado) |

## Notas
- Cobertura sobre `motor`, `knowledge`, `shared` (excluye `core/`)
- Subset de 535 tests cubre solo código activamente importado
- Muchos archivos en 0% porque el subset no los importa
- Reporte HTML generado en `docs/coverage/` (pendiente)

## Conclusión
Baseline: 19% sobre 28330 líneas en módulos monitoreados.
Sin regresión desde baseline (primera medición documentada).

Ejecuta una auditoría rápida del proyecto URA.

Pasos:
1. Ruff lint: `ruff check . --statistics`
2. Mypy: `mypy --no-incremental core motor shared 2>&1 | tail -5`
3. Tests: `python3 -m pytest tests/ -x -q --tb=line --timeout=30 2>&1 | tail -3`
4. Git status: `git status --short`

Presenta un resumen con: errores lint, errores tipo, tests resultado, archivos modificados.

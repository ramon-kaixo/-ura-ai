# URA — Proyecto de Orquestación Multi-Agente

## Comandos
- Ejecutar todos los tests: `pytest`
- Ejecutar test específico: `pytest tests/test_archivo.py::test_funcion`
- Lint: `ruff check .`
- Formatear: `ruff format .`
- Type checking: `mypy .`

## Estilo de código
- Python 3.11+
- Type hints obligatorios en todas las funciones.
- Docstrings en formato Google.
- Imports: estándar → terceros → local (un espacio entre grupos).
- Manejo de excepciones explícito (no usar `except Exception` sin más).
- Nombres: `snake_case` para funciones/variables, `CamelCase` para clases.
- Máximo 88 caracteres por línea.
- Usar `logging` en lugar de `print`.

## Estructura del proyecto
- `motor/orchestration/` → lógica de orquestación (API, workers, cola).
- `motor/core/` → utilidades y lógica compartida.
- `scripts/pro/` → scripts de producción y mantenimiento.
- `tests/` → tests unitarios y de integración.

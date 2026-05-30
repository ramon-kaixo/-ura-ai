---
description: Ejecutar tests de URA
---

Ejecuta todos los tests del proyecto URA.

## Pasos

1. Ejecutar tests unitarios
```bash
python -m pytest tests/ --cov=core --cov-report=html
```

2. Ejecutar tests de integración
```bash
python -m pytest tests/integration/ -v
```

3. Verificar cobertura
```bash
python scripts/coverage_report.py
```

## Opciones adicionales

Solo tests específicos:
```bash
pytest tests/test_specific.py -v
```

Tests con markers:
```bash
pytest -m "not slow"
```

Ver reporte HTML:
```bash
open htmlcov/index.html
```

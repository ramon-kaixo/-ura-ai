# Guía de contribución a URA

## Ramas
- `main`: solo código probado y estable.
- `develop`: integración continua.
- `feature/*`: nuevas funcionalidades.
- `fix/*`: corrección de errores.

## Commits atómicos
- Un commit por cambio lógico.
- Mensaje claro: tipo(ámbito): descripción (ej. `fix(api): corregir import circular`).

## Pull Requests
- Toda modificación de `main` debe hacerse mediante PR.
- Requiere al menos una revisión de otro miembro.
- Debe pasar todos los checks de CI (GitHub Actions).

## Herramientas
- `ruff` para linting y formato.
- `mypy` para tipos.
- `bandit` para seguridad.
- `pytest` para pruebas.

## Antes de commitear
Ejecuta `pre-commit run --all-files` para verificar que todo está correcto.

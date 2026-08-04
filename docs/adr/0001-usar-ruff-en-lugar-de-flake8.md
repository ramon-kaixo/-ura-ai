# ADR-0001: Usar ruff en lugar de flake8

## Estado
Aceptado

## Contexto
El proyecto usaba flake8 para linting pero era lento y requeria multiples plugins.

## Decision
Migrar a ruff, que unifica linting y formateo en una sola herramienta escrita en Rust.

## Consecuencias
- Mas rapido (10x)
- Unifica lint + format + isort
- Menos dependencias

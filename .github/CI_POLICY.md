# CI/CD Pipeline Policy — Matriz de pipelines

Fuente de la sección "CI/CD Pipeline Policy" de AGENTS.md. Definición de pipelines y su contenido.

| Pipeline | Trigger | Contenido |
|----------|---------|-----------|
| PR/Commit | push/PR | Lint + typecheck + unit tests rápidos (~2200) + security + architecture |
| Merge a main | push a main | PR + slow tests |
| Nightly | 00:00 UTC | Concurrencia, timing, tests frágiles |
| Pre-release | tag v* | Todo + benchmarks + E2E |

## Principios

- No se persigue el 100% de tests en CI (~94% es el techo práctico).
- Benchmarks, E2E con servicios reales y tests de hardware específico se ejecutan en pipelines programadas o previas a release.
- Cualquier desviación se registra en `.github/tests-ci-exclude.txt`.

## Workflows actuales (2026-08-08)

- `ci.yml` — tests (`pytest motor/tests/`, e2e), lint, security, architecture
- `publish.yml` — publicación de paquetes
- `release.yml` — release

## Excepciones

Ver `.github/tests-ci-exclude.txt` (política completa en AGENTS.md "Policy: Exclusiones de CI").

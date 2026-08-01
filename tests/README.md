# tests/ — Criterios de organización

Directorio raíz de la suite de pruebas. Los tests NO se mueven entre
directorios sin actualizar este documento y verificar el impacto.

## Directorios y criterios de madurez

| Directorio | Criterio | Estado esperado |
|------------|----------|-----------------|
| `unit/` | Tests aislados, sin red, sin servicios externos, deterministas | Siempre verdes; entran en CI de PR |
| `integration/` | Tests con varios módulos reales (sin mocks salvo externos inevitables) | Verdes; entran en CI de PR |
| `contracts/` | Tests de contratos de API (ADR-011, plugins, ProtocolEnvelope) | Verdes |
| `infra/` | Tests de infraestructura (systemd, Docker, despliegues) | Condicionales a entorno |
| `knowledge/` | Tests de Knowledge Engine (corpus de evaluación) | Verdes en nightly |
| `nightly/` | Benchmarks y soak tests (lentitud > 60s o hardware específico) | Solo nightly, no en PR |
| `pending/` | Tests con bugs conocidos o en corrección activa | Documentar el bug en el test |
| `legacy/` | Tests históricos sin refactorizar | Migrar a unit/integration en Fase 4 |

## Política de madurez

Los módulos tienen distinta madurez (observación del protocolo):

| Módulo | Madurez | Estrategia de tests |
|--------|---------|---------------------|
| `motor/` | Alta (framework con ADRs, fases 10-29) | Cobertura exhaustiva, 90% |
| `core/` | Media (dominio con reglas ADR-007) | Prioridad de cobertura en puntos calientes |
| `knowledge/` | Media (engine con fases 0-7) | Tests de corpus + integración |

## Reglas

- No excluir tests de CI sin pasar por la Policy de Exclusiones (AGENTS.md)
- `tests/knowledge/` contiene el corpus de evaluación (movido por
  `7532c5c`); no modificar sin coordinación con la entidad que lo gestiona
- Los tests de cobertura dirigida de CLI viven en `tests/unit/test_ura_cli.py`
  y `tests/unit/test_ura_chat_cli.py`

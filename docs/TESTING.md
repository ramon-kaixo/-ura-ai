# Plan de Testing — URA v2.0 (Ecosistema)

**Fecha:** 2026-08-05
**Baseline Fase 1:**

| Métrica | Valor |
|---|---|
| Tests totales | 6,333 |
| Complejidad promedio (radon) | **A (3.03)** — objetivo cumplido |
| Violaciones xenon (umbral B) | **158** (baseline — deuda a reducir) |
| Fixtures muertas | **1** (eliminada: auth_headers) |
| pytest-randomly | ✅ activo por defecto |
| Cobertura global | ~78.4% |

## Herramientas

| Herramienta | Estado | Uso |
|---|---|---|
| pytest (unit+integration) | ✅ | `make validate` |
| ruff + mypy + bandit | ✅ | `make lint` |
| **pytest-randomly** | ✅ instalado y activo | `make test-random` — orden aleatorio, detecta dependencias entre tests |
| **pytest-deadfixtures** | ✅ instalado | `make test-deadfixtures` — fixtures sin usar |
| **radon** | ✅ instalado | `make complexity` — complejidad ciclomática |
| **xenon** | ✅ instalado | `make complexity` — falla si supera umbral (B absoluto) |
| hypothesis | ✅ instalado | property-based (Fase 2: tests/property/) |
| mutmut | ✅ instalado | mutation testing (Fase 4: nocturno) |
| pytest-snapshot | ⏳ Fase 3 | snapshot testing |
| locust | ⏳ Fase 3 | load testing |

## Targets Makefile

- `make validate` — Fast (~9 min): pytest + lint + hooks
- `make test-random` — pytest unit con orden aleatorio
- `make test-deadfixtures` — detecta fixtures muertas
- `make complexity` — radon promedio + xenon umbrales
- `make test-suite` — random + deadfixtures + complexity (~25 min)
- `make test-deep` — (Fase futura) + tuneladora + auditoria
- `make nightly` — (Fase futura) + mutmut + locust + chaos

## Complejidad (baseline xenon)

158 módulos superan el umbral B. **Estrategia de reducción** (no bloquea aún):
1. Refactorizar los módulos D primero (críticos)
2. Luego los B más grandes
3. El target `complexity` REPORTA — no bloquea hasta alcanzar <50 violaciones
4. Promedio actual: A (3.03) — objetivo del plan ya cumplido

## Reglas para OpenCode

1. **Cada test independiente** — no asumas orden; usa tmp_path/monkeypatch/fixtures
2. **NUNCA time.sleep()** en tests — usa asyncio.sleep o mocks
3. **Cada test con assert** — sin assert no es test
4. **Si xenon falla**: refactoriza en subfunciones, NO desactives
5. **Si random falla**: anota la semilla, arregla la dependencia, NO desactives
6. **Si snapshot falla**: revisa si el cambio es intencional, NO actualices sin permiso
7. **Si mutmut sobrevive**: mejora el test, NO arregles el mutante
8. **No instalar dependencias de testing sin ADR**

## Fases pendientes

- **Fase 2** (Semana 1): tests/property/ con 10+ tests hypothesis
- **Fase 3** (Semana 2): tests/snapshot/ (5+) + tests/load/ (locustfile) + docs/API.md
- **Fase 4** (Semana 3): mutmut nocturno + chaos_test integrado

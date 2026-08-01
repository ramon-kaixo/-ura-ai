# ADR-005-F5-lote-A — Refactor de funciones CC≥20 (Fase 5, Sprint 5b)

**Estado:** En ejecución · **Sprint:** 5b · **Funciones:** ~9 de 13 (excluidas C8/C9: `cmd_*`, `build_parser`, `validate_span_tree`)

## Justificación (ADR-007)

Funciones con CC≥20 son puntos de fallo no testables: cada rama adicional multiplica los
casos de prueba necesarios sin red de seguridad. El cambio no es alcanzable vía Protocol,
EventBus o adaptador externo porque es deuda interna de representación de flujo. La
extracción no cambia semántica ni firmas públicas (semantic freezing, ADR-007).

## Migración y rollback

- Un commit por función, reversible individualmente (`git revert` del commit).
- Oráculo: red de tests existente; donde no existe (C1), test de seguridad previo.

## Degradación

- Comportamiento observable idéntico; los 26 tests de `test_router_handler.py` pasan sin
  modificación (verificado en cada entrada).

## Funciones

| Commit | Función | Técnica | CC/LOC antes→después | Validación |
|--------|---------|---------|----------------------|------------|
| 2a0c8b1 | `handler.py:296 do_POST` | Orquestador + `_leer_body_json`, `_registrar_contexto`, `_clasificar_peticion`, `_servir_cache`, `_rutear_proxy`, `_emitir_respuesta` (compartido con `_do_proxy_inference`) | CC 24, LOC 88 → CC 3, LOC 15 (máx. helper 39) | 26/26 tests verdes, ruff 0, sin cambios de firma |

## Registro

| Fecha | Acción |
|-------|--------|
| 2026-08-01 | Apertura lote; primera función completada (`do_POST`) |

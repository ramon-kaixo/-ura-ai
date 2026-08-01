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
| 6143895 | `handler.py:296 do_POST` | Orquestador + `_leer_body_json`, `_registrar_contexto`, `_clasificar_peticion`, `_servir_cache`, `_rutear_proxy`, `_emitir_respuesta` (compartido con `_do_proxy_inference`) | CC 24, LOC 88 → CC 3, LOC 15 (máx. helper 39) | 26/26 tests verdes, ruff 0, sin cambios de firma |
| ff63b14 | `motor/core/llm/base.py:79 validate_provider` | Orquestador + `_validar_heredero`, `_validar_instanciable`, `_validar_provider_name`, `_validar_metodos`, `_validar_firmas`, `_validar_capacidades`, `_validar_comportamiento` (orden de errores idéntico) | CC 20, LOC 92 → CC 3, LOC 26 (máx. helper 29) | 20/20 tests verdes, ruff 0, mypy 41=41 (baseline) |
| *pendiente* | `knowledge/engine/validator.py:53 validate_knowledge_object` | Orquestador + `_validar_doc_type`, `_validar_warnings_core`, `_validar_tags_aliases`, `_validar_campos_obsoletos` (orden KE003→KE009→KE204 idéntico) | CC 21, LOC 123 → CC 2, LOC 30 (máx. helper 41) | 172/172 nightly verdes, ruff 0 (RUF100 limpiado) |

## Registro

| Fecha | Acción |
|-------|--------|
| 2026-08-01 | Apertura lote; primera función completada (`do_POST`) |

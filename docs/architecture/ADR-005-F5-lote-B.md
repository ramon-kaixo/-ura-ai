# ADR-005-F5-lote-B — Refactor de funciones LOC>60 con red de tests (Sprint 5b)

**Estado:** En ejecución · **Sprint:** 5b · **Referencia:** FASE5_PROPOSAL.md (C2/C3)

## Justificación (ADR-007)

Funciones >60 LOC concentran lógica de varias etapas: dificultan lectura, revisión y
pruebas dirigidas. Red de tests existente como oráculo (nightly/unit F4). Sin cambio de
comportamiento observable; firmas públicas intactas (semantic freezing).

## Migración y rollback

- Un commit por función, reversible individualmente (`git revert`).
- Oráculo: red de tests existente; verificación antes y después de cada refactor.

## Degradación

- Sin degradación: los tests pasan sin modificación. Excluidas por restricciones del plan:
  C4 (motor/assistant/api, conversation.py), C8 (CLIs declarativos), C9 (span_tree).

## Funciones

| Commit | Función | Técnica | CC/LOC antes→después | Validación |
|--------|---------|---------|----------------------|------------|
| 4c0f701 | `knowledge/engine/compiler.py:49 compile_source` | Orquestador por etapas DAG + `_compilar_defaults`, `_ctx_stage` (elimina 4 construcciones duplicadas), `_warnings_deletados`, `_etapa_parsing`, `_etapa_validacion`, `_sync_semantica`, `_auditar` | LOC 178 → 100 (orquestador) / máx. helper 41; CC 25 → 6 | 172/172 nightly verdes, ruff 0 (RUF100 limpiado) |
| c670d1f | `knowledge/engine/parser.py:81 parse_source` | `_decodificar`, `_error_codigo` (unifica 5 errores duplicados), `_relaciones_extra` | LOC 81 → 48 / máx. helper 24; CC 18 → 5 | 172/172 nightly verdes, ruff 0 |
| *pendiente* | `knowledge/engine/validator.py:212 validate_batch` | `_construir_lookups`, `_validar_relaciones` (KE004), `_check_duplicados` (KE101/KE007) | LOC 84 → 45 / máx. helper 35 | 172/172 nightly verdes, ruff 0 |

## Registro

| Fecha | Acción |
|-------|--------|
| 2026-08-01 | Apertura lote |

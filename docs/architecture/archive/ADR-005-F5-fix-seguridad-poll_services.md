# ADR-005-F5-fix-seguridad — check_service ignora forbidden_commands (Sprint 5b)

**Estado:** Cerrado · **Fecha:** 2026-08-01 · **Tipo:** Bugfix de seguridad (M7)

## Vulnerabilidad

`monitor/snc.py::check_service` ejecutaba el comando `check` del runbook **sin aplicar
la política `forbidden_commands`** (solo `repair_service` la aplicaba). Un runbook
malicioso o comprometido podía inyectar comandos arbitrarios (p.ej. `rm -rf /`) a través
de la clave `check`, ejecutados con los permisos del servicio SNC.

Descubierto por el test de seguridad C1 (Sprint 5b): `test_poll_services_nunca_ejecuta_comandos_prohibidos`
fallaba al ver `rm -rf /tmp/x` llegar a `subprocess.run`.

## Fix

- `check_service(check_cmd, forbidden=None)`: si el check está en la lista prohibida,
  retorna `False` (tratado como fallo → se intenta reparar, que sí filtra). Nunca ejecuta.
- `poll_services` pasa `runbook.get("forbidden_commands", [])` al check.
- Firma ampliada con parámetro opcional (backward-compatible); único caller en repo.

## Rollback

`git revert` del commit; degradación: sin el fix el sistema vuelve al comportamiento
inseguro previo (documentado, no debe revertirse sin mitigación).

## Validación

- 3/3 tests nuevos (`tests/unit/test_snc_poll_services.py`) verdes.
- Ruff 0 errores nuevos (INP001 preexistente, consistente con tests/unit).
- Sin cambios de comportamiento para runbooks legítimos (forbidden_commands vacío ⇒
  idéntico al anterior).

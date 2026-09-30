---
name: adr-guard
description: Bloquea modificaciones en core/ sin ADR y plan de rollback
---

# ADR obligatorio antes de tocar core/

Antes de modificar cualquier archivo dentro de `core/`:

1. Comprueba si existe un ADR que cubra el cambio en `docs/architecture/`.
2. Si NO existe:
   - PARA. No edites.
   - Propón al humano crear un ADR nuevo (formato: `docs/architecture/archive/ADR-NNN-titulo.md`).
   - Propón un plan de rollback (comando exacto).
   - Propón quién va a revisar (agente @revisor o humano).
3. Si SÍ existe:
   - Cita el ADR en la respuesta.
   - Procede.

Regla de oro: `core/` no se toca sin ADR. Esto es ADR-007.

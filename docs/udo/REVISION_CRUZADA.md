# Política de Revisión Cruzada (WEB ↔ TERM)

**Aprobada por RAMON 2026-08-13 (TASK-20260813-009)**. Complementa el modelo dual
UDO (`docs/udo/README.md`) y el Engineering Process (rol revisor por tarea).

## Principio

Nadie certifica su propio trabajo. Toda TASK cerrada DONE debe tener un revisor
distinto del ejecutor, **en la dirección opuesta**: lo que ejecuta WEB lo revisa
TERM; lo que ejecuta TERM lo revisa WEB. La AUTO-REVISIÓN queda solo como
excepción auditada (revisor indisponible + autorización expresa del coordinador).

## Reglas

1. **Dirección cruzada**: TASK ejecutada por el Web → revisor el Terminal;
   TASK ejecutada por el Terminal → revisor el Web. Nunca el mismo agente.
2. **Roles por tarea** (mecanismo existente): `ura-udo update TASK --agente_web
   "WEB (ejecutor)" --agente_terminal "TERM (revisor)"` — el revisor declarado
   NO modifica la zona que revisa (la reserva sigue activa en REVIEW).
3. **Revisor real**: el agente `revisor` del Terminal (config opencode.json Mac)
   o, si no hay ruta, el agente `qa`/revisión con evidencia objetiva en ASUS
   (suite, git, CI) marcado AUTO-REVISIÓN explícita.
4. **Planes extensos con ambos programando**: partición por zonas disjuntas
   (`ura-udo reserve` con enforcement — sin solapamiento), expediente UDO como
   punto de encuentro, commits `[TASK-...][WEB|TERM]`, y revisión cruzada de la
   otra mitad ANTES de cerrar DONE. Si una zona está reservada/ocupada, el otro
   agente NO la toca: la espera o toma otra (regla §5.19 UDO).
5. **Evidencia mínima del revisor**: commits y rutas:líneas revisadas, veredicto
   (APROBADA / APROBADA-PARCIAL / RECHAZADA) e integración en
   `docs/udo/review-pending.md` (formato Acta TERM 2026-08-13).
6. **Excepciones**: solo con autorización expresa del coordinador (humano) y
   registradas en el historial del expediente (`AUTORIZACIÓN EXPRESA`).

## Flujo (plan extenso con 2 agentes)

```
PLAN (OpenClaw/propuesta) → RAMON aprueba → TASKs por zonas (reservas disjuntas)
→ WEB ejecuta zona A / TERM ejecuta zona B (en paralelo si no solapan)
→ TERM revisa zona A / WEB revisa zona B (cruzado)
→ veredictos en review-pending.md → cierre DONE por TASK → validación final
```

## Referencias

- Modelo dual UDO: `docs/udo/README.md` (roles por tarea, reservas, gate de cierre).
- Acta de revisión cruzada ejecutada (primer lote): `docs/udo/review-pending.md`
  §ACTA REVISIÓN EXTERNA TERM — LOTE 2026-08-13.
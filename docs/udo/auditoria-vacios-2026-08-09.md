# Auditoría de vacíos — "lo que se marca hecho, se comprueba hecho"

**Fecha**: 2026-08-09 · **Tarea**: TASK-20260809-012
**Explicado en sencillo** (sin tecnicismos): buscamos los sitios donde decíamos "hecho" sin que nadie lo comprobara de verdad — y los cerramos.

---

## Los 3 vacíos que encontramos (como el que descubrimos en la conversación)

| # | Dónde estaba | Qué pasaba | Ejemplo real |
|---|--------------|------------|--------------|
| **V1** | Al cerrar una tarea (`validacion:`) | El agente **escribía** "suite 35/35 OK" y el sistema lo **aceptaba sin comprobarlo** | Podía poner "todo pasa" sin haber ejecutado nada |
| **V2** | Un plan con muchos puntos | Nadie verificaba que **cada punto del plan** quedara hecho | Plan con 8 requisitos → se hacían 6 y cerraba igual |
| **V3** | La revisión del revisor (`--ok`) | El revisor **decía** "OK" pero el sistema no comprobaba nada | El OK dependía solo de la palabra del revisor |

**El patrón común**: escribíamos "hecho" en un papel, pero nadie miraba si era verdad.

## La solución implementada (V1 — la más importante)

**Nuevo: la verificación se EJECUTA, no se declara.**

```
ANTES:  "digo que los tests pasan"  → el sistema me cree
AHORA:  "digo que los tests pasan Y el sistema los ejecuta de verdad antes de cerrar"
```

Cuando el agente cierra una tarea, ahora puede decirle al sistema **qué comando comprobar** (`--verificar "bash tests/udo/test_udo.sh"`). Y el sistema:
- **Ejecuta** ese comando de verdad
- Si falla → **bloquea el cierre** con el error en pantalla
- Si pasa → "Verificación real: OK" → se cierra

**Verificado de verdad**: probé un comando que falla → el cierre se bloqueó ✅ · un comando que pasa → el cierre se completó ✅ · suite 45/45 ✅

## Lo que NO se cerró (pendiente — decisión tuya)

| Vacío | Por qué queda abierto | Qué haría falta |
|-------|----------------------|-----------------|
| **V2** (requisitos del plan) | Requiere decidir el formato de "checklist" por tarea | Campo `requisitos:` con `[x]`/`[ ]` — el gate bloquearía si queda alguno sin marcar |
| **V3** (revisor) | El revisor ES otro agente (OpenCode Escritorio) — su veredicto es humano/LLM, no automatizable | Ya queda auditado en `revision:`; la verificación real V1 ayuda al revisor a comprobar |

## Próximo paso (ya en marcha)

Esta auditoría y sus cambios **pasan ahora a revisión del OpenCode Escritorio** (el flujo de doble ojo que montamos): él verificará que lo que dice este documento es cierto, con `ura-doble verify` + `ura-udo diff`, y dará su OK o devolverá con motivos.

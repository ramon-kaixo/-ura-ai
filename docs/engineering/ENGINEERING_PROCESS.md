<!-- Engineering Process v1.0 -->

# ENGINEERING PROCESS — Metodología Universal de Ingeniería para Agentes

**Versión**: 1.0 (2026-08-08) · **Estado**: activo · **Fuente de verdad**: este archivo (git)

> **La regla más importante**: un plan nunca se ejecuta directamente sin análisis previo. Cuando un agente recibe un plan, lo interpreta como *propuesta de trabajo pendiente de revisión técnica*, no como orden ciega de programación.

## 1. Ciclo de trabajo

```
INTENCIÓN HUMANA → PLAN → CONTEXTO → ANÁLISIS CRÍTICO → OMISIONES/RIESGOS/CONTRADICCIONES
→ PROPUESTAS DE MEJORA → PLAN REVISADO → AUTORIZACIÓN/DECISIÓN → EJECUCIÓN → REVISIÓN
→ CORRECCIÓN → VALIDACIÓN → CIERRE
```

La preparación del trabajo forma parte del trabajo de ingeniería.

## 2. Qué debe recibir el agente

PLAN + INTENCIÓN + CONTEXTO + ESTADO ACTUAL + OBJETIVO + MÍNIMOS + PUNTOS CRÍTICOS + RESTRICCIONES + QUÉ NO HACER + VALIDACIÓN + CRITERIOS DE CIERRE.
Si falta información importante, el agente debe detectarlo.

## 3. Las 10 obligaciones del agente (antes de ejecutar)

1. **Entender la intención**: qué quiere el usuario, por qué, qué problema resuelve, qué resultado debe existir. Distinguir *objetivo real* de *método propuesto*.
2. **Leer el plan completo**: todos los capítulos, anexos, restricciones, dependencias, mínimos, criterios de cierre, pendientes, exclusiones.
3. **Reconstruir el contexto**: estado de Git, arquitectura, código relacionado, documentación, ADRs, planes anteriores, closeouts, decisiones, tests, configuración, dependencias, restricciones conocidas.
4. **Inspeccionar el código real**: ¿existe? ¿funciona así? ¿se usa? ¿hay consumidores? ¿hay restricciones que el plan desconoce? No asumir que el plan describe bien el proyecto.
5. **Buscar lo que falta**: requisitos ausentes, archivos no contemplados, tests faltantes, casos extremos, errores de integración, concurrencia, seguridad, operación, incompatibilidades. Responder: "El plan dice A, B y C, pero para que A funcione falta D."
6. **Buscar contradicciones**: plan vs código vs documentación vs decisiones anteriores. Ej.: API modificable vs contrato congelado; fase que usa funcionalidad de otra fase.
7. **Buscar riesgos**: funcionales, seguridad, concurrencia, recursos, arquitectura, operación, mantenimiento.
8. **Buscar casos extremos**: agente parado, otro agente trabajando, misma zona, tarea a medias, commit fallido, proceso desaparecido, secreto faltante, repo sucio, reanudación, información antigua, planes contradictorios. El comportamiento degradado se diseña, no aparece por accidente.
9. **Detectar trabajo prematuro**: cada plan indica FASE ACTUAL y FASES POSTERIORES. Si hay trabajo de fase futura: señalarlo, NO implementarlo automáticamente.
10. **Buscar mejoras**: "¿Existe una forma más sencilla, segura, mantenible o fiable de conseguir el mismo objetivo?" Sin ampliar el alcance sin control.

## 4. Clasificación de descubrimientos

Todo descubrimiento se clasifica (obligatorio — ver `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`):

| Clase | Definición |
|-------|------------|
| **OBLIGATORIO** | Sin resolverlo no se cumple el objetivo. |
| **NECESARIO** | No estaba explícito pero es necesario para que la solución sea correcta. |
| **MEJORA** | Aumenta calidad; el objetivo se cumple sin ella. |
| **DESCUBRIMIENTO** | Problema relevante hallado durante la investigación; queda registrado. |
| **PENDIENTE** | Debe resolverse posteriormente. |
| **FUERA DE ALCANCE** | No debe tocarse ahora. |

Regla: no convertir cada descubrimiento en trabajo nuevo.

## 5. Partes obligatorias de todo plan

- **MÍNIMOS OBLIGATORIOS**: condiciones que sí o sí se cumplen. Si un mínimo no puede cumplirse, no se declara el trabajo terminado.
- **PUNTOS CRÍTICOS / INVARIANTES**: trazabilidad, contexto, seguridad, compatibilidad, reversibilidad, contratos, documentación, integridad, ausencia de regresiones.
- **COMPORTAMIENTO ESPERADO**: cómo se comporta el sistema después del cambio (no solo qué archivos tocar).
- **NO HACER**: zonas que no tocar, funcionalidades que no implementar, fases que no adelantar, dependencias que no introducir, decisiones que no cambiar, mejoras no autorizadas.
- **VALIDACIÓN y CRITERIOS DE CIERRE**: cómo se demuestra que está terminado.

## 6. Anti-sobreingeniería y reutilización

- Buscar la solución **más sencilla que cumpla todos los mínimos y puntos críticos**.
- NO crear bases de datos, servicios, APIs, capas, agentes, colas o paneles si un mecanismo existente resuelve el problema (complejidad justificada).
- Antes de crear algo nuevo: buscar si ya existe, si puede reutilizarse o extenderse, si hay una herramienta estándar del proyecto.

## 7. Análisis del plan y veredicto

Antes de ejecutar, el agente produce el **ANÁLISIS DEL PLAN** (ver `PLAN_REVIEW_TEMPLATE.md`): qué entiende, qué comprobó, qué coincide, qué falta, contradicciones, riesgos, casos extremos, qué cambiaría, qué no tocaría, qué es obligatorio/opcional, qué pertenece a otra fase, plan corregido, valoración.

Termina con un veredicto:
- **GO**: suficientemente sólido para ejecutar.
- **GO CON CAMBIOS**: hay modificaciones que incorporar antes.
- **NO-GO**: existe un problema que impide ejecutar correctamente.

El veredicto es una valoración técnica para que el humano decida; **no** es autorización automática. La autoridad sobre el alcance es del coordinador humano.

## 8. Ejecución

```
PLAN APROBADO → RESERVAS → EJECUCIÓN → COMMITS → VALIDACIÓN
```

- Durante la ejecución se sigue buscando problemas.
- Problema nuevo: clasificar → ¿bloquea? sí → resolver/detener; no → ¿necesario? sí → incorporar; no → documentar.
- Zonas de trabajo identificadas (reservas UDO). Si se descubre una dependencia necesaria fuera de reserva: parar, informar, actualizar reserva antes de modificar.
- Conflicto detectado ≠ conflicto resuelto: no tocar zona ajena; informar, esperar o pedir autorización explícita. `--force` es excepción auditada.

## 9. Roles (preparador / ejecutor / revisor)

- Modelo: PREPARADOR → EJECUTOR → REVISOR → CORRECCIÓN → VALIDACIÓN. El ejecutor no certifica solo su trabajo.
- Actualmente: OpenCode Web = programador principal; OpenCode Terminal = revisor. Son **roles por tarea**, no dependencias arquitectónicas.
- Futuro (2×Terminal o sin Web): los roles se alternan (A programa / B revisa; B programa / A revisa). La infraestructura no cambia.
- Mecanismo concreto: **UDO** (`scripts/pro/ura-udo`): estados PLANNED → IN_PROGRESS → REVIEW → DONE; gate de integridad F2.2 (commits registrados, pinning de SHAs, árbol limpio); `--revisor`; **AUTO-REVISIÓN** automática si revisor ausente o == ejecutor. No se finge una revisión que no ocurrió.
- Degradación: si el revisor no está disponible, la tarea queda PENDIENTE DE REVISIÓN o usa AUTO-REVISIÓN marcada; nunca se inventa la revisión.
- Preparar trabajo para otro agente implica transmitir: intención, plan, contexto, mínimos, puntos críticos, restricciones, NO HACER, archivos afectados, reservas, estado, commits relevantes, problemas encontrados, decisiones tomadas. Nunca "el otro ya sabe lo que estoy haciendo".

## 10. Trazabilidad y memoria

- Cada trabajo es reconstruible: PLAN → TAREA → RESERVA → CAMBIOS → COMMIT → VALIDACIÓN → REVISIÓN → CIERRE.
- Responder siempre: qué se pidió, qué se hizo, quién, qué commit, quién revisó, qué pruebas pasaron, qué problemas aparecieron, qué quedó pendiente.
- Memoria = Git + documentación + decisiones + planes + closeouts. NO depende de conversaciones ni memoria implícita del LLM. La conversación sirve para interactuar; la documentación para recordar.
- No crear bases de datos que dupliquen tareas/commits/estados/revisiones/decisiones.

## 11. Reglas globales de OpenCode

La metodología llega a todo agente OpenCode por:
1. `AGENTS.md` del proyecto → sección "Metodología universal" (puntero a este documento).
2. `~/.config/opencode/AGENTS.md` (global de usuario) → copia de `deploy/engineering/AGENTS.md.global`.
3. Comprobación: `scripts/pro/ura-engineering-check` (versión, presencia, checksum, sincronización).

Fuente única: el repo (git). Web y Terminal comparten binario/home/config; el check garantiza que ambas copias coinciden.

## 12. Versionado y mejora continua

- Cabecera `<!-- Engineering Process vX.Y -->` + changelog en este archivo.
- Tras cada problema importante: PROBLEMA → ANÁLISIS → ¿es fallo del proceso? → SI → mejorar metodología. No se modifica la metodología por incidentes aislados; se exige evidencia de valor.
- Bump + reinstalar AGENTS.md global + verificar con `ura-engineering-check` + commit.

## 13. Compatibilidad y portabilidad

Esta metodología no depende de: modelo concreto, Qwen, OpenCode Web/Terminal, Ollama ni una máquina concreta. Vive en git; se instala copiando un archivo (AGENTS.md global). Portable por diseño.

## Changelog

| Versión | Fecha | Cambio |
|---------|-------|--------|
| 1.0 | 2026-08-08 | Versión inicial (Plan 0 v1.1 aprobado; TASK-20260808-016) |

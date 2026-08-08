# TROUBLESHOOTING — Qué hacer ante los problemas habituales

**UDO v5** — problemas conocidos y su resolución.

## Lock huérfano (tarea abandonada con reserva activa)

**Síntoma**: `ura-udo check` o `reserve --add` dice BLOQUEADO por una tarea que nadie sigue.

**Resolver** (sin editar archivos a mano):
```bash
ura-udo show TASK-XXXX        # verificar que está abandonada (sin actividad reciente)
ura-udo reserve TASK-XXXX --clear   # liberar la zona (sin --force: solo el propietario puede; con --force queda auditado)
```
Regla: **no automatizar** la liberación (riesgo de falso abandono). Decisión humana. La tarea abandonada se queda en su estado (IN_PROGRESS/REVIEW) — nunca se inventa que terminó.

## Tarea bloqueada (no puede pasar de estado)

**Síntomas y soluciones**:

| Error | Causa | Solución |
|-------|-------|----------|
| `DONE solo desde REVIEW` | Se intentó cerrar sin revisión | Pasar a REVIEW antes: `update TASK --estado REVIEW` |
| `DONE requiere commits registrados` | No se ejecutó verify | `ura-udo verify TASK` (registra el commit) |
| `DONE requiere analisis/validacion` | Faltan campos (gate A1/A2) | `update TASK --analisis "..." --validacion "..."` |
| `commit 'x' no es ancestro de HEAD` | Historia reescrita tras verify | No reescribir historia; o `--force` con nota |
| `DONE bloqueado — cambios sin commitear` | Árbol sucio fuera del expediente | Commitear antes de cerrar |

## Commit sin TASK-ID

**Política (§5.12)**: permitido si es operación administrativa excepcional. El validador solo exige conventional commits (`feat/fix/docs/...`); **no inventa tareas automáticamente**. El commit queda como UNTRACKED (sin asociar). Para asociarlo después: `ura-udo verify TASK` no lo reclama — se documenta en el expediente con nota.

## Discrepancia (declaración vs Git)

**Síntoma**: `verify` muestra `MODIFICADOS SIN DECLARAR` o WARNING de coherencia.

**Resolver**:
1. Añadir las rutas a la reserva: `ura-udo reserve TASK --add "ruta"` (si es del trabajo).
2. O documentar en el expediente por qué se tocó (`--nota`).
3. Re-ejecutar `ura-udo verify TASK` hasta que no haya discrepancias.
4. Nunca ocultar: si se declara "no modifiqué nada" y Git muestra archivos, el verify lo detecta y se registra.

## Recuperación de una sesión interrumpida

1. `ura-udo status` — ver tareas activas con owner, última actividad, commits, pendientes.
2. `ura-udo context TASK` / `ura-ask TASK` — reconstruir qué se pedía, qué se hizo, qué falta.
3. Si el ejecutor dejó trabajo a medias: queda IN_PROGRESS/REVIEW (nunca DONE).
4. Retomar con `ura-opencode` o continuar en Terminal (respetando reservas).

## Web sin respuesta / idle

- `ura-udo status` muestra si hay tareas esperando.
- Si la Web está idle de facto: Terminal puede ejecutar tareas independientes (sin solapar reservas) y la revisión se marca AUTO-REVISIÓN (honestidad, nunca fingir).
- Al volver la Web: revisar el lote de `docs/udo/review-pending.md`.

## Rendimiento

`status`/`verify` son <1s con decenas de tareas (solo leen expedientes + git). Si un día se vuelve lento (miles de tareas), optimizar antes que añadir una BD (regla: no BD para un problema que no existe).

## Desinstalar / reversibilidad

```bash
rm -rf docs/udo/ && rm scripts/pro/ura-udo   # deja URA intacta (principio UDO)
```

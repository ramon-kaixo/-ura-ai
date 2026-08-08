# TASKS — Crear, consultar, actualizar y cerrar tareas

**UDO v5** — referencia rápida de `ura-udo` (script: `scripts/pro/ura-udo`).

## Crear

```bash
ura-udo create "descripción del trabajo"
# → Creada: TASK-YYYYMMDD-NNN
```

## Consultar

```bash
ura-udo show TASK-ID            # expediente completo (campos + historial)
ura-udo context TASK-ID         # contexto compartido (expediente + commits + reservas)
ura-udo list [ESTADO]           # lista de tareas (filtro opcional)
ura-udo status                  # estado del proyecto: tareas activas con owner/actividad/commits/pendientes
ura-udo verify TASK-ID          # verificación: commits, discrepancias reserva↔git, coherencia cambios (F4)
```

## Actualizar

```bash
ura-udo update TASK-ID --estado IN_PROGRESS|REVIEW|DONE|BLOCKED|CANCELLED
ura-udo update TASK-ID --nota "texto"
ura-udo update TASK-ID --agente_web "WEB (ejecutor)" --agente_terminal "TERM (revisor)"
ura-udo update TASK-ID --instrucciones "..." --restricciones "..."
ura-udo update TASK-ID --revisor "WEB"
ura-udo update TASK-ID --analisis "análisis previo del plan"     # obligatorio en DONE (gate)
ura-udo update TASK-ID --validacion "suite 35/35"                # obligatorio en DONE (gate)
ura-udo update TASK-ID --pendientes "lo que queda"
ura-udo update TASK-ID --resultado "resultado global"
ura-udo update TASK-ID --resultado_web "qué hizo Web"
ura-udo update TASK-ID --resultado_terminal "qué hizo Terminal"
```

## Reservas

```bash
ura-udo reserve TASK --add "ruta1,ruta2"     # declarar zona de trabajo
ura-udo reserve TASK --clear                 # liberar zona
ura-udo check [ruta...]                      # detectar conflictos con reservas ajenas
# --force = excepción auditada (queda en historial como AUTORIZACIÓN EXPRESA)
```

## Cerrar (DONE)

Secuencia obligatoria (gate F2.2 + A1/A2):

```bash
ura-udo update TASK --estado REVIEW --nota "revisado"
ura-udo verify TASK-ID                        # registra el commit en el expediente
ura-udo update TASK --estado DONE --analisis "..." --validacion "..."
```

- DONE **solo desde REVIEW** (CASO B). Sin `--force` no hay atajos.
- El gate exige: commits registrados, diff no vacío, SHAs ancestrales, árbol limpio, analisis/validacion no vacíos.
- Sin revisor independiente → marca **AUTO-REVISIÓN** automática + registro en `docs/udo/review-pending.md`.

## Estados

`PLANNED → IN_PROGRESS → REVIEW → DONE` (+ BLOCKED / CONFLICT / CANCELLED)

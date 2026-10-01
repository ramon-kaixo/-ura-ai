# URA OpenCode Setup

Configuración de OpenCode para el proyecto URA IA 1972.

## Contenido

- `agents/` - 7 agentes especializados (build, calidad-cobertura, orchestrator, revisor, revisor-fondo, tester, verificador)
- `skills/` - 7 skills (adr-guard, alarma-coverage, cobertura-pipeline, load-memory, orchestrator-plan, read-agents-md, verify-on-close)
- `commands/` - 6 comandos (audit, check, status, sync, test, verify)
- `themes/` - tema ura-dorado.json
- `plans/` - planes de desarrollo y arquitectura
- `opencode.json` - configuración del proyecto
- `project.json` - metadatos del proyecto

## Variables de entorno requeridas

- `OPENCODE_SERVER_PASSWORD` - password del servidor OpenCode
- `URA_ORCHESTRATOR_URL` - URL del orquestador URA (ej: http://127.0.0.1:4097)

## Cómo replicar este setup

1. Clonar el repo URA
2. Copiar `.opencode/` a la raíz del proyecto
3. Copiar `.config/opencode/` a `~/.config/opencode/`
4. Configurar variables de entorno
5. Instalar dependencias: `pip install -e .` (si hay requirements)

## Servicios systemd relevantes

- `opencode.service` - servidor web OpenCode (puerto 8081)
- `opencode serve` - servidor API (puerto 4097)
- `open-engine.service` - daemon de ingenieros URA
- `ura-chaos.service` - chaos engineering (timer activo)
- 25+ servicios URA activos

## Recuperación desde backup

```bash
tar xzf /home/ramon/URA/.opencode-backups/full-<timestamp>.tar.gz -C /
```

## Kit portátil

```bash
tar xzf /home/ramon/URA/.opencode-backups/kit-<timestamp>.tar.gz -C /destino
```

## Comandos útiles

- `/test` - suite completa de tests
- `/sync` - sincronizar Mac ↔ GX10
- `/verify` - revisor + verificador + tester
- `/audit` - auditoría rápida
- `/status` - estado servicios GX10

## Nota histórica: padre .opencode/

El directorio `/home/ramon/URA/.opencode/` (padre del proyecto) existía anteriormente como configuración global compartida. Fue movido a `/home/ramon/URA/.opencode-backups/agents-old-<timestamp>/` durante la limpieza. Contenía 7 symlinks a los agents del proyecto, que ahora viven solo en `.opencode/agents/` del proyecto.


## Nota sobre commands (sync/status/test)

Los commands `sync.md`, `status.md` y `test.md` fueron escritos originalmente para ejecutarse
desde la Mac. Ahora OpenCode corre en la ASUS, así que:

- Las IPs dentro de ellos (`100.72.103.12`) apuntan a la ASUS, no a la Mac.
- Los paths (`/Users/ramonesnaola/...`) son de Mac.

Si algún día se ejecutan desde la ASUS, hay que reescribirlos. Por ahora se dejan como están
porque no se usan desde aquí.

IPs reales:
- ASUS: 100.72.103.12
- Mac: 100.123.81.101

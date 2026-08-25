# ROLES DE LOS 3 OPENCODE — URA

Fecha: 2026-08-25 · Autor: TERM · Verificado por: ocpm-check (auto)

## OpenCode Desktop ASUS (GX10) — REVISOR

- **Rol**: Revisor, auditor, veredictos
- **Conexión**: Ollama local `localhost:11434`
- **Modelo por defecto**: `ollama/qwen3.6:27b`
- **Modelos disponibles**: 8 (qwen3.6:27b, qwen3-coder:30b, gemma4:26b, nemotron-3-nano:30b, llama3.3:70b, llama3:latest, llava:7b, nomic-embed-text)
- **Permisos**: lectura/verificación de todo, NO commits de código nuevo sin aprobación
- **Tareas típicas**: revisar PRs, verificar tests, auditar seguridad, dar veredictos TASK-00X, análisis de planes (Modo Análisis)

## OpenCode Desktop Mac (Mini M4) — GENERADOR

- **Rol**: Generador de código, consultas, ejecución de tareas
- **Conexión**: Ollama remoto `100.72.103.12:11434` (GX10 vía Tailscale)
- **Modelo**: configurable en dropdown
- **Permisos**: commits en ramas de trabajo (`ia/TASK-*`), NO push a main sin revisión
- **Tareas típicas**: desarrollo de código, tests, refactorizaciones, commits

## OpenCode Web/Terminal (GX10 :8081) — GENERADOR

- **Rol**: Generador de código, consultas, ejecución de tareas pesadas en GX10
- **Conexión**: Ollama local `localhost:11434` (misma máquina)
- **Modelo por defecto**: `ollama/qwen3.6:27b`
- **Permisos**: commits en ramas de trabajo (`ia/TASK-*`), NO push a main sin revisión
- **Tareas típicas**: tareas que requieren acceso directo a GX10 (servicios, GPU, archivos locales)

## Comunicación entre instancias

- Los 3 OpenCode trabajan sobre el **MISMO repo** `~/URA/ura_ia_1972`
- Los generadores (Mac + Web) hacen código y consultas
- El revisor (ASUS Desktop) revisa antes de que cualquier cosa llegue a main
- **UDO** (`scripts/pro/ura-udo`) es el protocolo de coordinación: expedientes, reservas, veredictos
- Si hay conflicto de edición simultánea: usar `git stash` o ramas temporales `ia/TASK-*`
- Las ramas de trabajo se fusionan a main SOLO con veredicto APROBADO del revisor

## Estado verificado (2026-08-25)

| Instancia | Ollama | Modelos | Rol |
|-----------|--------|---------|-----|
| ASUS Desktop (GX10) | localhost:11434 ✅ | 8 ✅ | REVISOR |
| Mac Desktop | 100.72.103.12:11434 ✅ | 8 ✅ | GENERADOR |
| Web/Terminal (GX10) | localhost:11434 ✅ | 8 ✅ | GENERADOR |

## Verificación cruzada CLI (2026-08-25, TERM)

| Instancia | Comando | Resultado |
|-----------|---------|-----------|
| Mac Desktop → GX10 Ollama | `curl gx10:11434/api/generate` | ✅ "hola mundo desde Mac" |
| GX10 Ollama local | `curl localhost:11434/api/generate` | ✅ "hola mundo desde GX10" |

## Pendiente de verificación humana (REVISOR)

- [ ] OpenCode Desktop Mac: abrir dropdown de modelos → confirmar que muestra los 8 modelos
- [ ] OpenCode Desktop ASUS: abrir dropdown de modelos → confirmar que muestra los 8 modelos
- [ ] OpenCode Web (:8081): abrir dropdown de modelos → confirmar que muestra los 8 modelos
- [ ] Si alguno NO muestra modelos: reconfigurar proveedor en ~/.config/opencode/opencode.json

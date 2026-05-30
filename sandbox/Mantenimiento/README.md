# Sandbox 1 — Mantenimiento

**Función:** Limpieza y optimización del ecosistema URA
**Ubicación:** Mac (local)
**Horario:** 06:00 y 18:00

## Herramientas
- `scripts/limpiar_caches.sh` — Limpieza de cachés Python, pip, npm
- `scripts/optimizar_db.sh` — VACUUM y reindexado de SQLite
- `scripts/rotar_logs.sh` — Rotación y compresión de logs antiguos
- `scripts/limpiar_temp.sh` — Eliminación de archivos temporales
- `scripts/refactorizar_complejidad.sh` — Análisis y refactorización de complejidad ciclomática

## Flujo de ejecución
1. El orquestador activa Mantenimiento a las 06:00 y 18:00
2. Ejecuta los scripts en orden: caches → db → logs → temp
3. Registra resultados en `logs/mantenimiento_YYYYMMDD.jsonl`
4. Notifica a Seguridad y Documentación vía sandbox_orchestrator

## Dependencias
- Acceso al sistema de archivos del Mac
- SQLite3 para optimización de BD
- Python venv del proyecto

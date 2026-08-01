# Estructura del Repositorio URA (Fase 3 — v1)

Mapa de responsabilidad única por carpeta, tras la reorganización de
la Fase 3. Documento vivo: actualizar al añadir/mover carpetas.

## Paquetes principales

| Ruta | Responsabilidad | Estado |
|------|-----------------|--------|
| `core/` | Lógica de dominio (conciencia, valores, scribe, rollback, mochila, model_router, memoria, voice, debate) | VIVO — no reorganizar internamente sin ADR (ADR-007) |
| `motor/` | Framework del motor (config única, plataforma, pipeline, agents, memory, assistant, cli) | VIVO |
| `knowledge/` | Memoria a largo plazo, Knowledge Engine (Fases 0-7), evaluación | VIVO |
| `agents/` | Agentes especializados (runner, diseño, hostelería, legal, programación, sandbox) | VIVO |
| `scripts/` | Scripts de operación: `pro/` (pipeline ~146), `deploy/`, `hooks/`, `tests/` | VIVO |
| `tests/` | Suite de pruebas (ver `tests/README.md`) | VIVO |
| `docs/` | Documentación (architecture/, plugins/, etc.) | VIVO |
| `deploy/` | Unidades systemd, scripts de despliegue, Dockerfiles | VIVO — incluye `ura.service` (movido de raíz en F3) |
| `config/` | Configuración runtime (settings.json, system_config.json, dispositivos, infra, reglas) — varios ficheros con `chattr +i` | VIVO |
| `data/` | Datos runtime (changes.db, baseline, documentos, eventos, snapshots) | RUNTIME |
| `requirements/` | requirements base/dev/gpu.txt | VIVO |
| `schemas/` | SQL schemas + migraciones | VIVO |
| `bitacora/` | Bitácoras fechadas (YYYY-MM-DD.md) | VIVO |
| `shared/` | Utilidades compartidas (`paths.py`, con test) | VIVO |
| `monitor/` | Monitorización (snc.py, health_check, log_alerts) — usado por tests/legacy y plists | VIVO |
| `mantenimiento/` | Scripts de mantenimiento (ura_maintenance, auto_reparacion, rotate_logs) | VIVO |
| `scraping/` | Minería remota (`meta_miner_remote.py` se despliega a Hetzner) | VIVO (remoto) |
| `ura_search/` | Búsqueda vectorial del grafo indexado (import lazy en core/model_router.py:1095) | VIVO |
| `configs/` | 🔒 **Congelado** — `ia_committee_config.json` con `chattr +i`; pendiente de consolidar en `config/` cuando haya sudo (Fase 3-B5 diferido) | ⚠️ PENDIENTE |

## Archivos de raíz (keep)

| Archivo | Responsabilidad |
|---------|-----------------|
| `ura.py` | Wrapper CLI (83% cobertura) — no eliminar (Fase 9) |
| `ura_chat.py` | Chat CLI (97% cobertura) |
| `path_setup.py` | Setup de paths (sincronizado por sync_ura.sh) |
| `mochila_engine.py`, `memoria_fallos.py`, `memoria_movimiento.py`, `prompt_injector.py` | Herramientas de raíz con tests en tests/unit/ (decisión F3: permanecen en raíz) |
| `Makefile`, `Dockerfile`, `entrypoint.sh`, `docker-compose*.yml`, `install.sh`, `instalar_cron.sh`, `prometheus.yml`, `requirements.txt`, `pyproject.toml`, `p2p_asus.sh`, `persist_p2p_mac.sh` | Infraestructura |

## Archivos eliminados (Fase 3)

| Archivo | Motivo |
|---------|--------|
| `agent_hierarchy.py` | 0 imports, servicio systemd fallido; referencias obsoletas limpiadas (arq_auditor, sync_ura) |
| `verify_agents.py` | 0 referencias |
| `test.txt`, `benchmark_f10_results.json` | Artefactos |
| `core_deps.txt`, `motor_deps.txt`, `knowledge_deps.txt`, `imports.txt`, `archivos_python.txt` | Artefactos de diagnóstico (regenerables) |

## Archivo .attic/ (nuevo, gitignored)

Archivo local de código retirado (no versionado, no sincronizado):

| Origen | Contenido |
|--------|-----------|
| `app/` | motor_flujo.py, gestor_archivos.py, main.py, capturador.py |
| `cli/` | `__init__.py` vacío |
| `sandbox/` | sandbox_client.py, sandbox_runner.py, linter_advanced.py, Dockerfile |

Recuperación: `git log` conserva la historia completa de las rutas originales.

## Hallazgos para fases futuras

1. **`core/modules/data/chroma_db_code/chroma.sqlite3` (10 MB trackeado en git)** —
   datos de runtime versionados. Recomendación: política de datos (excluir de git
   y regenerar) en fase de datos/rendimiento.
2. **`core/modules/data/raw/*.jsonl`** — stubs de 0 bytes eliminados; el único
   fichero con contenido quedó aplanado desde `core/modules/modules/data/`.
3. **`configs/`** — consolidación bloqueada por `chattr +i` (requiere sudo).
4. **ADRs 084-090 duplicados** generados por el hook post-commit (misma causa);
   revisar el generador de ADRs para deduplicar por hash de mensaje.
5. **`data/baseline/`** — salida de la Fase 0 (línea base), sin versionar.

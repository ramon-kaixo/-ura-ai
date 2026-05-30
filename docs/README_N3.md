# URA N3 — OpenClaw + Aprendizaje Observacional + Sandbox (Fase 3)

**Estado:** F1+F2+F3 completos y testeados (106/106 tests N2/N3 + 529 suite total).
**Fecha:** 2026-05-05.

## Lo que añade esta fase

| Módulo | Responsabilidad |
|---|---|
| `core/ura_openclaw_client.py` | Cliente local para OpenClaw (subprocess / HTTP / ollama_direct / stub auto) |
| `core/ollama_n3_client.py` | Cliente directo a Ollama para N3 (reemplaza OpenClaw embedded) |
| `core/openclaw_health.py` | Verificador de salud de OpenClaw |
| `core/openclaw_connector.py` | Conector HTTP para OpenClaw (vía ollama launch openclaw) |
| `core/n3_orchestrator.py` | Orquestador dual N3 (Ollama directo + OpenClaw complementario) |
| `core/training_gatekeeper.py` | Gatekeeper para entrenamiento masivo N3 (controla cuándo entrenar) |
| `core/training_orchestrator.py` | Orquestador de entrenamiento masivo N3 con Ollama directo |
| `core/ura_observational_learner.py` | Observa N3, promueve maletas N2 tras 10 ejec + examen |
| `core/ura_sandbox_bridge.py` | Capa de aislamiento I/O (passthrough / SSH / Lima) |
| `ura_n3_search.py` | Entry point CLI/API para N3 |
| `ura_search.py` | **Entry point UNIFICADO** N1/N2/N3 vía router |
| `core/ura_n2_to_n8n_exporter.py` | (F4) Workflow JSON real con 4 nodos n8n |

## Configuración por variables de entorno

### OpenClaw (N3)

```bash
# Forzar modo stub (no llamar al binario aunque exista)
export URA_OPENCLAW_STUB=1

# Apuntar a binario en ruta no-PATH
export URA_OPENCLAW_BIN=/ruta/a/openclaw

# O usar HTTP (si OpenClaw expone un servidor)
export URA_OPENCLAW_HTTP=http://127.0.0.1:9080

# Modelo Ollama por defecto
export URA_OPENCLAW_MODEL=llama3

# Timeout en segundos
export URA_OPENCLAW_TIMEOUT=180
```

Detección automática: el cliente busca `openclaw` en PATH si no hay env vars.
**En tu Mac ya está detectado** en `/opt/homebrew/bin/openclaw`.

### Requisitos para OpenClaw real (modo subprocess)

**Estado actual (2026-05-05)**: OpenClaw embedded tiene timeout persistente (600s) con Ollama local. El problema es el modo embedded de OpenClaw, no Ollama.

**Diagnóstico**:
- Ollama funciona perfectamente directamente (API responde en ~0.5s)
- OpenClaw embedded se queda esperando 600s (10 minutos) antes de timeout
- Logs muestran: "embedded run timeout: timeoutMs=600000"
- El problema es fundamental: OpenClaw embedded no es compatible con Ollama local

**Solución implementada**: Cliente directo a Ollama para N3

En lugar de usar OpenClaw embedded, se implementó `core/ollama_n3_client.py` que:
- Usa Ollama directamente (http://127.0.0.1:11434)
- Funciona correctamente (~9s por consulta)
- Se integra en `ura_openclaw_client.py` como modo "ollama_direct"
- Autodetectado automáticamente cuando Ollama está disponible

**Modos disponibles** (autodetección en orden de prioridad):
1. `ollama_direct` - Ollama directo en puerto 11434 (recomendado, funciona)
2. `http` - OpenClaw HTTP endpoint
3. `subprocess` - OpenClaw binario local (timeout persistente)
4. `stub` - Respuesta sintética (fallback)

**Uso**:
```bash
# Ollama directo se detecta automáticamente
python3 ura_search.py "tema" --json

# Forzar stub si lo prefieres
export URA_OPENCLAW_STUB=1
python3 ura_search.py "tema" --json
```

### Gatekeeper de entrenamiento masivo N3

**Objetivo**: Controlar cuándo se ejecuta el entrenamiento masivo N3 para evitar ejecuciones innecesarias.

**Configuración por variables de entorno**:

```bash
# Umbral de semillas para activar entrenamiento (default 500)
export URA_TRAINING_VOLUME_THRESHOLD=500

# Umbral de días desde último entrenamiento (default 7)
export URA_TRAINING_TIME_THRESHOLD_DAYS=7
```

**Cómo funciona**:

El gatekeeper (`core/training_gatekeeper.py`) verifica dos condiciones antes de activar el entrenamiento:

1. **Volumen de semillas**: Si hay ≥ 500 semillas pendientes en `seed_pipeline`, activa entrenamiento
2. **Tiempo desde última activación**: Si han pasado ≥ 7 días desde el último entrenamiento, activa entrenamiento

Si cualquiera de las dos condiciones se cumple, el entrenamiento se activa automáticamente.

**Prueba manual**:

```bash
# Verificar si se debe activar entrenamiento
python -c "from core.training_gatekeeper import TrainingGatekeeper; print(TrainingGatekeeper().should_activate())"

# Activar entrenamiento si cumple condiciones
python -c "from core.training_gatekeeper import TrainingGatekeeper; TrainingGatekeeper().activate_if_ready()"
```

**Activación automática (crontab)**:

Para activar el entrenamiento automáticamente a las 3 AM diariamente, añade esta línea a tu crontab:

```bash
crontab -e
# Añadir esta línea:
0 3 * * * /bin/bash /Users/ramonesnaola/URA/ura_ia_1972/scripts/check_and_train.sh
```

**Script de activación**:

El script `scripts/check_and_train.sh` ejecuta el gatekeeper y activa el entrenamiento si se cumplen las condiciones.

**Estado de entrenamiento**:

El gatekeeper guarda el estado de entrenamiento en `~/.ura/training_state.json` con la fecha de última activación.

## Entrenamiento nocturno automático

El sistema entrena automáticamente cuando:
- Hay 500+ semillas pendientes en el pipeline
- Han pasado 7+ días desde el último entrenamiento

### Activación manual (para pruebas)

```bash
# Verificar si se debe activar entrenamiento
python -c "from core.training_gatekeeper import TrainingGatekeeper; print(TrainingGatekeeper().should_activate())"

# Activar entrenamiento si cumple condiciones
python -c "from core.training_gatekeeper import TrainingGatekeeper; print(TrainingGatekeeper().activate_if_ready())"
```

### Consultar estado del gatekeeper

```bash
python -c "from core.training_gatekeeper import TrainingGatekeeper; import json; print(json.dumps(TrainingGatekeeper().get_status(), indent=2))"
```

### Activación automática (cada noche)

Añade al crontab:

```bash
crontab -e
# Añadir esta línea:
0 3 * * * /bin/bash /Users/ramonesnaola/URA/ura_ia_1972/scripts/check_and_train.sh
```

### Logs de entrenamiento

El entrenamiento se loguea a `~/.ura/training.log` y los informes se guardan en `/Volumes/TOSHIBA_NUEVO/URA_entrenamiento/reports/informe_entrenamiento_YYYY-MM-DD.json`.

### OpenClaw como N3 complementario

**Objetivo**: Añadir OpenClaw como backend complementario para tareas autónomas, manteniendo Ollama directo como N3 principal.

**Arquitectura dual**:

- **Ollama directo** (N3 principal): Consultas rápidas, búsqueda, QA, descomposición
- **OpenClaw** (N3 complementario): Tareas autónomas (system, file_ops, multi_step)

**Cómo arrancar OpenClaw**:

```bash
# Arrancar OpenClaw vía Ollama
bash scripts/start_openclaw.sh
```

Este script:
- Actualiza Ollama
- Lanza OpenClaw usando `ollama launch openclaw --gateway --port 18789`
- Expone API REST en http://localhost:18789

**Cómo verificar que funciona**:

```bash
# Verificar salud de OpenClaw
python -c "from core.openclaw_health import check_openclaw_ready; print('OK' if check_openclaw_ready() else 'FALLO')"
```

**Routing automático**:

El `core/n3_orchestrator.py` rutea automáticamente según tipo de tarea:

- `system`, `file_ops`, `multi_step` → OpenClaw (si disponible) o Ollama fallback
- `search`, `qa`, `decompose` → Ollama directo (siempre)

**Degradación elegante**:

Si OpenClaw no está disponible o falla, el sistema sigue funcionando con Ollama directo. No hay bloqueo.

**Prueba de envío de tarea**:

```bash
# Probar envío de tarea a OpenClaw
python -c "from core.n3_orchestrator import N3Orchestrator; import asyncio; asyncio.run(N3Orchestrator().route_task('system', 'Crea un archivo hola.txt en /tmp/'))"
```

**Configuración por variables de entorno**:

```bash
# URL de OpenClaw (default: http://localhost:18789)
export OPENCLAW_URL=http://localhost:18789
```

### Sandbox (VM o local)

```bash
# Modo local actual (default)
export URA_SANDBOX_MODE=passthrough

# Cuando tengas la VM por SSH:
export URA_SANDBOX_MODE=ssh
export URA_SANDBOX_SSH_HOST=ura@vm.local
export URA_SANDBOX_SSH_KEY=~/.ssh/ura_vm

# Si usas Lima (https://lima-vm.io, alternativa Mac sin Docker):
export URA_SANDBOX_MODE=lima
export URA_SANDBOX_LIMA_NAME=ura-vm
```

El bridge garantiza que `fetch_page`, `run_command` y `run_openclaw` funcionan
con la misma API en los 3 modos. **No necesitas cambiar código** cuando
instales la VM.

## Uso

### CLI unificado (recomendado)

```bash
# Decisión automática del nivel
python ura_search.py "cuota autónomos 2025"

# Forzar nivel
python ura_search.py "tema X" --force-level N3
python ura_search.py "tema Y" --force-level N2

# Con maleta específica
python ura_search.py "fiscalidad" --maleta fiscal_autonomos_es_v1

# Salida JSON
python ura_search.py "tema" --json
```

### CLIs específicos

```bash
python ura_n2_search.py "tema"          # solo N2 (swarm local)
python ura_n3_search.py "tema"          # solo N3 (OpenClaw)
python ura_n3_search.py "tema" --no-learn  # N3 sin observación
```

### Programáticamente

```python
import asyncio
from ura_search import unified_search

payload = asyncio.run(unified_search("regulación IA España 2025"))
print("Nivel:", payload["decision"]["nivel"])
print("Resultados:", len(payload["resultados"]))
```

## Pipeline de aprendizaje observacional

```
Ejecución 1   ──► Observada (1/10) — no se promueve
Ejecución 2   ──► Observada (2/10) — no se promueve
...
Ejecución 10  ──► Examen de validación (lanza N2 con maleta candidata)
                  ├── Score Jaccard URLs ≥ 0.85 → PROMUEVE a N2 (confianza 0.65)
                  └── Score < 0.85              → No promueve, sigue observando
Ejecución 11+ ──► Si maleta ya existe → refuerzo (+0.02 confianza)
```

Cuando una maleta alcanza confianza ≥ 0.95 y uses ≥ 20, el router sugiere
exportarla a n8n (Fase 4 / N1) con `N2ToN8nExporter`.

## Mapa completo de niveles

| Decisión router | Cuándo | Acción |
|---|---|---|
| **N3** | Sin maleta o confianza < 0.6 | OpenClaw responde, learner observa |
| **N2+N3** | Confianza 0.6-0.85 | N2 responde rápido al usuario, N3 audita en background y aprende |
| **N2** | Confianza ≥ 0.85 | Swarm local con maleta, sin N3 |
| **N2 (sugerencia N1)** | Confianza ≥ 0.95 + uses ≥ 20 | Igual que N2 + sugerencia de exportar a n8n |

## Tests añadidos en F3

| Archivo | Tests |
|---|---|
| `tests/test_n3_openclaw_client.py` | 7 (detección modos, stub, normalize, manejo errores) |
| `tests/test_n3_observational_learner.py` | 7 (umbral, examen pasa/falla, persistencia) |
| `tests/test_n3_sandbox_bridge.py` | 9 (config env, run_command, comandos inexistentes) |
| `tests/test_ura_search_unified.py` | 7 (force-level, routing N2/N2+N3, parser CLI) |

**Total acumulado N2+N3: 106/106 passed.**

## Próximos pasos (cuando tengas la VM)

1. **Crear VM**: opciones recomendadas para Mac sin Docker:
   - **Lima**: `brew install lima` + `limactl start ura-vm`
   - **VirtualBox + Vagrant**
   - **UTM** (gratis, M1/M2 nativo)
2. **Instalar dentro de la VM**:
   ```bash
   pip install playwright duckduckgo-search aiohttp beautifulsoup4
   python -m playwright install chromium
   # OpenClaw + Ollama
   ```
3. **Activar el sandbox**:
   ```bash
   export URA_SANDBOX_MODE=lima      # o ssh
   export URA_SANDBOX_LIMA_NAME=ura-vm
   ```
4. **Validar**: `python ura_search.py "test"` — todo el I/O ahora pasará por la VM.

# Contexto de Sesión — 2026-06-09

## Resumen de lo hecho hoy

### 1. Tests de Propiedades con Hypothesis
**Archivo**: `tests/test_properties.py` — 23 tests, todos pasando

| Módulo | Tests | Cobertura |
|--------|-------|-----------|
| `memoria_fallos` | 7 + stateful | 100% |
| `memoria_movimiento` | 5 + stateful | 100% |
| `mochila_engine` | 6 | 93% |

Incluye `RuleBasedStateMachine` para memoria_fallos y memoria_movimiento (secuencias de operaciones).

### 2. Xvfb Virtual Display (GX10)
- **Service**: `ura-xvfb.service` en `:99` (1920x1080x24)
- **Script**: `scripts/pro/captura_virtual.py`
  - `CapturaVirtual.capturar()` — screenshot a `/tmp/ura-capturas/`
  - `CapturaVirtual.abrir()` — lanza GUI app en display virtual
  - `CapturaVirtual.ventanas()` — lista ventanas visibles

### 3. PLAN_MAESTRO.md Restaurado
- Perdido por filesystem bug, restaurado de git (`7054cab`)
- 80 líneas, describe el flujo distribuido España→Alemania

### 4. OpenClaw Gateway
- **URL**: `http://10.164.1.99:18789`
- **Token**: `663d5e6b3b72780013730dbba0c767d4d918d88d48dcd634`
- **Dashboard**: `http://10.164.1.99:18789/#token=...`
- **PID**: 456036 + 456100 (mcp)
- **Conectar desde Mac**: URL directa o SSH tunnel

---

## Estado Actual del Sistema

### GX10 (10.164.1.99)
| Componente | Puerto | Estado |
|-----------|--------|--------|
| Ollama | 11434 | ✅ loopback, MAX_LOADED_MODELS=2 |
| Model Router | 11435 | ✅ cache 5min |
| OpenCode | 8081 | ✅ |
| ura-executor | 4096 | ✅ con restaurar.sh |
| OpenClaw | 18789 | ✅ token auth |
| ura-audit-api | - | ✅ |
| ura-ssh-guard | - | ✅ |
| ura-xvfb | :99 | ✅ nuevo |
| tuneladora.timer | - | ✅ cada 6h |
| RAM | 79/121 GB | 65% usado |

### Ollama — 10 modelos
| Modelo | Tamaño |
|--------|--------|
| llama3.3:70b | 42 GB |
| qwen3:32b-q8_0 | 34 GB |
| qwen2.5-coder:32b | 19 GB |
| qwen2.5-coder:q8_0 | 34 GB |
| codestral:22b | 12 GB |
| qwen2.5-coder:14b | 9.0 GB |
| qwen2.5:7b | 4.7 GB |
| deepseek-coder:6.7b | 3.8 GB |
| llama3.2-vision:11b | 7.8 GB |
| nomic-embed-text | 274 MB |

### Git
- **Branch**: `dev/v3.1-expansion`
- **Último commit**: `9f30f61` — fix guardian + MCP OpenClaw
- **Total tests**: 38 (23 hypothesis + 15 existentes)

---

## Red

| Interfaz | IP | Métrica |
|----------|-----|---------|
| Ethernet | 10.164.1.99 | 50 |
| WiFi (fallback) | 10.164.1.247 | 600 |
| Tailscale | 100.72.103.12 | - |

### Tailscale — peers relevantes
- `mac-mini-de-ramon` 100.123.81.101 ✅ activo
- `hetzner-escudo` 100.78.49.106 ⚠️ relay (sin conexión directa)
- `gx10-64c3` 100.127.206.86 (otra interfaz, offline 4d)

---

## Estructura de Archivos Relevante

```
ura_ia_1972/
├── tests/test_properties.py          ← NUEVO (23 hypothesis tests)
├── scripts/pro/captura_virtual.py    ← NUEVO (Xvfb capture)
├── PLAN_MAESTRO.md                   ← Restaurado de git
├── memoria_fallos.py                 ← Memoria de fallos
├── memoria_movimiento.py             ← Memoria de cubos
├── mochila_engine.py                 ← Motor de mochilas
├── core/
│   ├── guardians/ast_sentinel.py     ← Capa 1 Zero-Patch
│   ├── sandbox/docker_orchestrator.py
│   └── cleaner/cold_refractor.py
├── cli/gatekeeper.py                 ← CLI ura
└── ura-audit                         ← 10 herramientas
```

---

## Comandos Útiles

```bash
# Tests hypothesis
python3 -m pytest tests/test_properties.py -v

# Todos los tests existentes
python3 -m pytest test_memoria_fallos.py test_memoria_movimiento.py test_mochila.py -v

# Cobertura
python3 -m pytest tests/test_properties.py --cov=memoria_fallos --cov=memoria_movimiento --cov=mochila_engine --cov-report=term

# Xvfb capture
DISPLAY=:99 python3 scripts/pro/captura_virtual.py

# Lint
ruff check .

# Auditoría completa
bash tuneladora.sh

# URA audit (10 tools)
./ura-audit

# Contexto para IA
bash ura-contexto
```

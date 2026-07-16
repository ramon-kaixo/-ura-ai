# Auditoría de Secretos — F17.5

**Fecha:** 2026-07-16  
**Alcance:** Todos los archivos `.py`, `.sh`, `.env`, `.json`, `.yaml`, `.yml`, `.toml`, `.cfg`, `.conf`  
**Excluidos:** `.git/`, `__pycache__/`, `.venv/`, `build/`, `node_modules/`  
**Herramientas:** `grep`, `ast` analysis manual

---

## Resumen

| Métrica | Valor |
|---------|-------|
| Archivos analizados | ~1,100 |
| Env vars referenciadas via `os.getenv()` / `os.environ.get()` | 107 |
| Fallos críticos (hardcoded secrets) | 6 |
| Fallos altos (.env en repo) | 1 |
| Fallos medios (weak defaults docker) | 4 |
| Fallos bajos | 2 |
| Secretos correctamente gestionados via env vars | 107+ |

---

## 🔴 Críticos

### C01 — Password en `deploy/lildax_config.json`

| Campo | Valor |
|-------|-------|
| **Archivo** | `deploy/lildax_config.json:5` |
| **Tipo** | Password hardcodeado |
| **Valor** | `"password": "ura_1972_secure_autonomous"` |
| **Origen** | Configuración de servicio lildax |
| **Riesgo** | El password está en texto plano en el repositorio. Cualquiera con acceso al repo obtiene acceso al servicio. |

**Propuesta:** Reemplazar por variable de entorno `${LILDAX_PASSWORD}` con fallback vacío o fail cerrado.

---

### C02 — Password en `deploy/install_opencode_mac.sh`

| Campo | Valor |
|-------|-------|
| **Archivo** | `deploy/install_opencode_mac.sh:47` |
| **Tipo** | Password hardcodeado |
| **Valor** | `"ura_1972_secure_autonomous"` |
| **Origen** | Script de instalación de OpenCode en Mac |
| **Riesgo** | Mismo password que C01, duplicado en script shell. |

**Propuesta:** Extraer a variable de entorno y leer desde `~/.opencode/secrets.env` o similar.

---

### C03 — Fallback API Key en `core/auth_layer.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `core/auth_layer.py:7` |
| **Tipo** | API Key hardcodeada como fallback |
| **Valor** | `"ura_1972_secure_default"` |
| **Origen** | `os.environ.get("URA_API_KEY", "ura_1972_secure_default")` |
| **Riesgo** | Si `URA_API_KEY` no está definida, se usa una clave predecible. Cualquiera que conozca el código puede autenticarse. |

**Propuesta:** Eliminar el fallback. Si la env var no está definida, lanzar error o usar un flag que deshabilite autenticación solo en desarrollo.

---

### C04 — VNC Password en `app/capturador.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `app/capturador.py:38` |
| **Tipo** | Password hardcodeado como fallback |
| **Valor** | `"ura2026"` |
| **Origen** | `os.getenv("VNC_PWD", "ura2026")` |
| **Riesgo** | Conexión VNC con password por defecto conocido. |

**Propuesta:** Eliminar fallback, fail cerrado si `VNC_PWD` no está definida.

---

### C05 — VNC Password en `scripts/pro/uitars_hetzner.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `scripts/pro/uitars_hetzner.py:12` |
| **Tipo** | Password hardcodeado |
| **Valor** | `VNC_PASS = "ura2026"` |
| **Origen** | Módulo de gestión de Hetzner |
| **Riesgo** | Mismo password que C04, hardcodeado en código. |

**Propuesta:** Migrar a env var `VNC_PWD` con fail cerrado si no está definida.

---

### C06 — Grafana Password por defecto en docker-compose

| Campo | Valor |
|-------|-------|
| **Archivo** | `deploy/docker/docker-compose.yml:113` |
| **Tipo** | Password débil por defecto |
| **Valor** | `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-grafana123}` |
| **Origen** | Docker compose para despliegue |
| **Riesgo** | Si no se configura `GRAFANA_PASSWORD`, se usa `grafana123`. |

**Propuesta:** Eliminar fallback, exigir `GRAFANA_PASSWORD` o documentar que debe cambiarse.

---

## ⚠️ Alto

### A01 — `.env` commiteado al repositorio

| Campo | Valor |
|-------|-------|
| **Archivo** | `.env` (raíz del proyecto) |
| **Tipo** | Placeholder keys |
| **Valor** | `GROQ_API_KEY="gsk_..."`, `DEEPSEEK_API_KEY="sk_..."` |
| **Origen** | Template de desarrollo |
| **Riesgo** | Aunque son placeholders, `.env` debería estar exclusivamente en `.gitignore`. Su presencia en el repo puede normalizar la práctica de commitear secretos. |

**Propuesta:** Eliminar `.env` del repositorio. Mantener solo `.env.example` y `.env.secrets.template`.

---

## ⚠️ Medio

### M01 — WebUI Secret Key débil

`deploy/docker/docker-compose.yml:23`: `WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY:-ura_webui_secret_2026}`

### M02 — N8N Encryption Key débil

`deploy/docker/docker-compose.yml:41`: `N8N_ENCRYPTION_KEY=${N8N_KEY:-ura_n8n_key}`

### M03 — Frigate RTSP Password débil

`deploy/docker/docker-compose.yml:63`: `FRIGATE_RTSP_PASSWORD=${FRIGATE_RTSP_PASSWORD:-ura_cam_2026}`

### M04 — Linksys Router Password

`scripts/pro/bypass_linksys_gui.py:62`: `ROUTER_PASSWORD` con fallback vacío. Correcto (usa env var) pero elevar a crítica si el router es accesible desde red externa.

---

## Environment Variables de Secretos (Inventario Completo)

### API Keys (requieren migración a motor.core.secrets)

| Env Var | Consumidor | Origen | Default | Criticidad |
|---------|-----------|--------|---------|------------|
| `GROQ_API_KEY` | `core/mochila/providers/groq.py:17` | `os.getenv()` | `""` | Alta |
| `GEMINI_API_KEY` | `core/mochila/providers/gemini.py:16` | `os.getenv()` | `""` | Alta |
| `DEEPSEEK_API_KEY` | `core/mochila/providers/deepseek.py:17` | `os.getenv()` | `""` | Alta |
| `OPENROUTER_API_KEY` | `core/mochila/providers/openrouter.py:17` | `os.getenv()` | `""` | Alta |
| `URA_API_KEY` | `core/auth_layer.py:7` | `os.getenv()` | `"ura_1972_secure_default"` | Crítica |
| `URA_API_KEY` | `knowledge/engine/api.py:54` | `os.getenv()` | `None` | Alta |
| `URA_API_KEY` | `knowledge/engine/cli/api.py:20` | `os.getenv()` | `None` | Alta |

### Tokens de Notificación

| Env Var | Consumidor | Origen | Default | Criticidad |
|---------|-----------|--------|---------|------------|
| `PUSHOVER_USER_KEY` | `core/notifier.py:18` | `os.getenv()` | `""` | Alta |
| `PUSHOVER_APP_TOKEN` | `core/notifier.py:19` | `os.getenv()` | `""` | Alta |
| `TELEGRAM_TOKEN` | `core/notifier.py:25` | `os.getenv()` | `""` | Alta |
| `TELEGRAM_CHAT_ID` | `core/notifier.py:26` | `os.getenv()` | `""` | Alta |
| `PUSHOVER_USER_KEY` | `agents/agente_sandbox_codigo.py:31` | `os.getenv()` | `""` | Alta |
| `PUSHOVER_APP_TOKEN` | `agents/agente_sandbox_codigo.py:32` | `os.getenv()` | `""` | Alta |

### SMTP / Email

| Env Var | Consumidor | Origen | Default | Criticidad |
|---------|-----------|--------|---------|------------|
| `URA_SMTP_HOST` | `knowledge/engine/notify.py:288` | `os.getenv()` | `""` | Media |
| `URA_SMTP_PORT` | `knowledge/engine/notify.py:289` | `os.getenv()` | `"587"` | Media |
| `URA_SMTP_USER` | `knowledge/engine/notify.py:290` | `os.getenv()` | `""` | Media |
| `URA_SMTP_PASS` | `knowledge/engine/notify.py:291` | `os.getenv()` | `""` | Alta |
| `URA_EMAIL_FROM` | `knowledge/engine/notify.py:292` | `os.getenv()` | `"ura@localhost"` | Baja |
| `URA_EMAIL_TO` | `knowledge/engine/notify.py:293` | `os.getenv()` | `""` | Baja |

### Gateway / OpenClaw

| Env Var | Consumidor | Origen | Default | Criticidad |
|---------|-----------|--------|---------|------------|
| `OPENCLAW_GATEWAY_TOKEN` | `agent_hierarchy.py:17` | `os.getenv()` | `""` | Alta |
| `OPENCLAW_GATEWAY_TOKEN` | `core/model_router.py:73` | `os.getenv()` | `None` | Alta |

### Router / Red

| Env Var | Consumidor | Origen | Default | Criticidad |
|---------|-----------|--------|---------|------------|
| `ROUTER_PASSWORD` | `scripts/pro/bypass_linksys_gui.py:62` | `os.getenv()` | `""` | Alta |
| `VNC_PWD` | `app/capturador.py:38` | `os.getenv()` | `"ura2026"` | Crítica |
| `VNC_PWD` | `scripts/pro/uitars_hetzner.py:12` | `hardcoded` | `"ura2026"` | Crítica |
| `URA_SSH_USER` | `motor/scanner/collector_asus.py:62` | `os.getenv()` | `""` | Media |

### Otras Variables de Entorno (No Secretos)

Enumeradas a continuación para completitud, pero no son secretos:

`URA_CONFIG`, `URA_QDRANT_HOST`, `URA_QDRANT_PORT`, `URA_TIMER_INTERVAL_MIN`,
`URA_LOG_LEVEL`, `URA_NODE_ENV`, `URA_ROOT`, `URA_LOG_DIR`, `ASUS_EXEC_URL`,
`MODEL_ROUTER_URL`, `GROQ_BASE_URL`, `GEMINI_BASE_URL`, `DEEPSEEK_BASE_URL`,
`OPENROUTER_BASE_URL`, `SEARXNG_URL`, `DUCKDUCKGO_URL`, `HTTPS_PROXY`,
`HTTP_PROXY`, `MOCHILA_DEFAULT_ENGINE`, `MOCHILA_*`, `REFACTOR_*`,
`SANDBOX_*`, `DRY_RUN`, `MAC_IP`, `HETZNER_HOST`, `ROUTER_IP`, `ASUS_WIFI`,
`ASUS_CABLE`, `REVIEWER_MODEL`, `REVIEWER_TIMEOUT`, `MCP_SYNC_URL`,
`EXECUTOR_HOST`, `EXECUTOR_PORT`, `GUARDIAN_LOG`, `QDRANT_URL`,
`TAILSCALE_USER`, `CHUNK_CONFIG`, `WATERMARKS_PATH`, `CONCIENCIA_PATH`,
`REGLAS_PATH`, `REGLAS_CONFIG`, `URA_EMAIL_FROM`, `URA_EMAIL_TO`,
`URA_SMTP_HOST`, `URA_SMTP_PORT`, `URA_SMTP_USER` (sensible), `URA_AUTH_ENABLED`.

---

## Backends Actuales

Actualmente no existe un gestor de secretos unificado. Cada consumidor:

1. Lee `os.getenv()` directamente
2. Con fallback hardcodeado (C03, C04, C05) o vacío
3. Sin validación de existencia

**Propuesta de arquitectura (F17.5-B2):** `motor/core/secrets.py` con backends:
- `env` — lee de variables de entorno (actual)
- `file` — lee de archivo local no versionado (`/etc/ura/secrets.env`)
- `secret_manager` — preparado para Secret Manager externo futuro

---

## Propuesta de Migración

| ID | Consumidor | Secret | Prioridad | Bloque B3 |
|----|-----------|--------|-----------|-----------|
| M01 | `core/auth_layer.py` | `URA_API_KEY` | 🔴 B3.1 | motor |
| M02 | `core/notifier.py` | `PUSHOVER_USER_KEY`, `PUSHOVER_APP_TOKEN`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | 🔴 B3.1 | motor |
| M03 | `core/mochila/providers/groq.py` | `GROQ_API_KEY` | 🔴 B3.1 | motor |
| M04 | `core/mochila/providers/gemini.py` | `GEMINI_API_KEY` | 🔴 B3.1 | motor |
| M05 | `core/mochila/providers/deepseek.py` | `DEEPSEEK_API_KEY` | 🔴 B3.1 | motor |
| M06 | `core/mochila/providers/openrouter.py` | `OPENROUTER_API_KEY` | 🔴 B3.1 | motor |
| M07 | `knowledge/engine/api.py` | `URA_API_KEY` | 🔴 B3.2 | knowledge |
| M08 | `knowledge/engine/notify.py` | `URA_SMTP_PASS` | 🔴 B3.2 | knowledge |
| M09 | `core/auth_layer.py` | `URA_AUTH_ENABLED` | 🟡 B3.3 | core |
| M10 | `agent_hierarchy.py` | `OPENCLAW_GATEWAY_TOKEN` | 🟡 B3.3 | core |
| M11 | `core/model_router.py` | `OPENCLAW_GATEWAY_TOKEN` | 🟡 B3.3 | core |
| M12 | `scripts/pro/bypass_linksys_gui.py` | `ROUTER_PASSWORD` | 🟢 B3.4 | scripts |
| M13 | `app/capturador.py` | `VNC_PWD` | 🔴 B3.1 | motor |
| M14 | `scripts/pro/uitars_hetzner.py` | `VNC_PWD` | 🔴 B3.4 | scripts |

---

## Recomendaciones Post-F17.5

1. Eliminar `.env` del repositorio (A01)
2. Añadir `.gitleaks.toml` para CI/CD
3. Añadir `dahua_cameras.json` al `.gitignore`
4. Migrar `deploy/lildax_config.json` a env vars
5. Migrar `deploy/install_opencode_mac.sh` a env vars
6. Eliminar fallbacks hardcodeados (C03, C04, C05)
7. Añadir tests de auditoría automática en CI

---

## Archivos con Hardcoded Passwords (requieren acción manual fuera de F17.5 scope)

| Archivo | Línea | Valor |
|---------|-------|-------|
| `deploy/lildax_config.json` | 5 | `ura_1972_secure_autonomous` |
| `deploy/install_opencode_mac.sh` | 47 | `ura_1972_secure_autonomous` |
| `deploy/docker/docker-compose.yml` | 23 | `ura_webui_secret_2026` |
| `deploy/docker/docker-compose.yml` | 41 | `ura_n8n_key` |
| `deploy/docker/docker-compose.yml` | 63 | `ura_cam_2026` |
| `deploy/docker/docker-compose.yml` | 113 | `grafana123` |

Estos archivos están fuera del alcance de migración automática de F17.5 porque no son módulos Python.
Requieren refactorización manual para usar variables de entorno.

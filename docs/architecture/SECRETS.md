# Gestión de Secretos — URA (F17.5)

## Arquitectura

Los secretos se gestionan centralizadamente a través de `motor/core/secrets.py`,
que expone una API unificada con backends intercambiables:

```
┌─────────────────────────────────────────────┐
│              Consumidor                      │
│  core/auth_layer.py                          │
│  core/mochila/providers/*.py                 │
│  knowledge/engine/api.py                     │
│  ...                                         │
└──────────────┬──────────────────────────────┘
               │ get_secret() / require_secret()
               ▼
┌─────────────────────────────────────────────┐
│           motor.core.secrets                 │
│                                              │
│  1. os.environ  (máxima prioridad)          │
│  2. /etc/ura/secrets.env  (archivo local)   │
│  3. default  (fallback del consumidor)      │
│  4. Secret Manager  (futuro)               │
└─────────────────────────────────────────────┘
```

## Precedencia

El orden de resolución de `get_secret(name, default)` es:

| Prioridad | Backend | Descripción |
|-----------|---------|-------------|
| 1 (alta) | `os.environ` | Variable de entorno del sistema |
| 2 | `/etc/ura/secrets.env` | Archivo local no versionado (KEY=VALUE) |
| 3 (baja) | `default` | Valor por defecto proporcionado por el consumidor |

## API

### `get_secret(name, default=None) -> str | None`

Obtiene un secreto. Retorna `None` si no se encuentra en ningún backend.

```python
from motor.core.secrets import get_secret

api_key = get_secret("GROQ_API_KEY")
token = get_secret("PUSHOVER_APP_TOKEN", default="")
```

### `require_secret(name) -> str`

Obtiene un secreto o lanza `KeyError` si no está disponible.

```python
from motor.core.secrets import require_secret

api_key = require_secret("URA_API_KEY")
```

### `has_secret(name) -> bool`

Verifica si un secreto está disponible (no vacío).

```python
if has_secret("TELEGRAM_TOKEN"):
    send_telegram("Alerta")
```

### `list_available() -> list[str]`

Lista los secretos definidos en `KNOWN_SECRETS` que están disponibles actualmente.

```python
disponibles = list_available()
print(f"Secretos disponibles: {disponibles}")
```

## Secretos Conocidos

La lista completa de secretos conocidos está definida en `motor/core/secrets.KNOWN_SECRETS`.
Incluye:

| Categoría | Variables |
|-----------|-----------|
| API Keys | `GROQ_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `URA_API_KEY` |
| Notificaciones | `PUSHOVER_USER_KEY`, `PUSHOVER_APP_TOKEN`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` |
| Gateway | `OPENCLAW_GATEWAY_TOKEN` |
| SMTP | `URA_SMTP_HOST`, `URA_SMTP_PORT`, `URA_SMTP_USER`, `URA_SMTP_PASS`, `URA_EMAIL_FROM`, `URA_EMAIL_TO` |
| Red | `ROUTER_PASSWORD`, `VNC_PWD` |
| Docker | `WEBUI_SECRET_KEY`, `N8N_KEY`, `FRIGATE_RTSP_PASSWORD`, `GRAFANA_PASSWORD` |

## Configuración

### Variables de Entorno

```bash
export GROQ_API_KEY="gsk_tu_key_aqui"
export URA_API_KEY="mi_clave_segura"
```

### Archivo Local (`/etc/ura/secrets.env`)

Formato KEY=VALUE, una por línea. Comentarios con `#`.

```bash
# Secretos de URA
GROQ_API_KEY=gsk_tu_key_aqui
URA_API_KEY=mi_clave_segura
TELEGRAM_TOKEN=123456:ABC-DEF1234
```

El archivo se lee una vez y se cachea en memoria. No se versiona en git
(el directorio `/etc/ura/` está fuera del repositorio).

## Migración

Para migrar un consumidor de acceso directo a `motor.core.secrets`:

```python
# Antes
api_key = os.environ.get("GROQ_API_KEY", "")

# Después
from motor.core.secrets import get_secret
api_key = get_secret("GROQ_API_KEY", "")
```

Para secretos requeridos (fail fast):

```python
# Antes
token = os.environ.get("URA_API_KEY")
if not token:
    sys.exit(1)

# Después
from motor.core.secrets import require_secret
token = require_secret("URA_API_KEY")
```

## Rotación

Para rotar un secreto:

1. Actualizar el valor en `/etc/ura/secrets.env`
2. Limpiar la caché del proceso (o reiniciar el servicio)
3. Verificar con `scripts/pro/audit_secrets.py --path=<directorio>`

## Recuperación

Si un secreto se pierde:

1. Verificar que la variable de entorno existe: `echo $GROQ_API_KEY`
2. Verificar el archivo de secretos: `cat /etc/ura/secrets.env`
3. El consumidor debe tener un fallable (`get_secret` con `default`) o lanzar
   error claro (`require_secret` → `KeyError`)
4. Ejecutar `scripts/pro/audit_secrets.py` para diagnosticar accesos directos

## Buenas Prácticas

1. **No hardcodear secretos** — usar `get_secret()` con fallback vacío o
   `require_secret()` para fail fast.
2. **No versionar archivos de secretos** — `.env`, `secrets.env`, `*.secret`
   están en `.gitignore`.
3. **Usar el menor privilegio** — cada consumidor solo accede a los secretos
   que necesita.
4. **Validar en CI** — `scripts/pro/audit_secrets.py` en pre-commit hook.
5. **Rotar periódicamente** — cambiar claves cada 90 días.
6. **Loggear sin exponer** — nunca loguear valores de secretos completos.

## Auditoría Automática

```bash
# Escanear todo el proyecto
python3 scripts/pro/audit_secrets.py

# Escanear un directorio específico
python3 scripts/pro/audit_secrets.py --path=core/mochila

# Salida JSON
python3 scripts/pro/audit_secrets.py --json
```

El script detecta:
- Secretos hardcodeados (API keys, tokens, passwords)
- URLs con credenciales en texto plano
- Variables con nombre de secreto asignadas a valores literales
- Acceso directo a env vars secretas sin pasar por `motor.core.secrets`

## Referencias

- `motor/core/secrets.py` — Implementación del gestor de secretos
- `docs/architecture/SECRETS_AUDIT.md` — Auditoría completa del proyecto
- `scripts/pro/audit_secrets.py` — Script de auditoría automática

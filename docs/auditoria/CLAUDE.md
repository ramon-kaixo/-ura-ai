# URA — Contexto completo para Claude

## Qué es URA

URA (nombre en clave) es un sistema de agentes de IA local que corre en el Mac de su autor. Su propósito es automatizar tareas del día a día: leer mensajería (Telegram, email), ejecutar código, gestionar archivos, hacer backups, vigilar el sistema y conectar con modelos de IA locales (Ollama) y remotos (Claude, GPT-4, Gemini).

**No es un producto comercial.** Es una herramienta personal en desarrollo activo. El autor no es desarrollador de formación — trabaja con Windsurf y Claude Code como asistentes principales.

**Regla fundamental:** No crear modelos duplicados ni fine-tuning. Toda la personalización se hace con System Prompts sobre modelos base.

---

## Directorios del proyecto

| Directorio | Rol |
|---|---|
| `~/Desktop/URA_App` | **Proyecto activo** — aquí se trabaja siempre |
| `~/URA/ura_ia_1972` | Proyecto original, referencia histórica. No tocar. |

> URA_DNA y URA_Backups fueron eliminados el 2026-04-30 (eran backups redundantes de 4.85 GB).

---

## Estructura interna de URA_App

```
URA_App/
├── main_final.py          # GUI principal PyQt5 (~5000 líneas — monolito pendiente de dividir)
├── core/                  # 53 módulos activos
├── agents/                # 83 agentes especializados
├── connectors/            # ollama_connector.py (activo), otros
├── scripts/               # 54 scripts operacionales
├── config/                # Configuraciones JSON
├── tests/                 # 19 tests
├── dashboard/             # Web dashboard (app.py + templates)
├── gateway/               # api_gateway.py
├── monitoring/            # Configs Grafana + Prometheus
├── logs/                  # Logs rotativos JSON
└── core/code_agents/      # 26 agentes generadores de código
```

---

## Qué funciona realmente (módulos con lógica real)

| Módulo | Qué hace |
|---|---|
| `connectors/ollama_connector.py` | Conecta con Ollama local (llama3.2:3b, llama3, qwen2.5:3b, llava, mxbai-embed-large). Cache Redis, streaming real. Máx 3 reintentos + modo degradado. |
| `core/workflow_engine.py` | Motor principal. Flujo Director Técnico → guardrails anti-bypass IA comercial. |
| `core/thread_cleaner.py` | Limpia hilos zombies. Arquitectura KILL_ALLOWED / REPORT_ONLY — respetar siempre esta distinción. |
| `core/network_audit.py` | Escanea puertos, health check APIs, detecta conflictos (puertos fijos: Ollama 11434, Grafana 3000). |
| `core/agente_policia_v2.py` | Valida comandos con 3 checkpoints: patrones → LLM → consenso. Bloquea rm -rf, fork bombs, etc. |
| `core/semantic_memory.py` | Almacena hechos verificados con niveles crítico/procedimiento/ruido. **OJO:** usa SHA256 como "embeddings" — no es semántico real. Pendiente reemplazar con modelo de embeddings real. |
| `core/circuit_breaker.py` | Patrón CircuitBreaker real (CLOSED/OPEN/SEMI_OPEN) con persistencia en JSONL. |
| `core/payment_guardian.py` | Umbrales: <10€ auto, 10-49€ notifica, ≥100€ bloquea. Audit log append-only. |
| `core/privacy_scrubber.py` | Sanitiza username, rutas, credenciales antes de enviar a APIs externas. |
| `core/consensus_system.py` | Decisiones multi-agente por mayoría simple (>50%). |
| `agents/agente_banco.py` | SQLite real, conciliación de extractos CSV. |
| `agents/agente_email.py` | IMAP real con imaplib, SQLite. |
| `agents/agente_supervisor.py` | psutil real para CPU/RAM/disco. |

---

## Lo que es stub / fake / incompleto

| Módulo | Problema |
|---|---|
| `core/code_agents/generators/` (10 archivos) | `generar()` devuelve un template con `pass`. No genera código real. |
| `core/semantic_memory.py` | SHA256 ≠ embeddings semánticos. Dos frases similares producen vectores totalmente distintos. |
| `core/workflow_engine.py` líneas 580-630 | `simulate_windsurf_execution()` devuelve texto hardcodeado según keywords. Placeholder explícito. |
| `core/buscadores/buscador_noticias.py` | Devuelve noticias con URL `https://example.com/...`. Simulado explícitamente. |
| `core/storage_manager.py` | Google Drive y Dropbox son placeholders sin API real. |
| Face ID / biometría | `biometrico_ok = True` sin verificar nada. |
| `agents/agente_seguridad.py` | **No importable.** Usa `from ejecutor_seguro import ejecutar` y `from internet import get_url` — módulos que no existen. |

---

## Arquitectura de seguridad

### Capas activas
1. **agente_policia_v2.py** — 3 checkpoints antes de ejecutar cualquier comando
2. **consensus_system.py** — decisiones críticas requieren mayoría de agentes
3. **privacy_scrubber.py** — sanitiza antes de enviar a APIs externas
4. **change_guardian.py** — protege archivos críticos del sistema
5. **action_signer.py** — firma digital de acciones para trazabilidad
6. **payment_guardian.py** — bloquea transacciones ≥100€ automáticamente
7. **circuit_breaker.py** — corta servicios externos que fallen repetidamente

### Lo que NO está implementado (aunque el código existe)
- Face ID real (siempre devuelve True)
- Zero trust real (calcula score de 100 puntos sobre un dict, sin criptografía)
- WAF real (lista de patrones en memoria sin HTTP stack)

---

## Sistema de mantenimiento

| Módulo | Función |
|---|---|
| `core/thread_cleaner.py` | Zombies y procesos. **KILL_ALLOWED** = puede matar. **REPORT_ONLY** = solo informa. Ollama está en protected_processes. |
| `core/network_audit.py` | Auditoría de puertos y APIs. Puertos fijos: Ollama 11434, Grafana 3000, n8n 5678. |
| `core/disk_cleaner.py` | Docker, pip cache, npm, brew, logs >30 días. |
| `core/disk_monitor.py` | Alerta <5 GB (warning), <1 GB (crítico). |
| `core/cloud_backup.py` | Backup a iCloud con verificación nativa brctl. |

---

## Cajas de arena (sandboxes) y Docker

- `core/error_sandbox.py` — analiza errores no resueltos en entorno aislado antes de intentar reparación
- `docker-compose.yml` — stack completo: PostgreSQL, Redis, Grafana, Prometheus, nginx
- **PostgreSQL** corre en Docker, password por variable de entorno `POSTGRES_PASSWORD`
- **Redis** se usa como cache en ollama_connector.py
- Los directorios `infra/` y `nginx/` tienen configs pero el stack no siempre está levantado

Para levantar el stack: `docker-compose up -d`

---

## Sistema QA (activo desde 2026-04-30)

El pre-commit hook bloquea commits si:
- **Ruff** detecta errores de formato o imports (se autocorrige)
- **Bandit** detecta issues MEDIUM o HIGH de seguridad

Solo advierte (no bloquea):
- **mypy** — errores de tipos (modo legacy por ahora)
- **pytest** — tests fallando

Para ejecutar QA manual: `./qa_check.sh`

---

## Modelos de IA disponibles

| Modelo | Dónde | Uso |
|---|---|---|
| llama3.2:3b | Ollama local | Modelo rápido por defecto |
| llama3:latest | Ollama local | Tareas generales |
| qwen2.5:3b-instruct | Ollama local | Instrucciones técnicas |
| llava:latest | Ollama local | Visión (imágenes) |
| mxbai-embed-large | Ollama local | Embeddings (pendiente integrar en semantic_memory) |
| Claude API | Remoto | Tareas complejas |
| GPT-4 | Remoto | Validación externa |
| Gemini | Remoto | Validación externa |

**ram_manager.py** cambia dinámicamente de modelo según RAM disponible.

---

## Conectores de mensajería

- `telegram_reader.py` — lee y procesa mensajes de Telegram
- `whatsapp_reader.py` — WhatsApp
- `email_reader.py` — IMAP
- `instagram_reader.py` — Instagram

**IMPORTANTE:** El token de Telegram estuvo expuesto en Git (telegram_config.json). Si el bot no responde, revocar en @BotFather y regenerar.

---

## Deuda técnica conocida (no urgente pero registrada)

| Archivo | Problema |
|---|---|
| `main_final.py` (~5000 líneas) | Monolito: mezcla GUI + lógica + threads + imports. Dividir en fases. |
| `core/error_auto_repair.py` (~2000 líneas) | Mezcla ML, PDF, Slack, Teams, Prometheus, MLflow. Dividir en 5-6 módulos. |
| `semantic_memory.py` | Reemplazar SHA256 por mxbai-embed-large (ya instalado en Ollama) |
| `agents/agente_seguridad.py` | No importable. Requiere crear ejecutor_seguro.py e internet.py o reescribir |
| `.boveda_key` en Git | Clave Fernet en historial. Rotar + limpiar historial con git filter-repo |

---

## Cómo trabajar con este proyecto

- **Windsurf** hace los cambios de código
- **Claude Code** hace auditorías, planifica, da instrucciones a Windsurf
- El autor da instrucciones en español, a veces por voz (puede haber errores de transcripción)
- Cuando algo no arranca: buscar NameError / ImportError en main_final.py primero
- Antes de cualquier cambio grande: `git status` para ver estado limpio
- Después de cada grupo de cambios: commit con mensaje descriptivo

---

## Estado del proyecto (2026-04-30)

| Aspecto | Estado |
|---|---|
| Madurez real | ~50% — mejoró desde 40% tras limpieza |
| Git | Inicializado, 4 commits limpios |
| QA | Activo (ruff + bandit en pre-commit) |
| Seguridad | Mejorada — secrets movidos a variables de entorno |
| Ollama | Funcionando (máx 3 reintentos, luego modo degradado) |
| Grafana | Funcionando en localhost:3000 |
| Pendiente crítico | Rotar token Telegram + limpiar historial Git |

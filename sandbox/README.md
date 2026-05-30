# SAN BOX — Los 4 entornos autónomos de URA

## Arquitectura general

Cada San box es un contenedor Docker con un propósito fijo. Todos comparten:
- Base `python:3.12-slim`
- Acceso a Ollama en GX10 (`http://10.164.1.99:11434`)
- Máximos privilegios restados (`cap_drop ALL`, `no-new-privileges`)
- Límite de memoria (1-2 GB)
- `restart: unless-stopped`

```
URA
└── 📦 SAN BOX
    ├── 🔒 Seguridad       → nmap + bandit + integridad
    ├── 🔧 Mantenimiento   → limpieza + refactor + optimización
    ├── 📚 Documentacion   → informes + métricas + git log
    └── 🧠 Aprendizaje     → 26 buzos + LLM + biblioteca
```

---

## 🔒 1. SEGURIDAD

**Docker:** `ura-sandbox-seguridad` · 1 GB RAM · Red bridge

### Qué contiene

```bash
sandbox/Seguridad/
├── Dockerfile              # python:3.12-slim + nmap + curl + jq + openssh
├── docker-compose.yml
└── scripts/
    ├── ejecutar_seguridad.sh    # Entrypoint principal
    ├── run.sh                   # Entrypoint legacy (fallo de rodillo)
    └── verify_inventory_integrity.sh
```

### Cómo funciona

**1. `ejecutar_seguridad.sh`** — Ciclo completo de seguridad:
1. Ejecuta **Bandit** en todo el código Python (`/opt/ura/`, repo)
2. Ejecuta **pip-audit** en dependencias
3. Verifica permisos de archivos sensibles (`.env`, claves SSH)
4. Genera reportes JSON en `auditoria/`

**2. `verify_inventory_integrity.sh`** — Verifica el Registry:
1. Consulta `http://127.0.0.1:5100/agents`
2. Comprueba heartbeat de cada agente
3. Testea puertos de infraestructura con `nc`
4. Falla con código de error si hay problemas

**3. `run.sh`** — Entrada mínima: solo registra la incidencia en log.

### Cuándo se ejecuta
- Gatillado por fallos de rodillo bloqueante en la tuneladora
- Bajo demanda: `docker exec ura-sandbox-seguridad bash scripts/ejecutar_seguridad.sh`

---

## 🔧 2. MANTENIMIENTO

**Docker:** `ura-sandbox-mantenimiento` · 1 GB RAM · Red bridge · Acceso a docker.sock

### Qué contiene

```bash
sandbox/Mantenimiento/
├── Dockerfile              # python:3.12-slim + git + curl + jq + pyyaml
├── docker-compose.yml
└── scripts/
    ├── ejecutar_mantenimiento.sh    # Entrypoint principal
    └── refactorizar_complejidad.sh  # Análisis de complejidad
```

### Cómo funciona

**1. `ejecutar_mantenimiento.sh`** — 5 tareas en secuencia:
1. **Limpia** `__pycache__` y `*.pyc` de todo el proyecto
2. **Purga** caché de pip
3. **Optimiza** bases de datos SQLite (`VACUUM; REINDEX`)
4. **Comprime** logs con más de 30 días
5. **Elimina** temporales `/tmp/ura_*`

**2. `refactorizar_complejidad.sh`** — Solo analiza (no modifica):
1. Ejecuta `radon cc` sobre todo el código Python
2. Identifica métodos con complejidad alta (F, E, D)
3. Genera reporte en `sandbox/Mantenimiento/logs/refactorizacion_*.txt`

### Acceso especial
Monta `/var/run/docker.sock` para poder inspeccionar y gestionar contenedores desde dentro del sandbox.

---

## 📚 3. DOCUMENTACIÓN

**Docker:** `ura-sandbox-documentacion` · 1 GB RAM · Red bridge · Puerto 8087

### Qué contiene

```bash
sandbox/Documentacion/
├── Dockerfile              # python:3.12-slim + pandoc + texlive + mkdocs + pdoc
├── docker-compose.yml
└── scripts/
    ├── ejecutar_documentacion.sh    # Entrypoint principal
    └── generate_report.sh           # Genera informe de agentes
```

### Cómo funciona

**1. `ejecutar_documentacion.sh`** — Ciclo de documentación:
1. Mide métricas del sistema (`df -h`, `uptime`)
2. Consulta el `central_router` (agentes activos, shared memory)
3. Registra los últimos 20 commits Git de las últimas 12 horas
4. Todo se guarda en `logs/documentacion_*.log`

**2. `generate_report.sh`** — Genera informe Markdown:
1. Consulta `http://127.0.0.1:5100/agents` (Registry)
2. Lista todos los agentes con IP, puerto y último latido
3. Guarda en `docs/informes/informe_*.md`

### Wiki interna
Expone el puerto **8087** para servir documentación generada con `mkdocs` o `pdoc`.

---

## 🧠 4. APRENDIZAJE (EL ENJAMBRE)

**Docker:** `ura-sandbox-aprendizaje` · 2 GB RAM · Red bridge

### Qué contiene

```bash
sandbox/Aprendizaje/
├── Dockerfile              # python:3.12-slim + pandas + numpy + sklearn
├── docker-compose.yml
├── scripts/
│   ├── ejecutar_aprendizaje.sh     # Entrypoint placeholder
│   └── run.sh                      # Entrypoint bajo demanda
└── Enjambre/
    ├── config.sh                   # Config compartida (OLLAMA_URL, MODEL, PROXY)
    ├── bibliotecario.sh            # ORQUESTADOR PRINCIPAL (233 líneas)
    ├── coordinador.sh              # Orquestador legacy
    ├── test_enjambre.sh            # Test funcional
    ├── maleta.json                 # Config central de búsquedas
    ├── tests/test_buzos.py         # Tests unitarios
    └── buzos/                      # 26 AGENTES DE INVESTIGACIÓN
```

### El Enjambre — cómo funciona

El **`bibliotecario.sh`** es el cerebro. Su ciclo de vida:

```
1. AUTO-UPDATE
   └── git pull + auto_update.sh

2. SENSOR DE RECURSOS
   └── Mide RAM libre → ajusta delay entre buzos

3. MEMORIA UNIVERSAL
   └── Índice JSON anti-bucle (7 días sin repetir)

4. PLANIFICACIÓN DINÁMICA
   └── Cada buzo tiene: prioridad, urgencia, frecuencia

5. LANZA BUZOS (orden, timeout 60s, retardo dinámico)
   ├── académico      → literatura científica (5 fuentes)
   ├── economía       → noticias sector hostelero
   ├── tendencias     → GitHub trending
   ├── tendencias_locales → gastronomía Navarra
   ├── prensa_diaria  → eventos gastronómicos
   ├── bares_españa   → 52 provincias
   ├── bares_copas    → Pamplona + competencia
   ├── competencia_pamplona → 10 restaurantes
   ├── practicas      → HackerNews + artículos técnicos
   ├── recetas        → TheMealDB
   ├── teoria_culinaria → OpenLibrary
   ├── modelos        → Ollama (locales + candidatos)
   ├── calidad        → 7 rodillos (ruff, pytest, bandit...)
   ├── red            → nmap + WiFi + latencia
   ├── mac            → salud del Mac Mini
   ├── flota          → Tailscale
   ├── tailscale_discovery → nuevos nodos
   ├── sistema        → disco + duplicados + temporales
   ├── camaras        → descubrir RTSP
   ├── vigilancia     → Frigate health
   ├── vigilancia_actualidad → novedades videovigilancia
   ├── carteles_menu  → descarga + análisis visión
   ├── fotos_cocina   → Foodish API
   ├── video          → YouTube/Dailymotion educativo
   ├── video_instagram → Reels + análisis estético
   └── descargas      → archiva URLs encontradas

6. LIMPIEZA (si disco >80%)

7. RECOPILA HALLAZGOS
   └── Agrupa por buzo, guarda en hallazgos_*.json

8. ANALIZA CON LLM
   └── Consulta qwen3:32b en GX10 → genera decisiones

9. AUTO-DESCARGA
   └── Videos de alto valor

10. GOBERNANZA + BACKUP + AUTO-DOC

11. REFLEXIÓN (cada 4 semanas)
    └── Evalúa impacto del ciclo
```

### Los buzos más importantes

| Buzo | Fuente | Qué busca |
|------|--------|-----------|
| `buzo_academico` | Semantic Scholar, arXiv, Dialnet | Papers de gastronomía, IA, contabilidad |
| `buzo_calidad` | Local (rodillos) | Ruff, pytest, Bandit, autoflake |
| `buzo_modelos` | Ollama + ollama.com | Modelos IA candidatos |
| `buzo_camaras` | nmap local | Cámaras RTSP nuevas |
| `buzo_red` | nmap + wavescope | Dispositivos red + rogue APs |
| `buzo_video_instagram` | YouTube/Instagram | Reels + frames + análisis visión |
| `buzo_flota` | Tailscale API | Dispositivos conectados |
| `buzo_tailscale_discovery` | Tailscale API | Nuevos nodos + auth keys |

### Configuración central

`maleta.json` contiene las definiciones de búsqueda: disciplinas académicas, restaurantes competidores, áreas de cocina, ciudades para Instagram, etc. Es el mapa que siguen los buzos.

---

## Cómo orquestarlo todo

```bash
# Los 4 San boxes juntos
docker compose -f docker-compose.sandbox.yml up -d seguridad mantenimiento documentacion aprendizaje

# Ejecutar el enjambre
docker exec ura-sandbox-aprendizaje bash /sandbox/Enjambre/bibliotecario.sh

# Ver resultados
docker logs ura-sandbox-aprendizaje --tail 50
```

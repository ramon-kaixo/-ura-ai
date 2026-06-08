# Estado de Infraestructura — URA (08 Junio 2026)

## Estado Global: OPERATIONAL ✅

## Nodos

### GX10 (Local ARM64) — 10.164.1.99
- **OpenCode** :8081 — activo (Ollama local + Model Router)
- **Ollama** :11434 — activo, VRAM limpia, 10 modelos
- **Visión** `llama3.2-vision:11b` — responde a texto e imágenes ✅
- **GUI-Bridge** :4097 — activo, sesión MCP persistente
- **Docker** — activo (ura-gui-agent, n8n, open-webui, prometheus)
- **GUI Agent** — Playwright + Chromium ARM64, `--network host`

### Hetzner (Cloud x86_64) — 178.105.81.83
- **Scraper** — `collector_base.py` con `smart_request` integrado
- **Pool** — llamadas directas via `proxy_selector.py`
- **RAM** — 1.4 Gi disponible (scraper parado)
- **SSH** — alias `hetzner`

### Cloudflare (Edge)
- **Worker** `ura-pool` — `https://ura-pool.barkaixo.workers.dev`
- **Plan**: Free (100k req/día)
- **Rutas**: `/proxy?url=target` y `/health`

## Enrutamiento
- **Config**: `config/target_rules.json` — 8 targets + fallback
- **Pool** (Hetzner → CF Worker): Pinterest, Bing, FontsInUse, Google, fallback
- **Stealth** (GX10 Bridge): Behance, YouTube, Dribbble, Noona/IAs

## Pipeline de Extracción
- `collector_base.Collector._download()` → intenta `smart_request()` primero
- Si stealth: GX10 Bridge → Playwright + Chromium → screenshot
- Si pool: Cloudflare Worker → CF IP → contenido HTML/imagen
- Dedup: SHA-256 + pHash (imágenes)
- Almacenamiento: `~/.nervioso/ura_search/cola/`

## Componentes Clave
| Archivo | Propósito |
|---------|-----------|
| `core/proxy_selector.py` | Cerebro de enrutamiento |
| `core/request_manager.py` | Wrapper async httpx con routing |
| `scripts/pro/gui_bridge.py` | HTTP Bridge para GUI Agent |
| `deploy/cloudflare_worker.js` | Worker Cloudflare |
| `config/target_rules.json` | Reglas de enrutamiento |

## Pendiente
- ~Gemini API Key~ No necesario — Ollama visión operativa
- yt-dlp cookies para YouTube
- Dashboard de monitoreo

## Git
- Rama: `dev/v3.1-expansion`
- Últimos commits: `a5e6c7e`, `f9154ae`
- Origin: no configurado en GX10 (push desde Mac)

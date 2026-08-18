# Monitoreo URA (F8) — Prometheus + Grafana + Alertmanager + node-exporter

Stack de observabilidad del GX10. Configuración versionada en el repo (esta carpeta).

## Componentes (docker compose, puertos SOLO en 127.0.0.1)

| Servicio | Puerto host | Contenido |
|----------|-------------|-----------|
| Prometheus | 9092 (host) → 9090 (cont) | Scrape de servicios URA + nodo |
| Alertmanager | 9093 | Reglas y notificación (webhook n8n preparado) |
| Grafana | 3000 | Dashboard "URA — Servicios" provisionado |
| node-exporter | 9100 | Métricas del nodo (CPU/RAM/disco) |

Nota: el puerto 9092 evita el conflicto con ura-api (9090).

## Targets scrapeados (verificados 2026-08-18)

- ura-api (9090/metrics ✓), ura-metrics (9091/metrics ✓), ura-contraste (8002/metrics ✓),
  ura-executor (4096/metrics ✓), ura-model-router (11435/metrics ✓), node-exporter (9100).
- ura-audit-api (5053) SIN /metrics (P5 — ver deploy/patches/audit-api-metrics.patch).
- ura-openclaw retirado (2026-08-08) — fuera de los targets.

## Arranque (requiere sudo — docker sin permisos para ramon)

```bash
cd /home/ramon/URA/ura_ia_1972/deploy/prometheus
sudo docker compose up -d
```

Verificación:
```bash
curl -s http://127.0.0.1:9092/-/healthy        # prometheus
curl -s http://127.0.0.1:3000/api/health        # grafana
curl -s http://127.0.0.1:9093/-/healthy        # alertmanager
curl -s http://127.0.0.1:9100/metrics | head -1 # node-exporter
```

Opcional (permite docker sin sudo al humano): `sudo usermod -aG docker ramon`
(requiere cerrar sesión; grupo docker = privilegios root, decisión del humano).

## Alertas activas (alert.rules)

- ServiceDown (up==0, 30s) — critical
- NodoPerifericoDesconectado (telemetría, 90s) — critical
- Latencia p95 > 5s, CPU > 90%, RAM > 90%, disco < 10% — warning/critical

Alertmanager notifica al webhook `http://host.docker.internal:5678/webhook/ura-alerts`
(n8n); sin webhook configurado las alertas quedan visibles en el UI de Alertmanager
y listas para conectar Telegram/Pushover vía core/notifier.py.

## Reversibilidad

`sudo docker compose down` elimina los contenedores (los volúmenes persisten).
Ningún servicio existente se toca: los puertos 9092/9093/3000/9100 eran libres
(9090/9091/5053/8002/11435 intactos).
# URA Service Level Agreement (SLA)

## Objetivos

| Métrica | Objetivo | Ventana | Medición |
|---------|----------|---------|----------|
| **Uptime servicios core** (openclaw, model-router, qdrant, ollama) | 99.5% | Mensual | Prometheus `up` metric |
| **Uptime servicios soporte** (ejecutor, audit-api, detector) | 99.0% | Mensual | Prometheus `up` metric |
| **Latencia model-router** (p95) | < 500ms | Diario | Prometheus histogram |
| **Latencia embedding** (p95) | < 2s | Diario | Logs estructurados |
| **Precisión búsqueda** (p@5) | > 0.7 | Semanal | search_quality.ndjson |
| **RTO** (Recovery Time Objective) | < 30 min | N/A | Timepo hasta restauración |
| **RPO** (Recovery Point Objective) | < 24h | N/A | Backup Qdrant |
| **Tiempo de respuesta** (alerta → notificación) | < 5 min | N/A | Health check timer |

## Presupuesto de Error

- **Mensual**: 3.6 horas de downtime permitido (99.5% de 30 días)
- **Trimestral**: 10.8 horas
- **Anual**: 43.2 horas

## Mantenimiento Programado

- Ventana semanal: Domingos 04:00-06:00 CET
- Notificación: 24h antes vía Telegram
- Excepción: parches de seguridad críticos sin ventana

## Responsabilidades

- **Uptime**: scripts/pro/health_check.sh cada 5 min
- **Alertas**: Telegram vía monitor/snc.py + Prometheus Alertmanager
- **Backup**: scripts/pro/backup_to_mac.sh diario 03:00
- **DR**: scripts/deploy/bootstrap_recovery.sh

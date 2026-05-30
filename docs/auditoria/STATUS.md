# Estado del Sistema URA
**Fecha:** 01/05/2026 03:30

---

## Servicios Principales

| Servicio | Puerto | Estado |
|----------|--------|--------|
| API URA v2 | 5000 | ✅ Funcionando |
| Ollama (IA local) | 11434 | ✅ Funcionando |
| n8n (automatización) | 5678 | ✅ Funcionando |
| Redis | 6379 | ✅ Funcionando |
| Prometheus | 9090 | ✅ Funcionando |
| Grafana | 3000 | ✅ Funcionando |

## Contenedores Docker

| Contenedor | Estado |
|-----------|--------|
| ura-api | ✅ Up 12 hours |
| ura-postgres | ✅ Up 12 hours |
| ura-grafana | ✅ Up 12 hours |
| ura-nginx | ✅ Up 12 hours |
| ura-jupyter | ✅ Up 12 hours (healthy) |
| ura-prometheus | ✅ Up 12 hours |
| n8n | ✅ Up 12 hours |

## Módulos Críticos

| Módulo | Estado |
|--------|--------|
| Agente Policía | ✅ OK |
| Memoria Semántica | ✅ OK |
| Motor ReAct | ✅ OK |
| Bóveda | ✅ OK |
| Guardián de Cambios | ✅ OK |
| Gestor de Puertos | ✅ OK |

## Bases de Datos

| Base de Datos | Estado |
|--------------|--------|
| board.db | ❌ No existe |
| Índice Bóveda | ✅ OK (28 KB) |

---

_Informe generado automáticamente al arrancar URA_
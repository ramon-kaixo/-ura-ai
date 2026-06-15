# Plan de Mejora Continua — URA Motor de Conocimiento

Generado: 2026-06-15 tras auditoría de 32 archivos / 1904 líneas.
45 problemas encontrados (10 alta, 27 media, 8 baja). 5 críticos corregidos.

## 🚨 Críticos (corregidos)

| # | Problema | Fix |
|---|----------|-----|
| 1 | `calibration.py:31` — `getattr` sobre dict → `detectar_anomalias` siempre vacío | `estado.recursos.get(metric, 0)` |
| 2 | `pattern_matcher.py:27` — typo `load_avg_1m` → alerta CPU nunca dispara | `load_1m` |
| 3 | `collector_hw_vm.py:18` — `dmesg --read-clear` borra ring buffer | `--since "1 hour ago"` (read-only) |
| 4 | `pattern_matcher.py:93-98` — `total_h` nunca se actualiza | Eliminado campo `media_h`/`total_h` |
| 5 | `qdrant_client.py:158-160` — singleton sin lock | `threading.Lock` |

## 🔴 Alta prioridad (pendientes)

| # | Archivo | Problema |
|---|---------|----------|
| 6 | `cli/main.py:181-186` | IP `178.105.81.83` + usuario `ramon_admin` hardcodeados en comando SSH |
| 7 | `cli/main.py:182-186` | Posible inyección de comandos si `host` no se sanitiza |
| 8 | `guard/verifier.py:40-46` | Triple `except: pass` anidado en `_test_ollama` |
| 9 | `scanner/__init__.py:100-106` | `_check_opencode` definida pero nunca llamada |
| 10 | `core/config.py:13` | `asus_host="100.72.103.12"` como default |

## 🟡 Media prioridad (27 items)

- Todos los `except: pass` sin log (~25 ocurrencias)
- `backup_knowledge.py` no hace backup real (nombre engañoso)
- `collector_asus.py:40` — `ssh root@{host}` hardcodea usuario
- `collector_hw_asus.py:17` — `/dev/nvme0n1` hardcodeado
- `pipeline/orchestrator.py:81-83` — fuga de FD (open sin context manager)
- `pipeline/orchestrator.py:104-109` — None-check faltante en `_emit()`

## ⚪ Baja prioridad (8 items)

- `docker ps -a` ejecutado 2 veces por escaneo (duplicado)
- Múltiples `open().read()` sin context manager
- `DEPENDENCIAS` hardcodeado en correlacion.py
- `ejecutar_preflight` viola SRP (hace 4 cosas)

## 📊 Métricas objetivo

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Tests pasando | 20/20 | 30/30 |
| Líneas totales | 1904 | <1800 (eliminar código muerto) |
| `except: pass` | ~25 | <5 |
| IPs hardcodeadas | 5+ | 0 |
| Bugs conocidos | 0 | 0 |

## 🔄 Ciclo de mejora

1. Cada sesión: revisar `except: pass` y sustituir por logs
2. Cada viernes: mover IPs hardcodeadas a config
3. Cada mes: auditoría completa

# Plan de Activación de Herramientas Dormidas — URA v0.34.0
## Fecha: 2026-08-01

## Ya activadas hoy (8 scripts testeados)
| Script | Tests | Uso |
|--------|-------|-----|
| orchestrator.py | 2 | Health check pre-push |
| check_secrets.py | 2 | Escaneo de secretos |
| utils.py | 3 | Utilidades comunes |
| lock_manager.py | 4 | Gestión de locks |
| reglas_loader.py | 4 | Carga de reglas |
| backup_assistant.py | 4 | Backup/restore |
| router_rate_limiter.py | 8 | Rate limiting |
| seed_correcciones_voz.py | 6 | Seed de correcciones |

## Próximas activaciones
| Script | Acción |
|--------|--------|
| change_log.py | ✅ Activado en post-commit hook (venv) |
| commit_msg_validator.py | ✅ Activado en commit-msg hook (venv) |
| inspectores.py | Merge conflict arreglado, pendiente tests |
| auto_reindex.py | Escribir tests primero (118 líneas críticas) |

## No activables (infraestructura)
| Script | Razón |
|--------|-------|
| captura_virtual.py | Necesita X11 |
| test_latencia_mac.py | Necesita hardware de voz |
| benchmark_*.py | Necesitan infra de benchmarks |
| chaos_test.py | Toca motor/core en producción |
| uitars_hetzner.py | Necesita VNC |

## Herramientas de calidad bloqueadas
| Herramienta | Bloqueo |
|-------------|---------|
| mypy | Bug interno TypeGuardedType |
| semgrep | Arreglado: instalar semgrep en venv, corregir patrones |
2026-08-01 22:30 — change_log activado en venv
2026-08-01 23:50 — commit_msg_validator activado en venv

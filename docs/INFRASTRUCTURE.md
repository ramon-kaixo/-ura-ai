# URA Infrastructure Index
# Actualizado: 2026-07-26

## Servicios Systemd
| Servicio | Puerto | Estado |
|----------|--------|--------|
| ura-mochila | 4098 | active |
| model-router | 11435 | active |
| ura-heartbeat | — | active |
| ura-watch-daemon | — | active |
| smbd | 139/445 | active |
| opencode | 8081 | active |
| ollama | 11434 | active |
| qdrant | 6333 | active |
| redis | 6379 | active |

## Auth
- ura-mochila: Bearer token (URA_SECRET_API_KEY)
- ejecutor_api: Bearer token (URA_SECRET_API_KEY)

## Recovery
- Conflicts: grep -rl '<<<<<<<' --include='*.py' .
- Daemon bucle: sudo rm -f /tmp/tuneladora_watch.lock
- Auth rollback: comentar middleware en mochila_server.py

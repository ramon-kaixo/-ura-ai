# Hallazgos de Fondo (Auditoría C2 - 2026-08)

1. **Gestión de Sesiones**: Mantener herramientas (como OpenCode/Tailscale/SSH) en bucle bloquea el flujo principal. Usar siempre `&` y `nohup` para subprocesos.
2. **Rutas Absolutas**: Los scripts automatizados pierden el contexto si asumen `~`. Usar `/home/ramon/URA/...` garantiza determinismo.
3. **Delegación Estricta**: No usar LLMs para tareas de bash pura (grep, sed). La terminal directa es más rápida y menos propensa a alucinaciones.
4. **Dependencias del Linter**: Reglas estrictas (como `S101` de flake8-bandit) en tests bloquean pipelines; se deben excluir para archivos de test.

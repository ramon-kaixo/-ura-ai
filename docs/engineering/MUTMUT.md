<!-- MUTMUT v1.0 — Engineering Process -->

# MUTMUT + HYPOTHESIS — Mutation testing y property-based testing en URA

**Versión**: 1.0 (2026-08-09) · **Tarea**: TASK-20260809-002
**Objetivo**: medir la calidad real de los tests (¿un fallo introducido hace fallar al menos un test?) y validar casos límite automáticamente, sin fricción en el desarrollo diario.

## Arquitectura (qué, cuándo, por qué)

| Capa | Mecanismo | Cuándo | Por qué |
|------|-----------|--------|---------|
| **Barrido global progresivo** | `ura-mutmut-daily.timer` (systemd, diario 06:00) → `scripts/pro/mutmut_daily.py` → `mutmut run` por lotes | Cada mañana, un lote distinto | mutmut completo tarda horas; se reparte en lotes diarios equilibrados (motor/core, core, knowledge+intelligence, assistant/obs/scanner, agents/brain/memory/...) |
| **Reportes** | `docs/udo/mutation-reports/YYYY-MM-DD_<lote>.md` (vía `mutmut results`) | Tras cada lote | Registro histórico del score por lote |
| **Revisión** | El script crea una **TASK UDO**; OpenCode Terminal la revisa cada mañana | Diario | Clasificar mutantes vivos (test débil / código muerto / falso positivo) sin automatizar la decisión |
| **Feedback local** | Hook pre-commit `pytest-delta` (`scripts/pro/pytest_delta.sh`) | Cada commit | Valida SOLO los tests relacionados con los archivos staged (<10s) |
| **Property-based** | hypothesis con perfiles `dev` (10 ejemplos) / `ci` (200 ejemplos) | dev: commits · ci: timer | `HYPOTHESIS_PROFILE` selecciona el perfil |

## Qué NO hacemos (y por qué)

- **NO mutmut en pre-commit**: ejecutaría la suite por mutante (15-20 min/commit) y muta archivos en disco — interrumpir un hook con Ctrl+C dejaría mutaciones sin revertir.
- **NO rm -rf .git/hooks**: destruiría commit-msg/post-commit/pre-push legítimos. El rollback es solo systemd.
- **NO reinstalar herramientas**: mutmut 3.7.0 e hypothesis 6.156.1 ya están en `.venv`.

## Configuración

- `[tool.mutmut]` en `pyproject.toml` → `source_paths = ["motor/core/", "motor/intelligence/", "core/", "knowledge/"]` (clave `source_paths` de mutmut 3.7; `paths_to_mutate` está deprecada).
- Perfiles hypothesis en `tests/conftest.py` → `register_profile("dev"/"ci")` + `load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))`.
- Timer: `deploy/timers/ura-mutmut-daily.{service,timer}` → `OnCalendar=*-*-* 06:00:00`.

## Comandos

```bash
# Barrido manual de un lote
HYPOTHESIS_PROFILE=ci .venv/bin/mutmut run core/

# Ver resultados acumulados
.venv/bin/mutmut results

# Reset del cache (empezar de cero)
rm -f .mutmut-cache

# Activar el timer diario (requiere sudo)
sudo cp deploy/timers/ura-mutmut-daily.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ura-mutmut-daily.timer

# Ejecutar el lote de hoy manualmente
.venv/bin/python scripts/pro/mutmut_daily.py
```

## Rollback (no destructivo — no toca git)

```bash
sudo systemctl disable --now ura-mutmut-daily.timer
sudo rm /etc/systemd/system/ura-mutmut-daily.service /etc/systemd/system/ura-mutmut-daily.timer
sudo systemctl daemon-reload
# Opcional: quitar el hook pytest-delta de .pre-commit-config.yaml
```

## Umbral y política

- El score por lote se **registra e informa** (no bloquea commits — la revisión es auditoría, no gate).
- Meta aspiracional: **≥80% mutantes muertos** al completar el primer ciclo completo.
- Los mutantes vivos se revisan por Terminal cada mañana: se clasifican (test débil / código muerto / falso positivo) y se registran en el expediente de la TASK del día.

## Notas

- Prerrequisito resuelto (F0): se retiraron los tests huérfanos de `scripts.pro.mcp_mochila` (módulo archivado en la purga `38b7921c`): `motor/tests/test_mcp_server.py` eliminado + 2 tests MCP de `test_e2e.py` retirados. La recolección de pytest quedó limpia (6378 tests).
- La recolección de mutmut exige `pytest --collect-only` = 0 errores; si un test rompe la recolección, el timer crea la TASK como **BLOCKED** con el exit code.

# URA — AI Agent Instructions

## Project Context
URA es un asistente de escritorio multi-agente con agentes especializados, coordinador de consciencia, sandbox de auto-mejora, y enjambre autónomo de buzos de investigación.
Repo: `/home/ramon/URA/ura_ia_1972` (rama `main`).
El código fuente principal está en ASUS (`gx10-64c3`). El Mac (`Mini-de-RAMON`) es para desarrollo ligero. Sincronización: `git push` / `git pull`. Nunca scp/rsync.

## Build & Test Commands
- Lint: `ruff check . && ruff format .`
- Tipos: `mypy --no-incremental core motor shared`
- Tests: `python3 -m pytest tests/ -q`
- Gates completos: `make validate`

## Architecture (high-level)
- `core/` — Dominio (agentes, debate, guardianes, inferencia)
- `motor/` — Motor framework (LLM, eventos, orquestación, memoria)
- `knowledge/` — Motor de conocimiento (F25/F26: fusion, memoria histórica)
- `scripts/pro/` — Pipeline operativo (~146 scripts)
- `docs/architecture/` — ADRs, closeouts, auditoría

## Security Rules
- No `shell=True` en subprocess
- No secretos hardcodeados (usar env vars o bóveda)
- Network allowlist para sandbox
- ADR-007: modificar `core/` requiere ADR + plan de rollback + revisión

## Code Style
- Ruff ALL rules enabled
- Type hints obligatorios
- Docstrings estilo Google
- Naming: kebab-case en archivos/dirs, ISO 8601 en fechas

## Verification Requirements
- Gates: ruff + mypy + pytest + secret-scan (via `scripts/pro/revision_gates.sh`)
- Cobertura: ≥80% por módulo nuevo (meta 100×100)
- Política de flaky tests: fugas de estado global se arreglan con snapshot/restore, no con timing

## Protocolo de respuesta
Al terminar CADA respuesta, después del bloque `<<<RESUMEN>>>`, emitir en su propia línea la etiqueta de instancia:
- `[1-Desktop-Mac]`, `[2-Web-Mac]`, `[3-Desktop-ASUS]`, `[4-Web-ASUS]`, `[0-Desconocido]`
Determinar con: `echo "CLIENT=$OPENCODE_CLIENT HOST=$(hostname)"`

Toda acción ejecutada debe reportarse con:
COMANDO: <exacto>
SALIDA: <literal, sin resumir>
INTERPRETACIÓN: <qué significa>

## Maletas disponibles (subagentes)

Los subagentes son **perfiles de permisos**. No tienen system prompt propio.
Cuando el agente principal los invoca, debe pasarles las instrucciones en el mensaje.
Disponibles en `.opencode/agents/`:

- **@revisor** — Auditoría solo-lectura. Veredicto: GO / GO CON CAMBIOS / NO-GO.
  Pásale: "Eres revisor. Auditas, no programas. Emites GO/GO CON CAMBIOS/NO-GO con evidencia literal."
- **@revisor-fondo** — Modo fondo automático. Solo lectura estricta. Detecta hallazgos, registra plan, no toca código.
  Pásale: "Modo fondo. Auditas sin modificar. Registras hallazgos con plan."
- **@tester** — Verifica tests reales (RED→GREEN) y cobertura ≥80% por módulo.
  Pásale: "Verificas tests. RED→GREEN. Cobertura ≥80% por módulo. Reportas PASS/FAIL."
- **@verificador** — Ejecuta gates (ruff, mypy, pytest, secret-scan) y reporta evidencia literal.
  Pásale: "Ejecutas gates. Reportas evidencia literal. No arreglas nada."
- **@calidad-cobertura** — Solo lectura. Mide cobertura por módulo del diff. Mínimo 80%, meta 100×100.
  Pásale: "Mides cobertura de los módulos del diff. ≥80% obligatorio. Reportas."
- **@orchestrator** — Detecta planes, crea tareas UDO, distribuye entre nodos.
  Pásale: "Analizas el mensaje. Si es plan, lo parseas y distribuyes. Si es orden local, la ejecutas."
- **@build** (principal) — Ejecuta build, tests e integración. Edita y ejecuta bash. Es el default.

## Key Files
- `AGENTS.md`, `README.md`, `pyproject.toml`
- `motor/core/config.py` — UraConfig (fuente de verdad)
- `scripts/pro/tuneladora_mantenimiento.py` — pipeline de mantenimiento
- `docs/architecture/ADR-007-REGLA_NUCLEO.md`

## Problemas conocidos
- Subagentes NO tienen system prompt propio (limitación de OpenCode 1.18.21+). Sus `.md` sirven solo para description/mode/model/permission.
- AGENTS.md se inyecta al agente principal en cada turno. Mantenerlo corto (<150 líneas).

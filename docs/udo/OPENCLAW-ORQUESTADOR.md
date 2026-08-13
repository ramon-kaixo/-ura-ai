# Rol: OpenClaw "UraOrquestador" — Supervisor, Planificador y Coordinador

**Estado**: ACTIVO (diseñado 2026-08-13, TASK-20260813-008) — ✅ configurado y probado (TASK-20260813-011, 2026-08-13)
**Versión binario**: OpenClaw 2026.6.10 (`/usr/bin/openclaw`)
**Perfil aislado**: `openclaw --profile orquestador` (estado/config en `~/.openclaw-orquestador/`)
**Home virtual (rootfs RO)**: `/home/ramon/URA/ura_ia_1972/.openclaw-orq-home/` — ver §9

---

## 1. Propósito

OpenClaw actúa como **supervisor y generador de planes** que trabaja con Ramón:
prepara planes y proyectos, los muestra a los agentes ejecutores (OpenCode WEB/TERM),
lee sus respuestas, hace resúmenes para la toma de decisiones y coordina las tareas.

**NO es un agente autónomo ni un ejecutor.** Es el "cerebro de planificación" humano-en-el-bucle.

## 2. Por qué perfil aislado (no toca el rol histórico)

OpenClaw ya existe en URA con un rol DIFERENTE: **brazo de emergencia del SNC**
(`monitor/openclaw.py` + `monitor/snc.py`, protocolo de hombre muerto, ejecuta
emergency_runbook.json). Ese rol queda **INTACTO y no se toca** (decisión D7 del
closeout 2026-08-08).

El rol de orquestador usa `--profile orquestador` para **aislar estado, config y
políticas** del rol SNC. Ambos roles pueden coexistir sin interferencia.

## 3. Permisos (qué puede y qué no puede hacer)

| Área | Permitido | Prohibido |
|---|---|---|
| **Lectura** | Todo el repo URA, docs/udo, logs, expedientes TASK | — |
| **Escritura** | SOLO `docs/udo/plans/` (workspace de planes: `PLAN-YYYYMMDD-SLUG.md`) | Escribir en TASK-* ajenas, hallazgos-fondo, review-pending, código |
| **Ejecución** | SOLO comandos read-only: `git log/status/diff/show/ls`, `grep`, `cat/head`, `ura-udo context/status/list`, `openclaw agent` (turnos propios) | `systemctl`, `rm/mv/touch` fuera del workspace, `git push/commit/rebase/reset`, `docker`, `sudo`, instalar paquetes, escribir en disco fuera del workspace |
| **Red** | Solo la API de su LLM (y canales de chat configurados por Ramón) | Exposición de servicios, descargas no aprobadas |
| **Secretos** | Leer referencias documentativas | Nunca copiar/almacenar valores de `/etc/ura/secrets.env` ni API keys en sus planes |

**Protección técnica** (la instrucción textual NO basta — lección v1.8):
- `approvals allowlist` por agente: denegar por defecto, permitir solo la allowlist read-only.
- `exec-policy` sincronizada con el host para los comandos prohibidos.
- Opcional (modo duro): `openclaw --container <sandbox>` con el repo montado RO.

## 4. Flujo de trabajo (ciclo orquestador)

```
1. RAMON + OpenClaw dialogan (chat local/gateway del perfil orquestador)
2. OpenClaw escribe el plan: docs/udo/plans/PLAN-YYYYMMDD-SLUG.md
3. RAMON revisa el plan y lo envía al WEB/TERM ("analízalo y ejecútalo")
4. El agente ejecutor crea TASK UDO (docs/udo/tasks/TASK-...) y ejecuta
5. Al terminar, RAMON/agente refiere el resultado a OpenClaw
6. OpenClaw LEE git + expedientes (read-only) y produce un resumen
   (docs/udo/plans/RESUMEN-YYYYMMDD-SLUG.md) para la decisión de RAMON
7. RAMON decide: aprobar, ajustar, o abrir TASK nueva
8. Coordinación de roles: WEB = ejecutor, TERM = revisor (modelo dual UDO)
   Rol futuro "OpenCode Tests/Docs" = sin infraestructura nueva, mismo opencode
```

**Límite anti-bucle**: máximo 1 plan activo por ronda; cada ciclo cierra/avanza
una TASK UDO. Si no hay respuesta de Ramón tras 1 turno, OpenClaw documenta el
estado y espera (reglas ANTI-BUCLE del AGENTS global).

## 5. Primer arranque (pasos de Ramón, ~5 min)

> ✅ **EJECUTADO (2026-08-13)**: la configuración técnica está hecha y probada
> (ver §9). Lo que queda es decisión humana: instalar el gateway como servicio
> user (opcional) y usar el perfil vía wrapper.

```bash
# 1. Inicializar el perfil (credenciales LLM/canales — interactivo, credenciales
#    NO van al repo) — OPCIONAL: con la config actual el agente ya funciona
#    (ollama local del GX10, sin credenciales externas)
openclaw-orquestador.sh configure

# 2. Aplicar política de ejecución restringida (denegar por defecto) — HECHO
openclaw-orquestador.sh exec-policy preset deny-all
openclaw-orquestador.sh approvals allowlist --agent main \
  --add "git log --oneline -20"
# ... (añadir los read-only de la tabla de permisos) — HECHO (22 patrones, §9)

# 3. Verificar aislamiento
openclaw-orquestador.sh doctor

# 4. Probar el agente (embedded, sin gateway)
openclaw-orquestador.sh agent --local --timeout 120 --agent main -m "Hola"
```

> Credenciales del LLM de OpenClaw: mismo patrón que `OPENCODE_WEB_PASS` —
> fuera del repo, gestionadas por Ramón (o `/etc/ura/secrets.env` con sudo si el
> perfil soporta env).

## 9. Estado de configuración (TASK-20260813-011, 2026-08-13)

| Ítem | Valor |
|---|---|
| Wrapper | `scripts/pro/openclaw-orquestador.sh` (exporta HOME virtual + `--profile orquestador`) |
| Home virtual | `/home/ramon/URA/ura_ia_1972/.openclaw-orq-home/` (partición rw; el rootfs del home ASUS es RO) |
| Gateway | puerto `18791`, bind `loopback` — **NO instalado como servicio** (decisión humana; usar embedded `--local` o `gateway install` explícito) |
| Modelo | `ollama/deepseek-r1:14b` (Ollama GX10 `http://localhost:11434`, api ollama, contextWindow 65536) |
| Contexto | `agents.defaults.contextTokens=60000` |
| Exec policy | `preset deny-all` aplicado (security=deny, ask=off, askFallback=deny) |
| Allowlist | 22 patrones read-only: `/usr/bin/git log|status|grep|show|diff|rev-parse|branch`, `/usr/bin/cat|grep|ls|head|tail|wc|python3`, `/bin/{cat,ls,grep,head,tail,wc}`, `/home/ramon/URA/**/ura-udo` (agente `*`) |
| Agente | `main` (default), workspace `~/.openclaw/workspace-orquestador` |
| Prueba | `agent --local -m "Responde solo: OK"` → respuesta `OK` (stopReason=stop) ✓ (2026-08-13) |
| Plugin inworld | falla al cargar (highlight.js exports) — cosmético, no bloquea |

**Pendiente**: (a) **DECIDIDO 2026-08-13 (Ramón, "OK")**: gateway del perfil NO se instala
como servicio — se usa modo embedded `--local` (el plan restringe "sin gateway systemd";
la TUI es opcional, requiere túnel SSH 18791 solo si Ramón la quiere);
(b) F5 validación del ciclo con un plan real (pendiente, veredicto humano);

## 6. Reglas de identidad y trazabilidad

- Los planes de OpenClaw son **propuestas**, no órdenes: requieren veredicto
  humano (Plan 0) antes de convertirse en TASK UDO.
- Si OpenClaw commitea sus planes (futuro opcional): identidad `[OCLW]` en el
  formato `docs(plans): [OCLW] PLAN-...`; hasta entonces los archivos del
  workspace los commitea el WEB bajo TASK aprobada.
- Toda afirmación de OpenClaw (que leyó X, que Y está en git) debe poder
  verificarse con comandos read-only (reglas ANTI-ALUCINACIÓN).

## 7. Excepciones intencionales (NO tocar, histórico 2026-08-08)

| Archivo | Razón |
|---|---|
| `monitor/openclaw.py`, `monitor/snc.py` | Brazo de emergencia SNC (rol distinto) |
| `core/model_router/cli.py` | Auth de arranque (ADR-007) |
| `data/openclaw_stats.json` | Estadísticas runtime |
| `tests/integration/test_openclaw.py` | Test muerto (zona protegida) |
| `scripts/pro/tuneladora/snapshot.py` | Zona protegida |

## 8. NO HACER

- No sustituir la autorización humana (Plan 0: veredicto GO/NO-GO lo decide Ramón).
- No re-crear el gateway systemd (`ura-openclaw.service` NO se restaura;
  la integración vieja (reviewer/firmador/netlock) sigue retirada).
- No tocar el SNC ni el runbook de emergencia.
- No crear infraestructura nueva (BD, servicios, API) para el rol: git + UDO + workspace bastan.
- No ejecutar nada fuera de la allowlist; ante la duda: documentar y esperar.

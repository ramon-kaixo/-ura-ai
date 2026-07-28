# Historial de Sesiones — URA
## Generado el 2026-07-28 18:03

| Fecha | Commits | Tests arreglados | Pendientes |
|-------|---------|------------------|------------|
| 2026-06-06 | 25 commits | chore: Hetzner 16GB configurado con Ollama + 20 workers
feat: Hetzner cloud scra | |
| 2026-06-08 | 67 commits | fix: lockfile 5min, flag --commit, memoria_fallos en comite IA
fix: auditoria v3 | |
| 2026-06-09 | 26 commits | fix: gitignore binarios chroma + analytics en core/modules/data/
restore: PLAN_M | |
| 2026-06-10 | 68 commits | ops: crawler_alemania + sync scripts para recoleccion tecnica
ci: pre-commit hoo | |
| 2026-06-11 | 4 commits | fix: restore post-commit file state (pre-commit stash reverted working tree)
cle | |
| 2026-06-12 | 21 commits | add backup_gx10_configs.sh — backup system configs to Mac
fix: clean AGENTS.md - | |
| 2026-06-15 | 71 commits | fix: scanner macOS (FileNotFoundError, ping flags) health 15→94
fix: httpx loggi | |
| 2026-06-16 | 30 commits | Hetzner SSH recovery: rescue script + deploy + sync resiliencia + estado DOWN
fi | |
| 2026-06-17 | 1 commits | RAG local: enabled=true + threshold=0.55 + index 14 docs (46 chunks) + bitacora  | |
| 2026-06-18 | 15 commits | Master Plan: modelos, baseline, metadata, limpieza
Ciclo 1: SO_REUSEPORT + exit  | |
| 2026-06-22 | 19 commits | Zero-error cleanup: 4,747 -> 626 en core/monitor, 0 syntax errors
Mejora continu | |
| 2026-07-04 | 14 commits | docs: FASE9_BASELINE — baseline de Fase 9 (commit f0c843a, tag v0.7.1-audit-fase | |
| 2026-07-05 | 24 commits | feat(F12-04): reranking — BaseReranker, NoOp, LLMReranker (Ollama)
feat(F12-03): | |
| 2026-07-06 | 29 commits | F14: Bloque 4 — Profiling (5 escenarios, 50min, 0 anomalías)
F14: Bloque 3 — End | |
| 2026-07-15 | 2 commits | F15 — Inferencia multiproveedor (cliente unificado)
F14: Bloque 5 — RC Audit (RC | |
| 2026-07-16 | 64 commits | docs(f22): publish multi-provider closeout
test(f22): add multi-provider benchma | |
| 2026-07-17 | 31 commits | F26-B1: Memoria Historica — Arquitectura
F25 baseline: metrics, benchmarks, budg | |
| 2026-07-18 | 37 commits | Auditoría OBS completa: 10 puntos verificados, 63 tests
Observabilidad Distribui | |
| 2026-07-19 | 26 commits | Informe F29: Asistente Conversacional (arquitectura, componentes, 119 tests)
F29 | |
| 2026-07-20 | 69 commits | Post-migración: fix bugs preexistentes + tag v2.0
Migración definitiva a Tunelad | |
| 2026-07-21 | 108 commits | ARQ Auditor: 33→0 FAIL — side effects documentados
Tendencias ARQ: /arq/trends e | |
| 2026-07-22 | 35 commits | docs: AGENTS.md update, ARQ trends, ura.py wrapper
fix(scripts): ARQ auditor, me | |
| 2026-07-23 | 69 commits | fix(hooks): mypy reactivado — motor/brain/ y tuneladora limpios
feat(tuneladora) | |
| 2026-07-24 | 9 commits | feat(auto_trigger): integra pipeline v7.0 + fix timeout-script mapping
feat(pipe | |
| 2026-07-25 | 35 commits | tuneladora: auto-fix gate — 1 file(s)
tuneladora: auto-fix gate — 1 file(s)
tune | |
| 2026-07-26 | 25 commits | docs: flujo Mac→Asus verificado — pipeline 6.5s, auth OK
docs: config map audit  | |
| 2026-07-27 | 12 commits | fix: test_audit_api — 3 tests reparados (very_long, surrogates, cid)
cleanup: ba | |
| 2026-07-28 | 8 commits | fix: ultimo merge conflict en model_router.py eliminado
fix: ura_maintenance.py  | |

## Detalle por sesión

### 2026-06-06

**Commits (25):**
```
a7c37c4 chore: Hetzner 16GB configurado con Ollama + 20 workers
39a92de feat: Hetzner cloud scraper online + 4-node architecture
a15acf8 feat: 4-machine architecture, OpenClaw + Model Router fixes
1883ec0 feat: Pamplona competition scraping + OpenClaw LLM analysis
2a342eb openclaw_api: FastAPI + MCP server
e95146f ura-search v5.0: nucleo operativo
a3f1ef0 threading: HTTPServer → ThreadingHTTPServer + web UI + ura-ask
a55deb0 n8n: setup script + workflows importados
af491b0 pipeline: servicios sy
```
**Archivos:**
```
.claude/settings.local.json
.config/opencode/opencode.json
.config/opencode/opencode.jsonc
.config/opencode/ura_context.json
.config/prompts/unified_prompts.json
.env.example
.eslintrc.json
.github/workflows/ci.yml
.github/workflows/ci_cd.yml
.github/workflows/codeql.yml
.github/workflows/dependency
```

### 2026-06-08

**Commits (67):**
```
ee618ae fix: lockfile 5min, flag --commit, memoria_fallos en comite IA
ac795f7 fix: auditoria v3.2 — RAM >=45GB ? 70B : 32B
ac780b4 feat: comite 10 IAs con consenso (locales + Groq via Tor)
1abd27c feat: auditoria dual Groq/Tor + Qwen local con anonymizer previo
a0b448d feat: orquestador Asus->Hetzner: sanitiza, rsync, audita con deepseek, trae reporte
ac5f6ec feat: auditoria pesada 32B — suspende procesos, carga modelo, genera reporte
eb92d8c fix: usar qwen2.5-coder:32b (disponible) en vez de q
```
**Archivos:**
```
.analisis.sh
.nervioso/estado_mantenimiento.json
AGENTS.md
MACHINES.md
agents/sandbox/agent_diseno.py
agents/sandbox/agent_hosteleria.py
agents/sandbox/agent_legal.py
agents/sandbox/agent_programacion.py
agents/sandbox/agent_runner.py
cli/__init__.py
cli/gatekeeper.py
config/maintenance.json
configs
```

### 2026-06-09

**Commits (26):**
```
395d062 fix: gitignore binarios chroma + analytics en core/modules/data/
415127b restore: PLAN_MAESTRO.md from commit 2cd99a8
740eb8f feat: hypothesis 23 tests + Xvfb capture + contexto sesion 2026-06-09
3b6ad8a fix: restaurar guardian_openclaw + configurar MCP con OpenClaw
2cd99a8 docs: plan maestro arquitectura + doble flujo + 4 preguntas para OpenClaw
ef95b35 feat: doble via — texto prioritario, crudo segundo plano + hash dedup + log rotatorio
bac5c47 chore: unit file para flujo constante (op
```
**Archivos:**
```
.gitignore
INFORME_CRITICIDAD_REAL.md
PLAN_MAESTRO.md
app/capturador.py
app/flujo_constante.py
app/gestor_archivos.py
app/motor_flujo.py
config/settings.json
core/change_guardian.py
core/guardian_openclaw.py
"core/guardi\303\241n_disco.py"
core/modules/data/chroma_db_code/c89337fc-aea1-4233-804d-dc3
```

### 2026-06-10

**Commits (68):**
```
f9fc0c4 ops: crawler_alemania + sync scripts para recoleccion tecnica
f5bcaf7 ci: pre-commit hooks (ruff --fix + mypy) en core/mochila+memoria
255dc62 Fase 3: Limpieza final Ruff Core — 39/39 ✅
18eff2a FASE 3: ruff --fix mochila+memoria (61 auto-fixes)
41bd1a5 FASE 2 fix: restaurar.sh limpio de cli/ legado
cd20971 FASE 2 fix: eliminar imports muertos a cli/gatekeeper
9306387 FASE 2: Borrado quirúrgico — 21 archivos MUERTO + tests huérfanos
c0cdf2e FASE 0: Baseline inicial — Plan Limpieza 10/10
2
```
**Archivos:**
```
.gitignore
.nervioso/estado_mantenimiento.json
app/capturador.py
app/flujo_constante.py
app/gestor_archivos.py
app/motor_flujo.py
cli/__init__.py
cli/gatekeeper.py
core/memoria/__init__.py
core/memoria/analizador.py
core/memoria/archivo.py
core/memoria/bridge.py
core/memoria/compresor.py
core/memori
```

### 2026-06-11

**Commits (4):**
```
2a7dec1 fix: restore post-commit file state (pre-commit stash reverted working tree)
8f192aa cleanup: purge legacy modules + add app/cli multi-agent scaffold
e74dbc0 Final: pipeline 95% Alemania, ASUS blindado
a0fadde fix: Hetzner nunca más caído sin saberlo
```
**Archivos:**
```
.nervioso/estado_mantenimiento.json
.pre-commit-config.yaml
app/capturador.py
app/flujo_constante.py
app/gestor_archivos.py
app/main.py
app/motor_flujo.py
cli/__init__.py
cli/gatekeeper.py
core/auth_layer.py
core/code_indexer.py
"core/guardi\303\241n_disco.py"
core/memoria/__init__.py
core/memoria/a
```

### 2026-06-12

**Commits (21):**
```
c0be863 add backup_gx10_configs.sh — backup system configs to Mac
88b7ae5 fix: clean AGENTS.md - no nested code blocks
5420483 prompt: replace with pure interaction + code rules, no infra
5f0c4a3 log: ACTUALIZAR_PROMPT mechanism
229c081 feat(audit): full prompt format + ACTUALIZAR_PROMPT mechanism
70f2e9d feat(core): tone & identity rules + audit format + logrotate gb10_panic
fb5869c log: fase 1 backup redundante a Mac
58c08e6 log: sync orphan scanner into tuneladora_mejora
a51b1da feat(plugin):
```
**Archivos:**
```
AGENTS.md
docs/pro/sesiones/2026-06-12.md
scripts/pro/backup_gx10_configs.sh
scripts/pro/backup_hetzner_to_asus.sh
scripts/pro/hetzner_watchdog.sh
scripts/pro/openclaw_netlock.sh
scripts/pro/systemd_orphan_scanner.py
scripts/pro/tuneladora_mantenimiento.py
scripts/restaurar.sh
```

### 2026-06-15

**Commits (71):**
```
5f5d6b5 fix: scanner macOS (FileNotFoundError, ping flags) health 15→94
98b8e6d fix: httpx logging silenciado (antes de imports)
cdd0d5f fix: restaurar conftest + test_mochila (62 pass, 9 skip)
003d635 fix: restaurar motor/ + auditd rules + json protegidos
db96892 fix: auditd rules (sin syscalls aarch64), +json protegidos
d4f887f fix: backups fuera de repo + test_mochila skip rastreadores
0350a84 feat: stubs extractores video/audio (compat legacy)
fedc42d feat: archivo stub para memoria (fix ing
```
**Archivos:**
```
.nervioso/estado_mantenimiento.json
.opencode/plans/motor_conocimiento.md
.pre-commit-config.yaml
AGENTS.md
INFORME_CRITICIDAD_REAL.md
agents/sandbox/agent_runner.py
app/flujo_constante.py
bitacora/.gitkeep
bitacora/_reporte_completo.json
bitacora/_template.md
bitacora/requisitos_mac.md
cli/gatekeep
```

### 2026-06-16

**Commits (30):**
```
072e97e Hetzner SSH recovery: rescue script + deploy + sync resiliencia + estado DOWN
e9da5e8 fix: SSH port 2222 for Hetzner + watchdog/sync_knowledge updated + estado_alemania.json
8be913b meta_miner_remote.py + ura-query.py --json/--sources + sync_knowledge hostname fix + bitacora sesion 16
a33083e MemoryEngine class + import_remote_metadata_package + sync_knowledge.sh + ura-query.py
ede2056 [doc] bitacora sesion 15: watchdog VRAM + schema + num_threads
d213dc3 [feat] Plan 3-4: watchdog VRAM n
```
**Archivos:**
```
.gitignore
AGENTS.md
bitacora/2026-06-16.md
core/debate/__init__.py
core/debate/committee_config.json
core/debate/debate_engine.py
core/debate/lockfile.py
core/debate/plan_validator.py
core/guardian_openclaw.py
core/infra/__init__.py
core/infra/heartbeat.py
core/infra/state_manager.py
core/logs/__in
```

### 2026-06-17

**Commits (1):**
```
7abb5b8 RAG local: enabled=true + threshold=0.55 + index 14 docs (46 chunks) + bitacora sesion 17
```
**Archivos:**
```
bitacora/2026-06-16.md
config/system_config.json
```

### 2026-06-18

**Commits (15):**
```
fc28eb4 Master Plan: modelos, baseline, metadata, limpieza
de1235e Ciclo 1: SO_REUSEPORT + exit code telemetry (v3.1)
27d9888 Chore: auto_dumps dir + gitignore
0a831c9 FASES 0-4: Recuperación determinista + watchdog + metadata v3
b8adea3 Cleanup: eliminar anti-patrones Tailscale restantes
a470453 Refactor: Tailscale hardening — systemd nativo + MagicDNS + UFW estático
2897b02 Fix: Tailscale race conditions y auto-reparación al arranque
93e8620 Chore: actualizar baseline timestamp + SECURITY_EXCE
```
**Archivos:**
```
.env.example
.gitignore
.pre-commit-config.yaml
AGENTS.md
CLAUDE.md
Makefile
SECURITY_EXCEPTIONS.md
agent_hierarchy.py
bitacora/2026-06-17.md
config/dispositivos.json
config/maintenance.json
config/schema.json
config/system_config.json
core/cleanup.py
core/config_manager.py
```

### 2026-06-22

**Commits (19):**
```
52d0ad2 Zero-error cleanup: 4,747 -> 626 en core/monitor, 0 syntax errors
2f34b3c Mejora continua pass 2: 1385 fixes auto en todo el proyecto. 6687 restantes son codigo legacy (annotaciones, docstrings) que requieren revision manual futura.
f60f200 Mejora continua: ruff format + ruff check --fix + mantenimiento
0729941 Proactive: pre-commit con semgrep+shellcheck, dependabot, safety CI, makefile
3b244de Pipeline blindado: semgrep custom + mypy strict + target py312
ffa3bf2 fix: 3 bugs + 2 margin
```
**Archivos:**
```
.coverage
.env.secrets.template
.github/dependabot.yml
.github/workflows/ci.yml
.gitignore
.nervioso/estado_mantenimiento.json
.pre-commit-config.yaml
.semgrep.yml
.venv/bin/Activate.ps1
.venv/bin/activate
.venv/bin/activate.csh
.venv/bin/activate.fish
.venv/bin/pip
.venv/bin/pip3
.venv/bin/pip3.12
```

### 2026-07-04

**Commits (14):**
```
f5a7dc8 docs: FASE9_BASELINE — baseline de Fase 9 (commit f0c843a, tag v0.7.1-audit-fase8)
f0c843a docs: AGENTS.md — Fase 9 aprobada, tabla única, Stream D corregida
1e14cf1 docs: FASE9_PROPOSAL v2.1 — orden definitivo + regla validación obligatoria
e45adc0 docs: FASE9_PROPOSAL v2 — revisión técnica de los 4 streams
33a5734 docs: cierre auditoría Fase 8 (v0.7.1) + propuesta Fase 9
09eaa76 audit: cierre post-Fase 8 — B1, B2, A4 + limpieza arquitectónica
9746b81 Fase A: logging en except silencios
```
**Archivos:**
```
.coverage
.gitignore
.nervioso/estado_mantenimiento.json
.opencode/plans/capa11-arquitectura.md
.opencode/plans/roadmap_post_fase4.md
.pre-commit-config.yaml
.venv/bin/Activate.ps1
.venv/bin/activate
.venv/bin/activate.csh
.venv/bin/activate.fish
.venv/bin/pip
.venv/bin/pip3
.venv/bin/pip3.12
.venv/
```

### 2026-07-05

**Commits (24):**
```
d669eac feat(F12-04): reranking — BaseReranker, NoOp, LLMReranker (Ollama)
fd3c19e feat(F12-03): retrieval híbrido — Vectorial + BM25 con benchmark
42cebcf feat(F12-02): baseline real KE 1.x — Qdrant + nomic-embed-text
5b59cbf feat(F12-01): corpus, benchmark KE 1.x, baseline, tests
d14120d docs(F12-00): contrato de calidad — ADR-012-01 + métricas + corpus
edbacad docs(F11-04): closeout oficial Fase 11
4d75d51 feat(F11-03): observabilidad técnica — Metrics, Health, Readiness, Instrumentation
e984
```
**Archivos:**
```
.gitignore
AGENTS.md
Makefile
agent_hierarchy.py
agents/agente_sandbox_codigo.py
app/main.py
benchmark_f10_results.json
cli/__init__.py
core/cleanup.py
core/debate/plan_validator.py
core/error_sandbox.py
core/guardian_openclaw.py
"core/guardi\303\241n_disco.py"
core/infra/heartbeat.py
core/ingestado
```

### 2026-07-06

**Commits (29):**
```
69b4437 F14: Bloque 4 — Profiling (5 escenarios, 50min, 0 anomalías)
831dd46 F14: Bloque 3 — End-to-End testing (8 casos, ≥70% componentes reales)
264f9bb feat(F14-01): Bloque 1 — Load & Stress Testing completado
47bf1cd plan(F14): gobernanza final + congelacion
b3ca59f plan(F14): refinar con metricas objetivas y criterios PASS/FAIL
cfe78b9 plan(F14): redefinir como validacion operativa para RC
585f2c4 release(F14-plan): closeout transversal F10-F13
f81a1fe release(F13-10): release audit + close
```
**Archivos:**
```
.dockerignore
.env.example
.github/workflows/ci.yml
.github/workflows/release.yml
.gitignore
AGENTS.md
Dockerfile
README.md
deploy/grafana/dashboard.json
deploy/prometheus/alerts.yml
docker-compose.yml
docs/ARCHITECTURE.md
docs/CLI_REFERENCE.md
docs/PLUGIN_DEV.md
docs/QUICKSTART.md
```

### 2026-07-15

**Commits (2):**
```
1afe2a1 F15 — Inferencia multiproveedor (cliente unificado)
7bace00 F14: Bloque 5 — RC Audit (RC Ready with Conditions)
```
**Archivos:**
```
AGENTS.md
config.local.json
core/config_manager.py
core/memory_engine.py
docs/architecture/FASE15_CLOSEOUT.md
docs/architecture/RC_READINESS.md
docs/architecture/benchmark_f15.json
motor/core/llm/__init__.py
motor/core/llm/ollama.py
motor/core/qdrant_client.py
scripts/pro/benchmark_llm.py
scripts/pr
```

### 2026-07-16

**Commits (64):**
```
5eb21f3 docs(f22): publish multi-provider closeout
c97ff21 test(f22): add multi-provider benchmark tests
cfb0d65 feat(f22): add multi-provider benchmark
693a386 feat(f22): add vLLM provider
4913dd1 feat(f22): add LM Studio provider
196c390 feat(f22): add OpenRouter provider
1997498 feat(f22): add Gemini provider
128f05b feat(f22): add Anthropic provider
cfd454e feat(f22): add provider capability negotiation
ca58e87 feat(f22): add provider extension contract
5748fda docs(f21): publish rag evaluat
```
**Archivos:**
```
AGENTS.md
agent_hierarchy.py
agents/sandbox/agent_diseno.py
agents/sandbox/agent_hosteleria.py
agents/sandbox/agent_legal.py
agents/sandbox/agent_programacion.py
agents/sandbox/agent_runner.py
app/capturador.py
app/gestor_archivos.py
app/main.py
app/motor_flujo.py
config.local.json
core/auth_layer.p
```

### 2026-07-17

**Commits (31):**
```
4a1221e F26-B1: Memoria Historica — Arquitectura
63275f9 F25 baseline: metrics, benchmarks, budgets, invariants, contracts frozen
653c568 F25-RR1: Release Readiness Review
4a2b552 F25-A3 final: ownership audit, bridge contract, obsolete filter
0bd9660 F25-A3: Integracion Vertical
f7ed77d F25-A1/A2: Integration + Global Architecture Audit
87f651a F25-B7 final: canonical serialization, checksum, stability, budgets
6c4782c F25-B7: Hardening de FactHistory
1e74305 F25-B6: FactHistory + FactVersion i
```
**Archivos:**
```
CHANGELOG_v1.0.0-rc.md
docs/architecture/ADR-025-02-KNOWLEDGE_IDENTITY.md
docs/architecture/ADR-025-03-FACT_VERSIONING.md
docs/architecture/ADR-025-04-HASH_IDENTITY_POLICY.md
docs/architecture/ADR-026-01-MEMORY_ARCHITECTURE.md
docs/architecture/API_AUDIT_v1_RC.md
docs/architecture/F25_A1_A2_AUDIT.md
```

### 2026-07-18

**Commits (37):**
```
1d08b4f Auditoría OBS completa: 10 puntos verificados, 63 tests
14c5701 Observabilidad Distribuida (OBS-01..10) para F28
3ebb8a3 Platform hardening: health, logging, governance, API classification, backpressure
04b11fb Industrial readiness audit: 70 checks, 4/70 pass
be4e981 Security: CapabilityGate wiring + journal/snapshot encryption
68c7ebd Security: rate limiting, sanitization, resource limits, audit logs
657c653 Add synthetic data generator for testing
11874a3 Add E2E demo script: Documento
```
**Archivos:**
```
docs/architecture/ADR-026-01-MEMORY_ARCHITECTURE.md
docs/architecture/ADR-027-01-AGENT_MODEL.md
docs/architecture/ADR-028-01-PROTOCOL_ARCHITECTURE.md
docs/architecture/ADR-028-03-VERSIONING.md
docs/architecture/ADR-028-04-SERIALIZATION.md
docs/architecture/ADR-028-05-OBSERVABILITY.md
docs/architectu
```

### 2026-07-19

**Commits (26):**
```
9d1109c Informe F29: Asistente Conversacional (arquitectura, componentes, 119 tests)
3bceba2 F29 B7-B9: Personalidad, Aprendizaje, Gestión de conversaciones
832ab83 F29 B5+B6: Planificador conversacional + orquestador herramientas
7394489 F29 B4: StyleEngine (3 modos conversacionales)
d9cf601 F29 B3: IntentEngine (clasificación + entidades + routing)
f4d4ea3 F29 B2: ContextManager (3 niveles + prioridad + expiración)
874c11a F29 B1: Motor conversacional (ConversationEngine)
9604189 Informe de tr
```
**Archivos:**
```
.env.example
.github/workflows/ci.yml
.github/workflows/publish.yml
.gitignore
AGENTS.md
CHANGELOG.md
QUICKSTART.md
README.md
agent_hierarchy.py
agents/agente_sandbox_codigo.py
app/capturador.py
app/gestor_archivos.py
app/main.py
app/motor_flujo.py
config/loader.py
```

### 2026-07-20

**Commits (69):**
```
a2a27ea Post-migración: fix bugs preexistentes + tag v2.0
e2b0575 Migración definitiva a Tuneladoras v2
594c92b Fase 5+6: Systemd + deploy + eliminación código antiguo
723bf38 Fase 4: Improvement con engine + pipeline_refactor
eca87ff Fase 3: Maintenance como plugins + engine
2d7ca49 Fase 1+2: Motor compartido + Pipeline Refactor
0020538 Auditoría arquitectura tuneladoras: rediseño completo necesario
df92d55 Fix tuneladora: 12 hallazgos corregidos
1006d03 Auditoría tuneladora: 12 hallazgos (1 bu
```
**Archivos:**
```
.github/workflows/ci.yml
.gitignore
.opencode/plans/ASSISTANT_IMPROVEMENTS.md
.opencode/plans/COMPLETE_CONVERSATIONAL_ROADMAP.md
.opencode/plans/ROADMAP_F29_F35.md
AGENTS.md
CLAUDE.md
README.md
agent_hierarchy.py
agents/agente_sandbox_codigo.py
config.local.json
core/auto_reindex.py
core/cleanup.py

```

### 2026-07-21

**Commits (108):**
```
b31da09 ARQ Auditor: 33→0 FAIL — side effects documentados
4ab959e Tendencias ARQ: /arq/trends endpoint + save automático
25b7e04 ARQ Auditor: baseline en docs/architecture/ + CI check
1f22d79 CI: ARQ Auditor job — verificación arquitectónica automática
9db3aa5 Fix: core/auto_reindex.py — UraConfig.load() lazy (34→33 FAIL)
8dbe95c ARQ Auditor: exceptions para scripts, 52→34 FAIL
5cd5bef ARQ Auditor: script unificado bloques A-K
a5f6b8b Instaladas 6 mejoras pendientes
1f8aa0a MCP: memory_research
```
**Archivos:**
```
.github/workflows/ci.yml
.gitignore
AGENTS.md
README.md
agent_hierarchy.py
app/capturador.py
app/main.py
app/motor_flujo.py
core/agents/__init__.py
core/agents/__main__.py
core/agents/cli.py
core/agents/conciencia.py
core/agents/constants.py
core/agents/ejecutor.py
core/agents/healing.py
```

### 2026-07-22

**Commits (35):**
```
ca1f1f8 docs: AGENTS.md update, ARQ trends, ura.py wrapper
a23ea19 fix(scripts): ARQ auditor, metrics server, MCP, tuneladora fixes
2013af8 test: e2e, fusion, LLM providers, observability, SDA tests
f2366f4 feat(cli): ura command enhancements, system status
c970f3c fix(obs): remove decorative health calls from instrumentation, keep real pipeline health
0dbe9a7 fix(tracing): platform tracing fixes, exporter/sampler refinements
be71d33 ci(infra): CI pipeline updates, Makefile targets, pyproject co
```
**Archivos:**
```
.github/workflows/ci.yml
.opencode/plans/AUDITORIA_ARQ_AUTOMATIZADA.md
AGENTS.md
Makefile
agent_hierarchy.py
core/auto_reindex.py
core/debate/debate_engine.py
core/secretario_cache.py
deploy/ura-health-monitor.service
docs/architecture/RECOVERY_ROOTFS_RO.md
docs/architecture/arq_baseline.json
docs/a
```

### 2026-07-23

**Commits (69):**
```
b561a7a fix(hooks): mypy reactivado — motor/brain/ y tuneladora limpios
c954185 feat(tuneladora): Fase 2 — métricas Prometheus, dry run, notificaciones, 15 tests
936d750 feat(a2+tuneladora): autofix seguro + blindaje completo
e40c59b fix(hooks): CI limpio — ruff, pytest, bandit, shellcheck, no-ghost, secrets, compile pasan
72956eb fix: pre-commit config — ruff exclude old dirs, python3 -m pytest, ghost files cleanup
34d14cc fix(mypy): type parameters in tuneladora — ledger, snapshot, engine
e950
```
**Archivos:**
```
.github/workflows/ci.yml
.opencode/plans/F3_PLAN_TELEMETRIA.md
.opencode/plans/V6.1_F1_CLOSEOUT.md
.opencode/plans/V6.1_F2_CLOSEOUT.md
.opencode/plans/V6.1_INTEGRATION_PLAN.md
.opencode/plans/debt/F3_mypy_errors.md
.opencode/plans/debt/F3_ruff_debt.md
.pre-commit-config.yaml
AGENTS.md.v0.30.0
Docker
```

### 2026-07-24

**Commits (9):**
```
c9fc0a6 feat(auto_trigger): integra pipeline v7.0 + fix timeout-script mapping
1fa93b0 feat(pipeline): v7.0 validación, auto-fix, rollback, LLM fallback, sandbox y telemetría
dfeef61 feat(tuneladora): v4.0 integración completa — 6 bloques conectados
b9a2437 feat(tuneladora): v4.0 — autonomía 24/7, notificaciones, dashboard, persistencia, circuit breaker, auto-healing
b98a145 feat(tuneladora): v3.0 — instalador + mantenimiento integrado + mypy limpio
dc56344 fix(bandit): 41 errores High arreglado
```
**Archivos:**
```
HOOKS_STATUS.md
deploy/ura-tuneladora.service
docs/API_BRAIN.md
docs/CHANGELOG.md
docs/GETTING_STARTED.md
docs/SOLID_AUDIT.md
docs/TROUBLESHOOTING.md
docs/TUNELADORA.md
motor/assistant/executor.py
motor/assistant/tool_plugin.py
motor/assistant/vector_memory.py
motor/brain/auto_maintain.py
motor/cli/
```

### 2026-07-25

**Commits (35):**
```
68c0220 tuneladora: auto-fix gate — 1 file(s)
fbe240d tuneladora: auto-fix gate — 1 file(s)
29bb386 tuneladora: auto-fix gate — 1 file(s)
e2d8b87 tuneladora: auto-fix gate — 1 file(s)
c8ae0e4 tuneladora: auto-fix gate — 1 file(s)
e9b19f0 feat: add mac_sync.sh - rsync+fswatch for Mac-ASUS real-time sync
f554a2a fix: add deploy/fix_rootfs.sh to remount rootfs RW + fix NoNewPrivileges
f379b27 feat: add mac_mount.sh helper for SSHFS
c01e684 tuneladora: auto-fix gate — 1 file(s)
e3b5705 tuneladora: a
```
**Archivos:**
```
.env.example
.env.secrets.template
.github/dependabot.yml
.github/workflows/ci.yml
.opencode/plans/motor_conocimiento.md
.semgrep.yml
INFORME_CRITICIDAD_REAL.md
PLAN_MAESTRO.md
SECURITY_EXCEPTIONS.md
agent_hierarchy.py
agents/agente_sandbox_codigo.py
agents/sandbox/Dockerfile
agents/sandbox/agent_di
```

### 2026-07-26

**Commits (25):**
```
49fba89 docs: flujo Mac→Asus verificado — pipeline 6.5s, auth OK
ef0d297 docs: config map audit — duplicacion URA_ROOT, RUTAS_CONFIG, CONFIG_PATH
48f6f97 fix: preflight integrado en tuneladoras + 31 tests
eb2cee9 tuneladora: auto-fix gate - 1 file(s)
6134107 docs: god modules audit
6a70ce5 fix: preflight filtro efimeros, heartbeat con auth, manifest completo, open-webui auth
6d0e66b tuneladora: auto-fix gate - 1 file(s)
2654669 tuneladora: auto-fix gate - 1 file(s)
f2e2eb7 fix: manifesto complet
```
**Archivos:**
```
.gitignore
agent_hierarchy.py
app/capturador.py
app/gestor_archivos.py
app/main.py
app/motor_flujo.py
core/auth_layer.py
core/auto_reindex.py
core/cleaner/cold_refactor.py
core/config_manager.py
core/debate/debate_engine.py
core/guardian_openclaw.py
core/guardians/ast_sentinel.py
core/infra/heartbea
```

### 2026-07-27

**Commits (12):**
```
1e90b7c fix: test_audit_api — 3 tests reparados (very_long, surrogates, cid)
b0b8f5b cleanup: barrido final — tests 90/0, ruff 37 cosmeticos, bandit 0 HIGH
a8a24ed fix: FASE 4 arquitectura — shared/paths.py, sys.exit, URA_ROOT centralizado
54ff2ec fix: FASE 1-3 del plan de recuperacion
1bdf52d fix: merge conflicts + strategy.py call_with_retry signature
f263a20 tuneladora: auto-fix gate - 1 file(s)
c11476c tuneladora: auto-fix gate - 1 file(s)
8330c6e docs: auditoria completa URA + recovery scri
```
**Archivos:**
```
core/agents/constants.py
core/auto_reindex.py
core/config_manager.py
core/document_quality.py
core/guardian_disco.py
core/guardians/ast_sentinel.py
core/mochila/routes/models.py
core/model_router.py
core/modules/data/chroma_db_code/chroma.sqlite3
core/modules/data/raw/data_2026-06-08.jsonl
core/reso
```

### 2026-07-28

**Commits (8):**
```
8dfc6e5 fix: ultimo merge conflict en model_router.py eliminado
12e06c6 fix: ura_maintenance.py restaurado de commit limpio (auto-fix lo revirtio)
66f92e4 fix: merge conflicts reintroducidos por auto-fix gate — resueltos desde commit limpio
581007e fix: 454 tests pass, 0 fail — todos los PluginBase + models + merge conflicts
ce260f6 tuneladora: auto-fix gate - 1 file(s)
e6c0ad5 tuneladora: auto-fix gate - 1 file(s)
db95e29 fix: 260 tests pass, 0 fail — plugins, auth, audit
e74c33a tuneladora: au
```
**Archivos:**
```
core/memory_engine.py
core/model_router.py
core/modules/data/raw/data_2026-06-08.jsonl
core/sandbox_orchestrator.py
core/search_engine.py
docs/audit_externa_20260728_1159.md
docs/audit_externa_20260728_1216.md
docs/audit_externa_20260728_1216_AUDITOR.md
docs/audit_externa_latest.md
motor/core/llm/ro
```


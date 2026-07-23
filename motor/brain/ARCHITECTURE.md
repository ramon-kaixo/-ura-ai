# Brain Architecture — URA AI v0.34.0-alpha.5

## Data Flow Diagram

```
                 ┌─────────────┐
                 │  Analyzer   │  ← AST analysis
                 │ (advisor.py)│
                 └──────┬──────┘
                        │ proposals
                        ↓
┌────────────┐   ┌─────────────┐   ┌──────────────────┐
│  Observer  │──→│    Alerts   │──→│  AutoMaintainer  │
│.py         │   │ .py         │   │ .py              │
│ reg. health│   │ correlacion │   │ propone fixes    │
│ checks     │   │ anomalías   │   │ espera aprobación│
└────────────┘   └─────────────┘   └────────┬─────────┘
       ↑                                    │ approved
       │                                    ↓
       │                            ┌──────────────────┐
       │                            │    Executor      │
       │                            │ .py             │
       │                            │ PipelineEngine  │
       │                            │ (tuneladora)    │
       │                            └────────┬─────────┘
       │                                     │ result
       │                                     ↓
       │                            ┌──────────────────┐
       └────────────────────────────│  Verification    │
                                    │ (en AutoMaintain)│
                                    └──────────────────┘

              ┌─────────────────┐
              │  WebAdapter    │ ← learn_from_web()
              │ .py            │
              │ crawl+search   │
              │ summarize      │
              └─────────────────┘
```

## Class Table

| Class | File | Responsibility | Inputs | Outputs |
|-------|------|---------------|--------|---------|
| `CodeAnalyzer` | `analyzer.py` | AST analysis of Python files | file path | dict with metrics (lines, functions, classes) |
| `ArchitectureAdvisor` | `advisor.py` | Generate refactor proposals | CodeAnalyzer results | list of proposals (type, target, priority) |
| `BrainObserver` | `observer.py` | Register & run health checks | health functions | `HealthObservation` list |
| `AlertEngine` | `alerts.py` | Correlate observations → alerts | BrainObserver results | `Alert` list (4 patterns) |
| `AutoMaintainer` | `auto_maintain.py` | Scan → propose → approve → execute → verify | Observer + Executor | MaintenanceProposal, execution records |
| `ProposalExecutor` | `executor.py` | Execute proposals via tuneladora | proposal dict | execution result (status, returncode) |
| `WebLearningAdapter` | `web_adapter.py` | Search + crawl + summarize web | query string | dict with sources, content, summary |

## Level 1 Maintenance Flow (A1) — Manual approval

```
Step 1: Observer.observe_all()
        └─ Registers: disk.health, ollama.health (+ manual)
        └─ Returns: [HealthObservation(status, latency, anomaly)]

Step 2: AlertEngine.evaluate()
        └─ Input: BrainObserver observations
        └─ 4 patterns
        └─ Returns: [Alert(severity, title, description)]

Step 3: AutoMaintainer.scan()
        └─ Input: AlertEngine alerts
        └─ _classify_risk() asigna risk_level (safe/medium/critical)
        └─ Returns: [MaintenanceProposal(action, target, risk_level, auto_execute)]

Step 4: AutoMaintainer.propose_and_maybe_execute() (A2)
        ├─ risk_level=safe + auto_execute=True → ejecuta automaticamente
        ├─ risk_level=medium → pasa a Step 4a (pregunta humano)
        └─ risk_level=critical → solo propone, no ejecuta

Step 4a: Human approves (Y/n) — solo para risk_level=medium
        └─ AutoMaintainer.approve_and_execute(proposal, approved=True)

Step 5: ProposalExecutor.execute()
        └─ Input: proposal dict
        └─ Converts to PipelineEngine.run_script(args)
        └─ Returns: {status, returncode, stdout, stderr}

Step 6: AutoMaintainer._verify_resolution()
        └─ Calls Observer.observe_all() again
        └─ Checks if affected subsystem is now ok
        └─ Returns: {resolved: True/False}
```

## A2 Risk Classification

| risk_level | auto_execute | Comportamiento | Ejemplos |
|------------|-------------|----------------|----------|
| safe | True | Ejecuta automaticamente, no pregunta | `auto_fix_ruff`, `auto_fix_unused_imports`, `check_network` |
| medium | False | Pregunta humano (Y/n) como A1 | `clean_disk`, `restart_provider`, `scale_resources` |
| critical | False | Solo propone, NO ejecuta | `emergency_shutdown` |

## Module Dependencies

```
advisor.py       → analyzer.py
alerts.py        → observer.py
auto_maintain.py → observer.py, alerts.py, executor.py
executor.py      → scripts.pro.tuneladora.engine.PipelineEngine
web_adapter.py   → motor.core.web (HttpCrawler, DuckDuckGo, Summarizer)
```

## What's Missing for Level 2 (A2)

| Feature | Status | Dependencies |
|---------|--------|-------------|
| Scheduled execution (cron-like) | ❌ Missing | `schedule` lib or systemd timer |
| Learning from past executions | ❌ Missing | Needs SQLite memory (was removed) |
| Feedback loop to Advisor | ❌ Missing | AutoMaintainer doesn't tell Advisor what worked |
| Multi-step workflows | ❌ Missing | Only single proposal execution |
| DegradedMode integration | ❌ Missing | Should set DegradedMode on critical alerts |
| Metrics export to Prometheus | ⚠️ Partial | exporter.py exists but not integrated with brain |
| Notification (Telegram/Pushover) | ❌ Missing | `motor.core.notifier` exists but not wired |

# URA — Universal Research Agent

Multi-agent desktop assistant with specialized agents, a consciousness coordinator,
a self-improving sandbox, and an autonomous swarm of research buzzers.

## System Requirements

- **Hardware**: NVIDIA GB10 (Grace Blackwell) with 128 GB unified memory recommended.
  Also runs on Linux x86_64 (VM or bare metal) with 16 GB+ RAM.
- **OS**: Ubuntu 22.04+ / Debian 12+
- **Dependencies**: Python 3.11+, Ollama, Tailscale (for multi-node), systemd

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/ramon-kaixo/-ura-ai.git
cd ura-ai

# 2. Create virtualenv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp scripts/deploy/fix-path.conf.example /etc/ura/fix-path.conf
# Edit /etc/ura/fix-path.conf with your paths

# 4. Run the tuneladora (maintenance + improvement pipeline)
bash tuneladora.sh

# 5. Or start individual services
python3 scripts/pro/ejecutor_api.py   # API REST (port 4096)
python3 core/model_router.py          # Model Router (port 11435)
```

## Architecture

```
ura_ia_1972/
├── core/           Domain logic (consciousness, event bus, memory, security, providers)
├── agents/         Specialized agents (organized by domain)
├── knowledge/      Long-term memory, Knowledge Engine (Fases 0-7)
├── motor/          CLI, pipeline, scanner, diagnostics (active pipeline)
├── scripts/        Shell scripts, deployment, pro pipeline
├── monitor/        System monitoring and heartbeats
├── docs/           Architecture docs, ADRs, design documents
├── deploy/         systemd service units
├── tests/          Pytest and legacy test runners
└── config/         Machine-specific device inventory and profiles
```

## Main Commands

| Command | Purpose |
|---------|---------|
| `bash tuneladora.sh` | Unified maintenance + improvement pipeline |
| `python3 -m motor.cli.main status` | System status and health check |
| `python3 core/model_router.py` | Enhanced Model Router with caching |
| `python3 scripts/pro/ejecutor_api.py` | URA Executor REST API |

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0–6 | ✅ Closed | FTS5, edges, background queue, autorecovery, reconcile |
| 7 | ✅ Closed (v0.6.0-fase7) | Production optimizations |
| 8 | ✅ Closed (v0.7.0-fase8) | Hardening, coverage, documentation |

See `AGENTS.md` for detailed architecture, service inventory, and AI agent instructions.
See `docs/architecture/` for design documents and ADRs.

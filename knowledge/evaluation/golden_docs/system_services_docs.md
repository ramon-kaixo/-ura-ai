# URA System Services

URA runs multiple systemd services on the GX10 NVIDIA GB10 hardware.

## Core Services

- `ollama` (port 11434): LLM inference server, systemd base, 2 parallel requests, keep-alive 1m
- `ura-openclaw` (port 18789): Gateway MCP, hardening with CPUQuota=40%, MemoryMax=2G
- `opencode` (port 8081): OpenCode server for AI-assisted development
- `ura-executor` (port 4096): URA Executor API (renamed from opencode-executor)
- `model-router` (port 11435): URA Model Router Enhanced, cache 5min, Connection: close

## User Services

- `model-router`: Enhanced routing with caching
- `backend@codestral-22b`: llama.cpp backend for codestral-22b
- `backend@qwen2.5-coder-32b`: llama.cpp backend for qwen2.5-coder-32b

## Monitoring Services

- `ura-audit-api`: FastAPI for audit logging
- `ura-contraste` (port 8002): Proxy de Contraste + Telemetria POS
- `ura-detector`: YOLOv8 Detector + ByteTrack + Behavior Analysis

All services are managed by systemd with automatic restart policies.

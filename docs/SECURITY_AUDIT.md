# Security Audit URA v0.30.0-alpha.8

## Date: 2026-07-23

## Findings

### HARD-01: Hardcoded path /home/ramon/URA/ura_ia_1972
- Location: 18 files in scripts/pro/
- Risk: Medium — deployment-specific path prevents portability
- Mitigation: Most use `URA_ROOT` env var with fallback to hardcoded path
- Action: Documented. Fix requires config centralization (post-F3).

### HARD-02: Hardcoded IP 100.72.103.12 (Tailscale)
- Location: motor/core/config.py:15
- Risk: Low — overridable via env vars, only used for ASUS-specific features
- Mitigation: `HOST_ASUS` env var takes precedence over default
- Action: Acceptable as default config.

### HARD-03: Hardcoded port 4198
- Location: motor/core/config.py:16
- Risk: Low — overridable via `PUERTO_ASUS` env var
- Action: Acceptable as default config.

### SEC-01: API keys
- Location: motor/core/llm/{gemini,anthropic,openrouter,openai}.py
- Risk: None — keys retrieved via `get_secret()` from environment/secrets backend
- Mitigation: No hardcoded keys found in source code
- Action: Pass.

## Verdict
No critical security issues. No exposed secrets.
18 hardcoded paths documented for future config centralization.

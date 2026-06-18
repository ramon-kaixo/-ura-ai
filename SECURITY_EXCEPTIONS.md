# Security Exceptions

## OpenCode — `allowInsecureAuth`

| Field | Value |
|-------|-------|
| **Service** | `opencode` on port 8081 |
| **Risk** | No password, no TLS. Any device on `10.164.1.0/24` can access local LLM models |
| **Rationale** | HTTP access from Mac (`10.164.1.26`) in a controlled local network. No public exposure |
| **Validity** | Until Tailscale SSH, TLS proxy, or password auth is configured |
| **References** | `AGENTS.md:216`, `opencode.service`, `SECURITY_EXCEPTIONS.md:this` |

### Mitigation (applied 2026-06-18)
- `ufw` installed: only Mac IP `10.164.1.26` can reach ports 22 and 8081
- Default incoming policy: DENY
- Documented exception tracked in this file

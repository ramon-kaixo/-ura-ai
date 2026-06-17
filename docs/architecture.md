# URA Architecture Diagram
*Auto-generated: 2026-06-18T01:46:41+02:00*

```mermaid
graph TB

  subgraph GX10[NVIDIA GX10 Grace Blackwell]

    subgraph SYSTEMD[systemd Services]
      llama_vision[🟢 llama-vision]
      model_router[🟢 model-router]
      ollama[🟢 ollama]
      opencode[🟢 opencode]
      qdrant[🟢 qdrant]
      ura_agent_hierarchy[🟢 ura-agent-hierarchy]
      ura_api[🔴 ura-api]
      ura_audit_api[🟢 ura-audit-api]
      ura_auditd_watchdog[🔴 ura-auditd-watchdog]
      ura_cleanup[🔴 ura-cleanup]
      ura_contraste[🟢 ura-contraste]
      ura_detector[🟢 ura-detector]
      ura_ejecutor[🟢 ura-ejecutor]
      ura_go2rtc[🟢 ura-go2rtc]
      ura_heartbeat[🟢 ura-heartbeat]
      ura_hetzner_tunnel[🔴 ura-hetzner-tunnel]
      ura_maintenance[🔴 ura-maintenance]
      ura_memory_watchdog[🔴 ura-memory-watchdog]
      ura_mkdocs[🟢 ura-mkdocs]
      ura_mochila[🟢 ura-mochila]
      ura_mochila_guard[🔴 ura-mochila-guard]
      ura_model_preliminar[🔴 ura-model-preliminar]
      ura_pipeline[🔴 ura-pipeline]
      ura_ssh_guard[🟢 ura-ssh-guard]
      ura_watchdog[🔴 ura-watchdog]
      ura_xvfb[🟢 ura-xvfb]
    end

    subgraph DOCKER[Docker Containers]
      docker_ura_gui_agent[🟢 ura-gui-agent]
      docker_ura_mejora_continua[🟢 ura-mejora-continua]
      docker_ura_qdrant[🟢 ura-qdrant]
    end

    subgraph GIT[Git Repository]
      branch_dev_v3.1_expansion[🌿 dev/v3.1-expansion]
      branch_main[🌿 main]
      branch_master[🌿 master]
    end

      llama_vision
      model_router :11435
      ollama :11434
      opencode :8081
      qdrant :6333
      ura_agent_hierarchy
      ura_api
      ura_audit_api
      ura_auditd_watchdog
      ura_cleanup
      ura_contraste
      ura_detector :9092
      ura_ejecutor :4096
      ura_go2rtc
      ura_heartbeat
      ura_hetzner_tunnel
      ura_maintenance
      ura_memory_watchdog
      ura_mkdocs
      ura_mochila_guard
      ura_mochila
      ura_model_preliminar
      ura_pipeline
      ura_ssh_guard
      ura_watchdog
      ura_xvfb

  end
```

## System Status

| Service | Status | Port |
|---------|--------|------|
| ✅ llama-vision | active | ? |
| ✅ model-router | active | 11435 |
| ✅ ollama | active | 11434 |
| ✅ opencode | active | 8081 |
| ✅ qdrant | active | 6333 |
| ✅ ura-agent-hierarchy | active | - |
| ❌ ura-api | activating | ? |
| ✅ ura-audit-api | active | ? |
| ❌ ura-auditd-watchdog | inactive | ? |
| ❌ ura-cleanup | inactive | ? |
| ✅ ura-contraste | active | 8001 |
| ✅ ura-detector | active | 9092 |
| ✅ ura-ejecutor | active | 4096 |
| ✅ ura-go2rtc | active | 8554 |
| ✅ ura-heartbeat | active | ? |
| ❌ ura-hetzner-tunnel | activating | ? |
| ❌ ura-maintenance | inactive | ? |
| ❌ ura-memory-watchdog | inactive | ? |
| ✅ ura-mkdocs | active | ? |
| ✅ ura-mochila | active | ? |
| ❌ ura-mochila-guard | inactive | ? |
| ❌ ura-model-preliminar | inactive | ? |
| ❌ ura-pipeline | inactive | ? |
| ✅ ura-ssh-guard | active | ? |
| ❌ ura-watchdog | inactive | ? |
| ✅ ura-xvfb | active | ? |

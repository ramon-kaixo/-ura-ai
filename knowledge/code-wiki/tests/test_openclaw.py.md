# `tests/test_openclaw.py`

- **Language:** python
- **Chunks:** 4

## Symbols

### class: `TestOpenClawDeterminism`
- Line: 29

class TestOpenClawDeterminism:
Tests de comportamiento determinista de OpenClaw.
Methods: setUp, tearDown, test_runbook_loads_correctly, test_state_file_reading, test_emergency_detection, test_forbidden_commands_blocked, test_execute_runbook_blocks_forbidden, test_execute_runbook_runs_safe_commands, test_process_emergency_ignores_healthy_services, test_process_emergency_alerts_unknown_services, test_dead_man_timeout_constant, test_stats_file_writing

### class: `TestOpenClawIntegration`
- Line: 194

class TestOpenClawIntegration:
Tests de integración: simular caída de red + verificación runbook.
Methods: setUp, tearDown, test_simulated_network_failure_opens_runbook, test_openclaw_does_not_act_without_emergency

## Module Overview

Tests de integración — OpenClaw + SNC
Simula caídas de red y verifica que OpenClaw lee el estado EMERGENCY
y abre el emergency_runbook.json correctamente.

## Imports

```
json
monitor.openclaw.DEAD_MAN_TIMEOUT
monitor.openclaw.execute_runbook_action
monitor.openclaw.is_emergency
monitor.openclaw.is_forbidden
monitor.openclaw.load_runbook
monitor.openclaw.load_state
monitor.openclaw.process_emergency
monitor.openclaw.save_stats
monitor.openclaw.stats
pathlib.Path
sys
unittest
unittest.mock.patch
```

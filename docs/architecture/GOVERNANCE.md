# URA Platform Governance

## Module Ownership

| Module | Owner | Responsibility | API Classification |
|--------|-------|---------------|-------------------|
| `motor.core.fusion` | Fusion | Knowledge identity, FactHistory, FactIndex | 📄 38 symbols |
| `motor.core.fusion.stages` | Fusion | Pipeline stages (8) | 📄 21 symbols |
| `motor.memory` | Memory | Historical timeline, journal, snapshot | 📄 9 symbols |
| `motor.agents` | Agents | CapabilityGate, ToolRunner, Scheduler, Planner, Agent | 📄 42 symbols |
| `motor.agents.models` | Agents | AgentTask, AgentPlan, AgentResult, etc. | 📄 13 classes |
| `motor.platform` | Platform | ProtocolEnvelope, Transport, Validator | 📄 30 symbols |
| `motor.platform.serializer` | Platform | JSON serialization | 📄 2 ABCs |
| `motor.platform.validator` | Platform | Protocol validation + sanitization | 📄 1 class |

## Release Process

### Versioning
```
MAJOR.MINOR.PATCH
MAJOR: breaking API change
MINOR: new feature, backward compatible
PATCH: bug fix, no API change
```

### Release Checklist
```
[ ] All tests pass (pytest -q)
[ ] No new ruff errors (ruff check motor/)
[ ] No new bandit issues (bandit -r motor/)
[ ] ADRs updated if architecture changed
[ ] __all__ updated if API changed
[ ] API classification updated
[ ] CHANGELOG updated
[ ] Tag created (vMAJOR.MINOR.PATCH)
[ ] Branch merged to main
```

### Change Approval
```
PATCH: peer review + CI green
MINOR: peer review + CI green + ADR if applicable
MAJOR: team review + ADR required + migration plan
```

### Hotfix Process
```
1. Branch from last stable tag
2. Fix + test
3. Merge to main
4. Tag PATCH bump
5. Deploy
```

## Deprecation Policy

```
1. Mark deprecated in docstring + __all__ comment
2. Keep for 2 MINOR releases
3. Emit DeprecationWarning on use
4. Remove on next MAJOR
```

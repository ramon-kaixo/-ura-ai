# ADR-028-03: Protocol Versioning

**Status:** Draft  
**Phase:** F28-B1

---

## Semver

`protocol_version = "MAJOR.MINOR"` (PATCH no se usa en protocolo, solo documentación).

| Cambio | MAJOR | MINOR | Ejemplo |
|--------|-------|-------|---------|
| Campo requerido añadido/eliminado | ✅ | ❌ | 1.0 → 2.0 |
| Tipo de campo cambiado | ✅ | ❌ | 1.0 → 2.0 |
| Semántica de entrega cambiada | ✅ | ❌ | 1.0 → 2.0 |
| Campo opcional añadido | ❌ | ✅ | 1.0 → 1.1 |
| Nuevo message_type | ❌ | ✅ | 1.0 → 1.1 |
| Error corregido | ❌ | ❌ | 1.0 → 1.0 (patch doc) |

## Version Negotiation

```
1. Emisor envía mensaje con protocol_version = "1.5" + capabilities = ["v2.semantics"]
2. Receptor responde con protocol_version = "1.3" (su máxima versión soportada)
3. Emisor ajusta: usa protocol_version = "1.3", capabilities = intersection(...)
4. Si MAJOR mismatch: rechazar conexión con error incompatible_version
```

## ABC Versioning

```python
class Planner(ABC):
    @property
    def protocol_version(self) -> str:
        return "1.0"

    @abstractmethod
    def plan(self, task: AgentTask, context: AgentContext | None = None) -> AgentPlan:
        ...

    def plan_batch(self, tasks: list[AgentTask]) -> list[AgentPlan]:
        """Nuevo método opcional. Default: llama a plan() por cada tarea."""
        return [self.plan(t) for t in tasks]
```

**Regla:** Todo método nuevo en un ABC debe tener implementación por defecto. No abstract.

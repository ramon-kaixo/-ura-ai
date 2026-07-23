# AutoMaintainer Level 2 (A2) — Plan de Mejora

Basado en A1 existente: 149 líneas, 3 niveles de riesgo (low/medium/high),
flujo: Observer → AlertEngine → AutoMaintainer → ProposalExecutor → Verification.

---

## 1. Casos SEGUROS para autofix (sin aprobación humana)

| Caso | Código ruff | Riesgo | Acción automática |
|------|-----------|--------|-------------------|
| **Import no usado** | F401 | Bajo | `ruff check --fix select=F401` |
| **Import no ordenado** | I001 | Bajo | `ruff check --fix select=I001` |
| **Formato** | Formateo | Bajo | `ruff format` |
| **Variable no usada** | F841 | Bajo | `ruff check --fix select=F841` |
| **Espacios en blanco** | W291, W293 | Bajo | `ruff format` |
| **Typo simple** | — | Bajo | AST match con diccionario de typos comunes |
| **F821 (name not defined)** | F821 | Medio | Solo si el módulo existe en algún import cercano |

## 2. Casos NO seguros (requieren aprobación humana)

| Caso | Código | Riesgo | Razón |
|------|--------|--------|-------|
| **PLR0915** (función larga) | Refactor | Alto | Cambia estructura del código |
| **Refactor >10 líneas** | — | Alto | Puede romper lógica |
| **Cambio de API pública** | — | Crítico | Afecta a consumidores externos |
| **Eliminación de código** | — | Crítico | Posible pérdida de funcionalidad |
| **Cambio de dependencias** | — | Crítico | Puede romper CI |
| **Disco lleno <5GB** | — | Crítico | No autofixear — alertar humano |
| **Provider caído** | — | Medio | Requiere diagnóstico humano |

## 3. Implementación Propuesta

### 3.1 Añadir `risk_level` y `auto_execute` a MaintenanceProposal

```python
@dataclass
class MaintenanceProposal:
    alert: Alert
    action: str
    target: str
    params: dict[str, Any]
    estimated_risk: str  # safe, medium, critical
    auto_execute: bool = False  # A2: si True, no pregunta
```

### 3.2 Reglas de auto-ejecución

```python
def _should_auto_execute(self, proposal: MaintenanceProposal) -> bool:
    """Determina si una propuesta puede ejecutarse sin aprobación."""
    if proposal.estimated_risk == "safe":
        return True
    if proposal.estimated_risk == "medium":
        return False  # pregunta
    if proposal.estimated_risk == "critical":
        return False  # solo propone, no ejecuta
    return False

def propose_and_maybe_execute(self) -> list[dict[str, Any]]:
    """A2: propone y ejecuta automáticamente lo seguro."""
    results = []
    for proposal in self.scan():
        if self._should_auto_execute(proposal):
            result = self.approve_and_execute(proposal, approved=True)
            log.info("A2 auto-executed: %s — %s", proposal.action, result.get("status"))
            results.append(result)
        else:
            log.info("A2 needs approval: %s (risk=%s)", proposal.action, proposal.estimated_risk)
            self._pending.append(proposal)
    return results
```

### 3.3 Clasificador de riesgo automático

```python
class RiskClassifier:
    """Clasifica propuestas por riesgo basado en tipo de código."""
    
    SAFE_PATTERNS = {"F401", "I001", "W291", "W293", "F841"}
    MEDIUM_PATTERNS = {"F821", "PTH1[012]", "SIM1[05]"}
    CRITICAL_PATTERNS = {"PLR0915", "PLC0414", "B027"}
    
    @classmethod
    def classify(cls, error_code: str) -> str:
        if error_code in cls.SAFE_PATTERNS:
            return "safe"
        for pattern in cls.MEDIUM_PATTERNS:
            import re
            if re.match(pattern, error_code):
                return "medium"
        if error_code in cls.CRITICAL_PATTERNS:
            return "critical"
        return "medium"  # default conservador
```

### 3.4 Integración con ruff para autofix

```python
def _auto_fix_ruff(self, target_file: str, error_codes: list[str]) -> dict[str, Any]:
    """Ejecuta ruff --fix solo para errores seguros."""
    safe_codes = {"F401", "I001", "F841"}
    codes_to_fix = [c for c in error_codes if c in safe_codes]
    if not codes_to_fix:
        return {"status": "skipped", "reason": "no safe errors"}
    
    select = ",".join(codes_to_fix)
    result = self._executor.execute({
        "type": "ruff_fix",
        "target": target_file,
        "params": {"select": select},
    })
    return result
```

## 4. Hooks de pre-commit para autofix

| Hook | Comando | Riesgo | Incluir en A2 |
|------|---------|--------|---------------|
| ruff --fix | `ruff check --fix` | Bajo | ✅ Sí |
| ruff --fix solo F401/I001/F841 | `ruff check --fix --select F401,I001,F841` | Bajo | ✅ Sí |
| ruff format | `ruff format` | Bajo | ✅ Sí |
| py_compile | `python3 -m py_compile` | Ninguno | ❌ No (es verificación) |

## 5. Tiempo estimado de implementación

| Componente | Tiempo | Dependencias |
|-----------|--------|-------------|
| Añadir `auto_execute` a `MaintenanceProposal` | 30 min | Ninguna |
| Implementar `_should_auto_execute()` | 30 min | Riesgo clasificado |
| Implementar `RiskClassifier` | 1 hora | Códigos ruff |
| Implementar `_auto_fix_ruff()` | 1 hora | Executor existente |
| `propose_and_maybe_execute()` | 1 hora | Todo lo anterior |
| Tests para A2 | 3 horas | Mocks de ruff |
| **Total A2** | **~7 horas** | — |

## 6. Lo que NO cambia de A1

- `BrainObserver`, `AlertEngine`, `ProposalExecutor` → sin cambios
- `scan()` añade flag auto_execute pero mantiene firma
- `approve_and_execute()` se mantiene para casos manuales
- Logging y verificación se mantienen

## 7. Criterio de éxito para A2

```
1. ruff check motor/brain/*.py --fix ejecuta autofix sin preguntar
2. 0 regresiones en tests existentes
3. AutoMaintainer.propose_and_maybe_execute() retorna resultados
4. Los casos "safe" se ejecutan en <5 segundos (no esperan input)
```

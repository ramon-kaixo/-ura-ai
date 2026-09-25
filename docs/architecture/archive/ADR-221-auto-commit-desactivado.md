# ADR-221 — Auto-commit desactivado en la tuneladora

**Estado:** ACEPTADO
**Fecha:** 2026-08-05
**Contexto:** El pipeline de la tuneladora (`PipelineRunner.phase_commit`) tenía
~40 líneas de código de auto-commit que nunca se ejecutaban (código muerto
detrás de un `return Status.SKIP`). La decisión de desactivarlo fue deliberada,
pero no estaba documentada como ADR.

## Decisión

**El auto-commit permanece DESACTIVADO por defecto.** Razones:

1. **Seguridad**: evitar que el pipeline commitee código no verificado por un humano
2. **Control**: Ramón revisa los cambios antes del commit (regla de aprobación humana)
3. **Calidad**: los hooks pre-commit validan antes de commitear; el pipeline reporta pero no modifica el repo

## Reactivación (opcional, explícita)

La lógica de auto-commit se conserva en `_phase_commit_impl()` y se puede
reactivar temporalmente:

```bash
export URA_TUNELADORA_AUTO_COMMIT=1
```

Sin la variable, `phase_commit` devuelve `Status.SKIP` siempre.

## Consecuencias

- `phase_commit` → `SKIP` por defecto (comportamiento observable intacto)
- `_phase_commit_impl()` contiene el código original (git add -u + git commit --no-verify)
- La reactivación requiere también `mode=gate` y `cfg.auto_commit=True` (doble guarda)
- Este ADR cierra el Gap #1 del Plan Maestro de la Tuneladora

## Gaps relacionados

- Gap #2 (hook post-commit opcional): resuelto con `URA_TUNELADORA_POST_COMMIT`
- Gap #3 (notificación de FAIL): resuelto con `notifier.py`
- Gap #4 (quality_gate conectado): resuelto con import directo en `_finish`
- Gap #5 (coverage en reporte): resuelto con `coverage` en `_build_json_report`
- Gap #6 (código muerto): resuelto con este refactor (la lógica muerta es ahora `_phase_commit_impl`)

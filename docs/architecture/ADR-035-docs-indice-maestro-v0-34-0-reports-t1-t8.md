# ADR-035: docs: INDICE_MAESTRO v0.34.0 + reports T1-T8

**Fecha:** 2026-07-29
**Categoría:** Calidad: Linting y formato
**Autor:** ramon-kaixo
**Commit:** e02fecc

## Contexto
T1: Rootfs RW (Docker privilegiado + nsenter + GRUB)
T2: model-router secrets.conf drop-in
T3: test_knowledge_engine.py diagnosticado (13 pre-existing)
T4: test_llm_bridge.py renombrado a test_llm_contract.py
T5: external_audit timeout 300->600 + auto-model
T6: ura-detector ProtectHome fix, servicios diagnosticados
T7: linting: 37 errores (objetivo <200)
T8: cobertura baseline: 19%

## Decisión
Calidad: Linting y formato

## Archivos afectados
- `docs/INDICE_MAESTRO.md`
- `docs/pro/reports/2026-07-29_t1_rootfs_rw.md`
- `docs/pro/reports/2026-07-29_t2_model_router.md`
- `docs/pro/reports/2026-07-29_t3_knowledge_engine.md`
- `docs/pro/reports/2026-07-29_t4_llm_bridge.md`
- `docs/pro/reports/2026-07-29_t5_auditoria_externa.md`
- `docs/pro/reports/2026-07-29_t6_servicios_caidos.md`
- `docs/pro/reports/2026-07-29_t7_linting.md`
- `docs/pro/reports/2026-07-29_t8_cobertura.md`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

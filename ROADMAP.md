# ROADMAP — URA

Estado del roadmap de fases. Fuente de verdad: AGENTS.md (tabla de fases y
detalle por fase). Este archivo resume el plan a futuro.

## Fases cerradas (resumen)

| Fase | Título | Estado | Tag |
|------|--------|--------|-----|
| 0-6 | Fundamentos (FTS5, edges, cola, autorecuperación, reconcile) | ✅ | — |
| 7 | Optimizaciones de Producción | ✅ | v0.6.0-fase7 |
| 8 | Hardening, Cobertura y Documentación | ✅ | — |
| 15 | Migración HTTP (Ollama) | ✅ | v0.15.0-fase15 |
| 16 | Empaquetado y Deuda | ✅ | v0.16.0-fase16 |
| 17 | Configuración Unificada | ✅ | v0.17.0-fase17 |
| 17.5 | Gestión de Secretos | ✅ | v0.17.5-f17.5 |
| 25 | Knowledge Fusion | ✅ | v0.25.0-fase25 |
| 26 | Historical Memory | ✅ | v0.26.0-rc1 |
| 27 | Autonomous Agents | ✅ | v0.27.0-fase27 |
| 28.1 | Stabilization | ✅ | v0.28.3-stable |
| 29 | Production Readiness | ✅ | v0.29.0-fase29 |
| F1-F4 | Estabilización post-29 + cobertura | ✅ | v0.30.0-f2 |

## Plan de Consolidación 2026-08 (10 fases)

Ejecutado por el agente TERM en ASUS. Ver ADR-037 y ADR-038.

| Fase | Contenido | Estado |
|------|-----------|--------|
| 0 | Tag hito + corrección registros de auditoría | ✅ |
| 1 | Seguridad subprocess (validación de rutas) | ✅ |
| 2 | Barrido cobertura: 4 módulos más al 100% real | ✅ |
| 3 | Refactor entity_resolver.py (764→312 líneas) | ✅ (ADR-037) |
| 4 | Split de 4 tests largos (>900 líneas) | ✅ (ADR-038) |
| 5 | CI/CD: gate cobertura 85% + publish con no-regresión + Dockerfile multi-stage | ✅ |
| 6 | pip-audit: 0 vulnerabilidades | ✅ |
| 7 | ADRs faltantes + README Mermaid | ✅ |
| 8 | Rendimiento web (ya implementado) + limpiar mutants/ (275M) | ✅ |
| 9 | ROADMAP/CONTRIBUTING/DRP + documentar backups | ✅ |

## Próximos pasos sugeridos (sin asignar)

1. **Meta 100x100**: subir módulos <80% hacia 100 (fusion/models 79%, bloqueados
   LLM de Fase 2: strategy.py, citation.py, html_extractor.py, summarizer.py,
   diff_detector.py, collectors).
2. **Gate cobertura 90%**: siguiente escalón del verificador (MIN_DEFAULT).
3. **Revisión diferida** del lote de consolidación (Fases 0-4, 6 commits) por
   revisor independiente.
4. **Cerebro/segundo humano**: visión a largo plazo del proyecto (motor/brain +
   plugins), pendiente de diseño.
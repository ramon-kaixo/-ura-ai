# F29 B3 — Metodología de Validación Funcional

## Procedimiento

1. **Selección de documentos**: 20 documentos públicos por dominio
2. **Pipeline**: F24 (Web Fetch) → F25 (Fusion) → F26 (Memory) → F27 (Agent)
3. **Extracción de facts**: cada documento se procesa por FusionPipeline.run()
4. **Revisión manual**: 10% de los facts generados se revisan manualmente para precisión
5. **Métricas**: Precisión, cobertura, coherencia temporal, utilidad contextual

## Estados

- ✅ **Completado**: pipeline ejecutado, facts generados, revisión manual hecha
- ⏳ **Pendiente**: requiere F24/F25 operativo en GX10 con modelos cargados
- 📋 **Diseñado**: metodología lista, no ejecutado por dependencias externas

## Nota

B3 requiere la pila F24→F25→F26→F27 operativa con modelos LLM.
En el entorno actual (contenedor opencode) no es posible ejecutar el pipeline completo.
Los informes documentan el diseño metodológico.

# Sistema de Arquitectura y Calidad — URA

**Versión:** 1.0
**Fecha:** 2026-07-21
**Baseline:** `v4.3.2`

## Propósito
Definir los estándares, procesos y verificaciones automáticas que garantizan que el código nuevo y existente mantenga la coherencia arquitectónica, la calidad y la evolución sostenible del proyecto.

---

## ARQ-100 — Reutilización

### Objetivo
Evitar duplicación de código y de responsabilidades.

### Reglas
1. **Antes de crear cualquier módulo nuevo**, ejecutar el Reuse Detector para verificar que no existe funcionalidad similar.
2. **Si existe código similar**, evaluar si:
   - Se puede extender el módulo existente (responsabilidad compatible)
   - Se necesita un módulo nuevo (responsabilidad diferente)
3. **Pregunta obligatoria**: ¿La funcionalidad pertenece realmente a un módulo existente o estoy creando un nuevo concepto?
4. **No solo código duplicado**: también detectar responsabilidades duplicadas (ej. dos módulos que hacen logging, dos clases que gestionan config).

### Verificación automática
- `scripts/pro/reuse/reuse_detector.py` en fase pre-commit
- Revisión de responsabilidades en code review

### Referencias
- `scripts/pro/reuse_detector_plugin.py` — plugin para pipeline de mejora
- `scripts/pro/reuse/` — índice AST de funciones (14.349 funciones indexadas)

---

## ARQ-200 — Integridad Arquitectónica

### Objetivo
Garantizar que el código respeta la arquitectura definida: core/interfaces/ como frontera, direcciones de dependencia respetadas.

### Reglas
1. **Violaciones de capas**: `core/` no debe importar de `motor/` (salvo excepciones documentadas).
2. **Dependencias prohibidas**: `scripts/` no debe importar de `core/` (salvo fachada `motor/cli/public_api.py`).
3. **Imports desde módulos deprecated**: verificar que ningún código nuevo use módulos marcados como deprecados.
4. **Dirección de dependencias**: `motor/` → `core/interfaces/` → implementaciones concretas.

### Verificación automática
```bash
# Violaciones de capas core→motor
grep -rn "^from motor\|^import motor" core/ --include="*.py" | grep -v "test_" | grep -v "__init__"
# Imports deprecados
grep -rn "model_router_main\|core\.config " --include="*.py" .
```

### Excepciones documentadas actuales (v4.3)
| Archivo | Import | Razón |
|---------|--------|-------|
| `core/infra/heartbeat.py` | `motor.observability.logging` | Logging setup (infraestructura) |
| `core/json_logger.py` | `motor.observability.logging` | JSONFormatter (wrapper, deprecado) |
| `core/auto_reindex.py` | `motor.core.config` | Constante module-level |
| `core/model_router/cli.py` | `motor.core.secrets` | Preflight security check |
| `core/memoria/qdrant_store.py` | `motor.core.qdrant_client` | Construcción de cliente concreto |

---

## ARQ-300 — Calidad

### Objetivo
Mantener estándares de calidad diferenciados por tipo de módulo.

### Umbrales por zona

| Zona | Ruff | Mypy | Complejidad máx | Notas |
|------|------|------|-----------------|-------|
| **Core** (`core/`) | 0 errores | 0 errores | CC ≤ 10 | Dominicanio del negocio |
| **Motor** (`motor/`) | 0 errores | 0 errores | CC ≤ 15 | Infraestructura |
| **Knowledge** (`knowledge/`) | 0 errores | 0 errores | CC ≤ 15 | Conocimiento |
| **Scripts prod** (`scripts/pro/`) | 0 errores | Tolerante | CC ≤ 25 | Herramientas internas |
| **Benchmarks** | Tolerante | Tolerante | CC ≤ 30 | Medición, no producción |

### Aclaraciones
- **Benchmarks**: pueden admitir complejidad mayor (son herramientas de medición, no producción).
- **Core**: umbrales más estrictos (es el dominio del negocio).
- **Scripts/pro/**: se permite mayor flexibilidad pero sin errores de Ruff.

---

## ARQ-400 — Refactorización

### Objetivo
Disparar refactorización cuando el sistema realmente lo necesita, no por contadores arbitrarios.

### Disparadores (basados en indicadores reales)

| Indicador | Umbral | Acción |
|-----------|--------|--------|
| **Complejidad ciclomática** > 15 | Media | Revisar |
| **Complejidad ciclomática** > 25 | Alta | Refactorizar |
| **Duplicación** > 15% del módulo | Media | Evaluar extracción |
| **Tamaño de módulo** > 800 líneas | Media | Evaluar división |
| **Crecimiento de deuda** (Health Index -5% en 1 mes) | Alta | Refactorizar |
| **Caída del Health Index** por debajo de 70 | Crítica | Refactorizar urgente |

### No usar como disparadores
- ❌ Cada 25 commits (no mide complejidad real)
- ❌ Cada 15 archivos (no mide complejidad real)

### Módulos grandes
No hay regla obligatoria de >500 líneas. Un módulo de 700 líneas bien estructurado es mejor que uno de 200 líneas mal organizado. **Métrica real**: medir responsabilidades + complejidad + cohesión.

---

## ARQ-500 — Consolidación

### Objetivo
Gestionar el ciclo de vida completo de los componentes con estados intermedios.

### Estados
```
EXPERIMENTAL
    ↓
ACTIVO
    ↓
DEPRECADO
    ↓
OBSOLETO
```

| Estado | Significado | Acción requerida |
|--------|-------------|------------------|
| **Experimental** | En desarrollo activo, API puede cambiar | Ninguna |
| **Activo** | Estable, en producción | Mantenimiento normal |
| **Deprecado** | Sigue existiendo, tiene fecha de retirada | Migrar consumidores |
| **Obsoleto** | Eliminado o pendiente de eliminar | No usar |

### Por qué "Deprecado" es necesario
No todo pasa directamente de "Activo" a "Obsoleto". Un componente puede seguir siendo necesario mientras se migran sus consumidores (ej. `core/json_logger.py`: deprecado en v3.7.6, pendiente de eliminar en v4.0).

### Componentes actuales por estado (v4.3)
| Componente | Estado | Desde |
|------------|--------|-------|
| `motor/intelligence/memory/hybrid.py` | Experimental | v4.3.0 |
| `core/interfaces/` | Activo | v3.6.0 |
| `motor/core/llm/__init__.py` (sin __getattr__) | Activo | v4.0.0 |
| `core/json_logger.py` | Deprecado | v3.7.6 |
| `knowledge/engine/logging_config.py` | Deprecado | v3.7.6 |
| `core/mochila/circuit_breaker.py` | Activo | — |

---

## ARQ-600 — Validación Funcional

### Objetivo
Detectar funcionalidades que nunca se conectan, plugins nunca invocados, migraciones incompletas.

### Es el bloque más valioso
Las herramientas automáticas (ruff, mypy) encuentran errores de código, pero no detectan:
- **Funcionalidades nunca conectadas**: un módulo perfectamente escrito que ningún otro importa.
- **Plugins nunca invocados**: registrados en el registry pero nunca llamados.
- **Migraciones incompletas**: un refactor que dejó código antiguo sin eliminar.
- **Código muerto por cambio de requisitos**: funcionalidad que ya no tiene sentido pero nadie borró.

### Verificación automática
```bash
# Módulos sin imports externos (potencialmente muertos)
find . -name "*.py" -not -path "*/__pycache__/*" -not -path "*/.venv/*" \
  -exec sh -c 'grep -rl "def \|class " "$1" | head -1' _ {} \; 2>/dev/null

# Plugins registrados pero no invocados
grep -rn "register.*Plugin\|\.register(" --include="*.py" . | grep -v test | grep -v __pycache__
```

### Casos reales detectados por este sistema
| Hallazgo | Detectado por | Acción |
|----------|--------------|--------|
| `core/mochila/providers/` (7 archivos, 0 imports) | ARQ-600 | Eliminado en v3.7.2 |
| `build/` (artefactos stale) | ARQ-600 | Eliminado en v3.7.2 |
| `pattern_matcher.py` parámetro `circuit_breaker` nunca usado | ARQ-600 | Eliminado en v3.7.2 |

---

## ARQ-700 — Observabilidad

### Objetivo
Cada componente debe tener definidos: logs, métricas, trazas y diagnóstico.

### Requisitos por componente

| Componente | Logs | Métricas | Trazas | Diagnóstico |
|------------|------|----------|--------|-------------|
| **API** (mochila) | ✅ request/response | ✅ latencia, errores | ✅ trace_id | ✅ /health |
| **Agentes** | ✅ ejecución | ✅ contadores | ✅ span | ✅ status |
| **HybridMemory** | ✅ operaciones CRUD | Pendiente | Pendiente | ✅ health() |
| **MCP Server** | ✅ llamadas | ✅ tools llamados | Pendiente | Pendiente |
| **Heartbeat** | ✅ ciclos | Pendiente | Pendiente | ✅ HealthRegistry |
| **Tuneladora** | ✅ fase completa | Pendiente | Pendiente | Pendiente |
| **Metrics Server** | ✅ inicio | ✅ p50/p95 | Pendiente | ✅ /health + /ready |

### Implementación
- Usar `motor/observability/` (HealthRegistry, MetricsRegistry, tracing, logging JSON)
- Cada módulo nuevo debe registrar su componente en HealthRegistry
- Cada módulo nuevo debe emitir métricas en operaciones clave

---

## ARQ-800 — Rendimiento Continuo

### Objetivo
No solo benchmarks puntuales: monitoreo continuo de rendimiento con línea base y alertas.

### Línea base actual (v4.3)

| Métrica | Valor | Alerta si |
|---------|-------|-----------|
| Import time `motor.core.llm` | **0.1ms** | >5ms |
| Import time `core.mochila._state` | **116ms** | >200ms |
| Import time total (cold) | **~350ms** | >500ms |
| Tests pasando | **27/27** (core) | Cualquier fallo nuevo |
| Ruff en core/motor/knowledge | **0 errores** | >0 |
| Ruff en scripts/pro/ | **18 errores** | (excepciones documentadas) |
| Mypy en motor/observability | **0 errores** | >0 |

### Benchmarks disponibles
- `scripts/pro/benchmark_llm.py` — latencia de generación LLM
- `scripts/pro/benchmark_rag.py` — pipeline RAG completo
- `scripts/pro/benchmark_hybrid.py` — retrieval híbrido
- `scripts/pro/benchmark_qdrant.py` — Qdrant vector search
- `scripts/pro/benchmark_ke.py` — Knowledge Engine
- `scripts/pro/benchmark_final_retrieval.py` — retrieval final

---

## ARQ-900 — Seguridad Continua

### Objetivo
Separar seguridad de calidad como disciplina propia con verificaciones específicas.

### Áreas de verificación

| Área | Herramienta | Frecuencia |
|------|-------------|------------|
| Secretos en código | `scripts/pro/check_secrets.py` | Cada commit |
| Validación de entradas | Revisión manual + bandit | Cada PR |
| SSRF (Server-Side Request Forgery) | Bandit S310, S311 | Cada commit |
| Path traversal | Bandit S108, PTH | Cada commit |
| Dependencias vulnerables | `pip audit` o `safety` | Semanal |
| Permisos de archivos | EXE001/EXE002 (ruff) | Cada commit |
| Llamadas a procesos externos | Bandit S603, S605, S607 | Cada commit |
| SQL injection | Bandit S608 | Cada commit |

### Gestión de secretos
- Usar `motor/core/secrets.py` (`get_secret`, `require_secret`, `has_secret`)
- Prohibido hardcodear tokens (verificado por `scripts/pro/audit_secrets.py`)
- Backends: env vars, `/etc/ura/secrets.env`, preparado para Secret Manager futuro

---

## ARQ-1000 — Evolución Arquitectónica

### Objetivo
Evitar que la arquitectura se quede obsoleta aunque el código esté limpio.

### Revisión periódica (cada 3 meses)
1. ¿Las decisiones ADR siguen siendo válidas?
2. ¿Alguna abstracción ya no aporta valor?
3. ¿Existen capas que pueden eliminarse?
4. ¿El proyecto puede simplificarse?

### No es una limpieza
Es una **revisión estratégica**. No se trata de encontrar código muerto (eso ya lo hace ARQ-600), sino de cuestionar las decisiones arquitectónicas actuales.

### Preguntas guía
- ¿Sigue siendo necesaria esta interfaz o podemos eliminarla?
- ¿Este patrón sigue siendo el adecuado o la tecnología ha cambiado?
- ¿Podemos reducir el número de capas?
- ¿Hay alguna dependencia externa que ya no necesitamos?
- ¿Los protocolos en `core/interfaces/` reflejan las necesidades actuales?

### ADRs activos (v4.3)
| ADR | Estado | ¿Sigue vigente? |
|-----|--------|-----------------|
| ADR-007 — Core Modification Rule | Activo | ✅ |
| ADR-030 — Infraestructura congelada v2.3 | Activo | ✅ |
| ADR-031 — Reuso ≥85% + quality gates | Activo | ⚠️ Revisar (ARQ-100 sugiere flexibilizar) |

---

## Pipeline de Desarrollo

### Orden completo
```
Reuse Detector
    → Inventario de consumidores
    → ADR (si aplica)
    → Arquitectura
    → Diseño
    → Implementación
    → Tests
    → Ruff
    → Mypy
    → Seguridad (bandit + check_secrets)
    → Benchmarks (si aplica)
    → Auditoría Arquitectónica
    → Tuneladoras (mejora continua)
    → Consolidación
    → Health Index
    → Promoción
```

### Estados de Promoción
```
BORRADOR
    ↓
IMPLEMENTADO
    ↓
VALIDADO
    ↓
AUDITADO
    ↓
REFACTORIZADO
    ↓
CONSOLIDADO
    ↓
PROMOCIONADO
```

La **auditoría arquitectónica** merece entidad propia. Un cambio puede pasar todas las pruebas y, aún así, introducir acoplamiento o romper principios de diseño. Por eso aparece antes de la promoción, como filtro independiente.

---

## Integración con el Pipeline Existente

| Herramienta existente | Rol en este sistema |
|-----------------------|---------------------|
| `tuneladora_mejora.py` | Ejecuta ARQ-300, ARQ-400, ARQ-500 |
| `auditoria_continua.py` | Verifica ARQ-200, ARQ-600 |
| `reuse_detector.py` | Implementa ARQ-100 |
| `health_check.py` | Alimenta ARQ-800 |
| `check_secrets.py` | Implementa parte de ARQ-900 |
| `audit_secrets.py` | Implementa ARQ-900 |
| `conciencia.py` | Registra estados ARQ-500 |
| `motor/observability/` | Implementa ARQ-700 |
| `scripts/pro/benchmark_*.py` | Implementan ARQ-800 |

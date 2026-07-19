# F28.1 — Stabilization (Prerrequisito)

**Estado:** Propuesta
**Fecha:** 2026-07-19
**Fase base:** F28 (Platform Protocols) — tags v0.28.0-b3, v0.28.1-stabilization, v0.28.2-lockdown

---

## Justificación

F28 no está realmente cerrado:

- **F28_B1_AUDIT.md**: 5 críticos, 5 altos, 5 medios — resueltos en ADR pero NO en código
- **F28_B2_CODE_AUDIT.md**: 2 críticos (checksum nunca verificado, race condition en LocalTransport)
- **F28_PROTOCOL_AUDIT.md**: 4 críticos en comunicación cruzada F24—F27
- **ADRs**: 5 documentos en Draft, no Approved
- **Código**: `motor/platform/` implementado pero con bugs que invalidan el contrato

No se puede construir producción sobre una base quebrada.

---

## Criterio de Salida

| # | Criterio | Cómo se verifica |
|---|----------|------------------|
| 1 | 0 discrepancias ADR ↔ implementación | Diff entre lo que dice cada ADR y lo que hace el código |
| 2 | 0 bugs críticos | F28_B2_CODE_AUDIT.md resuelto y verificado |
| 3 | 0 race conditions | LocalTransport.request() con cobertura de concurrencia |
| 4 | checksum validado siempre | `compute_checksum()` en send, `verify_checksum()` en receive |
| 5 | ProtocolEnvelope usado en todas las llamadas cross-component | F28_PROTOCOL_AUDIT.md resuelto |
| 6 | ADRs Approved (no Draft) | 5 ADRs con estado Approved |
| 7 | Tag estable | `v0.28.3-stable`

---

## Trabajo

### P1 — Bugs críticos de código

| Bug | Archivo | Fix |
|-----|---------|-----|
| Checksum nunca se verifica | `motor/platform/serializer.py` | Implementar `verify_checksum()` en receive path |
| Race condition en `LocalTransport.request()` | `motor/platform/transport.py` | Lock por message_id + test concurrente |
| `send()` sin ProtocolEnvelope | `motor/platform/transport.py` | Envelopar en send() |
| TraceExporter buffer overflow sin backpressure | `motor/platform/tracing.py` | Drop policy cuando buffer lleno |

### P2 — ADRs Draft → Approved

Resolver las 5 contradicciones de F28_B1_AUDIT (ya corregidas en el audit, falta actualizar los documentos ADR) y promover a Approved.

### P3 — Wrappers mínimos F24—F27

Cada componente necesita un adaptador (<50 LOC) que envuelva llamadas entrantes/salientes en ProtocolEnvelope con trace_id, correlation_id, checksum.

---

## Tag

`v0.28.3-stable` — solo después de cumplir los 7 criterios de salida.

---

# F29 — Production Readiness

**Estado:** Propuesta
**Fecha:** 2026-07-19
**Prerrequisito:** F28.1 completado y taggeado

---

## Principios

1. **Cero nuevas capacidades de IA.** No se añaden agentes, fusión, memoria, ni protocolos.
2. **No se modifican APIs públicas congeladas.** Toda integración es por adaptación.
3. **No se rompe compatibilidad.** Ningún test existente debe fallar.
4. **Cada componente tiene**: productor, consumidor, owner, source of truth.
5. **Validación antes que endurecimiento.** Primero se descubre cómo se comporta el sistema real; luego se protege.

---

## Orden de Bloques

```
B1 Observabilidad     (lo mínimo para medir)
       ↓
B2 Validación técnica (datasets públicos, benchmarks, estrés)
       ↓
B3 Validación funcional (casos reales: utilidad, no rendimiento)
       ↓
B4 Operación          (lo que la validación reveló como necesario)
       ↓
B5 Resiliencia        (proteger lo que ya funciona)
       ↓
B6 Compatibilidad     (rolling upgrade, mixed-version, downgrade)
       ↓
B7 Gobernanza         (runbooks definitivos, ownership, SLOs)
       ↓
RR1 Production Readiness (checklist final)
```

---

## B1 — Observabilidad (lo mínimo para medir)

**Objetivo:** Poder medir lo que pasa durante las validaciones.

| Componente | Qué produce | Cómo se consume |
|-----------|-------------|-----------------|
| Health probes | `health()`, `readiness()`, `liveness()` por subsistema | Agregador central + endpoint HTTP |
| Métricas | Prometheus counters/histograms | `/metrics` endpoint |
| Logging estructurado | JSON con component, operation, trace_id, duration_ms | Archivo + stdout |
| Tracing | TraceExporter con span tree | Archivo JSON (OTel en futuro) |

Se implementa lo JUSTO para poder medir B2 y B3. No dashboards aún, no alertas aún.

---

## B2 — Validación Técnica

**Objetivo:** Caracterizar el rendimiento de la plataforma con datos controlados.

| Prueba | Pipeline | Qué mide |
|--------|----------|----------|
| Throughput F24 | WebPipeline.search() | docs/s, latencia p50/p95/p99 |
| Throughput F25 | FusionPipeline.run() | claims/s, fact/s |
| Throughput F26 | Memory.append() + state_at() | entradas/s, consultas/s |
| Throughput F27 | Scheduler.submit() + execute | ejecuciones/s |
| Cadena completa | F24→F25→F26 (+ F27 opcional) | Throughput end-to-end, cuello de botella |
| Memoria | Cada componente aislado | RSS, pico, leak tras 1000 ops |
| Precisión F25 | Corpus conocido → verificar facts generados | Precision, Recall, F1 |
| Estrés | 10x throughput normal | Punto de saturación, degradación |

**Datasets:** Benchmarks públicos, sin datos sensibles. Reproducibles.

---

## B3 — Validación Funcional

**Objetivo:** Demostrar que la plataforma resuelve problemas reales.

**5 dominios, 20 documentos cada uno:**

| Dominio | Tipo de documento | Qué mide |
|---------|------------------|----------|
| Jurídico | Sentencias, contratos (anónimos) | Precisión de extracción, calidad de fusión |
| Técnico | Documentación APIs, manuales open source | Coherencia del conocimiento fusionado |
| Código | Repositorios grandes | Escalabilidad, capacidad de contexto |
| Científico | Artículos open access | Precisión de entidades, relaciones |
| Conversacional | Diálogos largos | Memoria contextual, coherencia temporal |

**Qué se mide (no rendimiento, sino utilidad):**

| Métrica | Cómo |
|---------|------|
| Precisión del fact extraído | Revisión manual de una muestra |
| Coherencia temporal (F26) | ¿Los facts recuperados son consistentes en el tiempo? |
| Utilidad del contexto (F27) | ¿El agente produce mejores respuestas con contexto histórico? |
| Tasa de error real | ¿Cuántos facts son incorrectos? |

**Formato:** Cada dominio produce un informe de una página con hallazgos.

---

## B4 — Operación

**Objetivo:** Poder operar la plataforma de forma continua.

**Nota:** El contenido de B4 se ajusta según lo que B2 y B3 revelen. Si la validación muestra que F26 Memory crece 10GB/día, el backup pasa a prioridad máxima.

| Componente | Acción |
|-----------|--------|
| Graceful shutdown | F24 WebPipeline, F25 FusionPipeline, F26 Memory, F27 Scheduler |
| Health/Readiness/Liveness | Endpoints HTTP en ura-api |
| Backup/Restore F26 | Script + timer diario + verificación checksum |
| docker-compose | Servicios ura-api, ura-memory, prometheus (opcional) |
| Configuración por entorno | Revisar qué valores necesitan cambiar entre dev/staging/prod |

---

## B5 — Resiliencia

**Objetivo:** La plataforma sobrevive a fallos sin pérdida de datos.

| Mecanismo | Dónde | Qué protege |
|-----------|-------|-------------|
| Circuit breaker | Entre F24→F25, F25→F26, F26→F27 | Fallo en cascada |
| Backpressure | F25→F26 (escritura), F26→F27 (lectura) | OOM por ráfagas |
| Degradación graceful | Si F26 falls, F24→F25 siguen sin persistencia | Disponibilidad parcial |
| Timeouts configurables | Todas las llamadas cross-component | Bloqueo indefinido |

**Chaos tests** (7 escenarios):

| CT | Escenario | Verificación |
|----|-----------|-------------|
| 1 | Journal corrupto (F26) | Recuperación graceful, resto del log intacto |
| 2 | Snapshot faltante (F26) | Reconstrucción desde Journal |
| 3 | Scheduler kill (F27) | Reinicio, cola preservada |
| 4 | Componente inalcanzable | Circuit breaker OPEN, degradación graceful |
| 5 | Disco lleno simulado | Error graceful, no crash |
| 6 | Latencia extrema (10s) | Timeout, circuit breaker |
| 7 | Reinicio en caliente | Graceful shutdown + restart |

---

## B6 — Compatibilidad y Evolución

**Objetivo:** Demostrar que la plataforma soporta cambios de versión sin interrupción.

| Prueba | Qué demuestra |
|--------|---------------|
| Rolling upgrade | Actualizar un componente mientras el resto opera |
| Mixed-version | Componente v1 habla con componente v2 |
| Downgrade | Volver a versión anterior sin pérdida de datos |
| Forward compat | Componente nuevo recibe mensaje de componente futuro |
| Backward compat | Componente antiguo recibe mensaje de componente nuevo |
| Recuperación entre versiones | Backup v1 → restore en v2 → verify |

**Requisito:** F28.1 debe proporcionar el versionado de protocolo para esto.

---

## B7 — Gobernanza

**Objetivo:** Que la plataforma sea mantenible por más de una persona.

Se escribe DESPUÉS de B2—B6, cuando se sabe exactamente qué necesita cada Runbook.

| Artefacto | Contenido |
|-----------|-----------|
| Matriz de propiedad | Productor, consumidor, owner, source of truth por componente |
| Runbooks | Arranque, parada, recuperación, degradación, incidente |
| Release checklist | Automatizado en CI |
| SLOs + error budgets | Basados en métricas reales de B2 |
| ADRs F29 | 029-01..05 (Observabilidad, Validación, Operación, Resiliencia, Gobernanza) |

---

## RR1 — Production Readiness

**Checklist final:**

```
□ F28.1 estable (tag v0.28.3-stable, 0 bugs críticos)
□ B1: Health probes en todos los componentes
□ B1: Métricas Prometheus exportándose
□ B1: Logging estructurado activo
□ B2: Benchmarks publicados (throughput, latencia, memoria)
□ B3: 5 informes de validación funcional
□ B4: Graceful shutdown verificado
□ B4: Backup/restore de F26 automático
□ B4: docker-compose funcional
□ B5: 7 chaos tests documentados y ejecutables
□ B5: Circuit breakers en todas las llamadas cross-component
□ B6: Rolling upgrade verificado
□ B6: Mixed-version verificado
□ B6: Forward/backward compat verificado
□ B7: Runbooks publicados
□ B7: Release checklist en CI
□ 0 regresiones vs baseline F28.1 (tests + lint)
□ Tag v0.29.0-fase29
```

---

## Esfuerzo Estimado por Entregable

| Bloque | Entregables | Esfuerzo |
|--------|-------------|----------|
| **F28.1** | 0 bugs críticos, ADRs Approved, wrappers F24—F27, tag stable | 12-18h |
| **B1** | Health wiring + metrics endpoint + logging + tracing mínimo | 8-12h |
| **B2** | Benchmarks + datasets + informe técnico | 12-18h |
| **B3** | 5 dominios procesados + 5 informes | 15-25h |
| **B4** | Shutdown + health endpoints + backup + compose + config | 10-15h |
| **B5** | Circuit breakers + backpressure + 7 chaos tests | 12-18h |
| **B6** | Rolling upgrade + mixed-version + compat tests | 8-12h |
| **B7** | Ownership + runbooks + release checklist + SLOs + ADRs | 8-12h |
| **RR1** | Checklist final + tag | 2-4h |
| **Total** | | **87-134h** |

---

## ADRs de F29

| ADR | Título | Bloque |
|-----|--------|--------|
| **ADR-028-11** | F28.1 Stabilization | F28.1 |
| **ADR-029-01** | Observabilidad de Plataforma | B1 |
| **ADR-029-02** | Validación — Técnica y Funcional | B2 + B3 |
| **ADR-029-03** | Operación | B4 |
| **ADR-029-04** | Resiliencia | B5 |
| **ADR-029-05** | Compatibilidad y Evolución | B6 |
| **ADR-029-06** | Gobernanza | B7 |

---

## Lo que NO incluye F29

- Nuevos agentes, fusión, memoria, o protocolos
- Modificación de APIs públicas congeladas
- Migración a Kubernetes
- OpenTelemetry nativo (se prepara el terreno)
- Interfaz de usuario web
- Plugins F11 (no se tocan)

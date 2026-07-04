# ADR-007: Regla del Núcleo — Excepciones Controladas

> **Fecha:** 2026-07-03
> **Propósito:** Definir cuándo y cómo se puede modificar el núcleo (`core/`)
> **Estado:** ✅ Aprobado

## Contexto

Desde Fase 4, la regla "nunca modificar el núcleo" ha protegido la estabilidad
del sistema. Sin embargo, el análisis crítico (PREGUNTAS_INCOMODAS.md) identificó
que esta regla, tomada como absoluto moral, está creando barreras artificiales
que dificultan la evolución del proyecto.

Problemas concretos detectados:
1. **Dos sistemas de eventos sin puente**: `core/event_bus.py` (ZeroMQ) y
   `knowledge/engine/eventbus.py` (in-process) son independientes. No hay forma
   de que Capa 11 publique eventos en el bus del núcleo ni viceversa.
2. **Sin camino de vuelta**: El EventBus es unidireccional (core → Capa 11).
   Capa 11 no puede influenciar al núcleo.
3. ~~**Config duplicada**: `core/config.py` (UraConfig) no tenía el path de la
   knowledge DB. Cada módulo de Capa 11 lo resolvía por su cuenta.~~
   ✅ **Resuelto en fase de cierre post-Fase 8**: `core/config.py` eliminado,
   `motor/core/config.py` es la única implementación de `UraConfig`.
4. **Sin hooks de compilación**: El compilador no puede leer KnowledgeAssets
   para resolver referencias ni disparar re-extracción cuando un documento cambia.

## Decisión

**La regla cambia de "nunca modificar el núcleo" a "el núcleo solo se modifica
con excepción documentada y validación obligatoria".**

### Principios

1. **API pública del núcleo es inviolable**. Las interfaces, protocolos y
   contratos públicos (`UraConfig`, `EventBus.publish()`, etc.) no cambian su
   firma. Solo se añaden campos o métodos nuevos (backward compatible).

2. **Modificaciones permitidas** (con ADR, tests, y rollback plan):
   - Añadir campos opcionales (nullable, con default) a `UraConfig`
   - Añadir topics al ZeroMQ EventBus (sin cambiar topics existentes)
   - Añadir hooks o callbacks en el orquestador (sin cambiar el flujo existente)
   - Añadir métodos al `EventBus` Protocol (sin cambiar firma de existentes)
   - Toda modificación permitida debe ser **degradable**: el sistema debe
     funcionar sin ella (ej: campo opcional con None = comportamiento antiguo)

3. **Modificaciones prohibidas** (lista exhaustiva):
   - Refactorizar o renombrar funciones, clases, módulos o archivos existentes
   - Cambiar la firma de métodos, funciones o constructores existentes
   - Eliminar funcionalidad o reducir el conjunto de features
   - **Cambiar el comportamiento observado** de cualquier función, incluso
     si la firma no cambia (congelación semántica)
   - Añadir dependencias nuevas al núcleo (se inyectan desde fuera)
   - Cualquier modificación que **pueda lograrse mediante un nuevo Protocol,
     un nuevo suscriptor de EventBus, o un adaptador externo** sin tocar
     el núcleo
   - Cualquier modificación que **carezca de plan de rollback**

### Proceso para modificar el núcleo

1. **ADR requerido**: Toda modificación al núcleo requiere un ADR que
   documente:
   - **Qué** se cambia (diff completo)
   - **Por qué** es necesario (problema concreto)
   - **Justificación de necesidad**: demostrar que el cambio NO puede
     lograrse mediante un nuevo Protocol, un suscriptor de EventBus, o
     un adaptador externo. Si existe alternativa sin tocar el núcleo,
     esa es la respuesta correcta.
   - **Plan de migración**: si el cambio afecta a datos (schema, config),
     incluir script de migración.
   - **Plan de rollback**: procedimiento para revertir el cambio sin
     pérdida de datos ni estado.
   - **Degradación**: verificar que el sistema funciona sin la modificación
     (debe ser degradable).
2. **Tests de no-regresión**: La modificación debe incluir tests que
   verifiquen que el comportamiento existente no cambia (mismos inputs →
   mismos outputs).
3. **Revisión obligatoria por segunda parte**: La modificación debe ser
   revisada por otro agente o humano antes de aplicarse. No puede hacerse
   en una sesión autónoma sin supervisión.
4. **Aprobación explícita**: Requiere validación manual del responsable
   del proyecto.

## Alternativas Consideradas

1. **Mantener la regla actual**: Crearía un cuello de botella arquitectónico
   creciente. Eventualmente habría que romper la regla o duplicar funcionalidad
   (como los dos event buses actuales). → **Rechazado**

2. **Eliminar la regla por completo**: Riesgo de cambios irresponsables en el
   núcleo. Sin protección, la estabilidad del sistema se degradaría. → **Rechazado**

3. **Separar core/ en core-api/ y core-impl/**: Demasiado intrusivo para el
   estado actual del proyecto. Sería apropiado en una rearquitectura mayor. → **Futuro**

## Consecuencias

- **Positivas**: Capa 11 puede evolucionar sin duplicar infraestructura.
  El compilador puede integrarse con el knowledge engine. Los eventos fluyen
  bidireccionalmente.
- **Negativas**: Mayor responsabilidad de revisión. Riesgo de acoplamiento si
  no se documentan bien las excepciones.
- **Neutrales**: El equipo debe aprender a escribir ADRs para cambios al núcleo.
  La regla anterior era simple pero insostenible.

## Próximos Pasos (Opcionales)

| # | Acción | Prioridad |
|---|--------|-----------|
| 1 | Añadir `knowledge_db_path` a `UraConfig` (opcional, default None) | Baja |
| 2 | Unificar los dos EventBus: que Capa 11 publique en ZeroMQ | Media |
| 3 | Añadir hook post-compile en el orquestador para disparar extracción | Baja |

---

*ADR-007 — 2026-07-03 — Con endurecimientos post-auditoría (AUDIT_EVOLUCION_MODELO.md)*

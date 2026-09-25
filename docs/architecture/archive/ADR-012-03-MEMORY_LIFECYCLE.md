# ADR-012-03: Memory Lifecycle — Creación, Consolidación, Compresión, Olvido

> **Fecha:** 2026-07-05
> **Fase:** 12 (Inteligencia)
> **Propósito:** Definir el ciclo de vida completo de un registro de memoria.
> **Estado:** ✅ Aprobado

## Contexto

ADR-012-02 define los tipos de memoria y el contrato `MemoryRecord`. Este ADR
define **cómo** los registros transitan entre tipos, cuándo se consolidan,
comprimen y olvidan. Sin este ciclo de vida formal, la memoria crecería sin
control y los registros obsoletos contaminarían las búsquedas.

## Decisión

### 1. Diagrama de Flujo

```
                  ┌─────────────────────┐
                  │   Working Memory    │
                  │  (sesión actual)    │
                  └─────────┬───────────┘
                            │ fin de interacción
                            ▼
                  ┌─────────────────────┐
                  │   Episodic Memory   │
                  │  (store + embed)    │
                  └─────────┬───────────┘
                           / \
                          /   \
                   ┌─────┘     └─────┐
                   ▼                  ▼
        ┌──────────────────┐  ┌──────────────────┐
        │  Consolidación   │  │  Abstracción     │
        │  (batch → LTM)   │  │  (LLM → hechos)  │
        └──────────────────┘  └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │  Semantic Memory │
                              │  (dedup + store) │
                              └────────┬─────────┘
                                       │
                              ┌──────────────────┐
                              │  Long-Term Memory│
                              │  (KE index)      │
                              └──────────────────┘

    Todos los tipos → Decaimiento → Compresión → Olvido
```

### 2. Ciclo de Vida Detallado

#### 2.1 Creación
```
Trigger: El sistema recibe una interacción (query, respuesta, feedback)
1. MemoryRecord(type=WORKING, payload=input)
2. Working Memory almacena en RAM
3. Si working.count() > max → eliminar el más antiguo (FIFO)
```

#### 2.2 Consolidación (Working → Episodic)
```
Trigger: Fin de interacción (respuesta entregada al usuario)
1. Working.flush() → MemoryRecord(type=EPISODIC, payload=turno completo)
2. Generar embedding del payload
3. Asignar importancia según:
   - feedback del usuario (si existe): ±0.3
   - duración de la interacción: +0.1 por minuto (max 0.5)
   - número de referencias a KE: +0.1 por referencia (max 0.3)
   - default: 0.5
4. Asignar TTL = 7 días (configurable)
5. Episodic.store(record)
```

#### 2.3 Abstracción (Episodic → Semantic)
```
Trigger: Episodio marcado como "relevante" (importancia > 0.7) O
         mismo patrón detectado 3+ veces en 24h
1. LLM extrae hechos del episodio:
   "El usuario preguntó X y la respuesta fue Y"
   → "El sistema responde a X con Y"
2. SemanticMemory.store(fact, dedup=True)
3. Episodio actualizado con reference al hecho semántico
```

#### 2.4 Compresión
```
Trigger: Episodic.count() > max_records (default 10,000) O
         ejecución manual / programada
1. Seleccionar bloques de episodios similares (misma entidad, mismo tema)
2. Generar resumen por bloque vía LLM
3. Almacenar resumen como nuevo Episodic con type=EPISODIC+compressed
4. Registrar referencia: resumen.refs = [episodio_ids...]
5. Los episodios originales se marcan para olvido (ttl reducido a 24h)
```

#### 2.5 Recuperación
```
Trigger: Búsqueda por query
1. Buscar en Working Memory (más rápido)
2. Buscar en Episodic Memory (embedding similarity)
3. Buscar en Semantic Memory (embedding similarity)
4. (Opcional) Buscar en KE (Long-Term)
5. Fusionar resultados con RRF
6. Aplicar boost por importancia y freshness
7. Retornar top-K ordenados por score compuesto
```

#### 2.6 Olvido
```
Trigger: (TTL expirado) OR (decaimiento por falta de uso) OR (explícito)
1. Evaluar criterios de olvido:
   - TTL alcanzado → marcar para eliminación
   - importance < 0.2 Y no accedido en > 30 días → marcar
   - importance < 0.5 Y no accedido en > 90 días → marcar
   - importance >= 0.8 → protegido (no se olvida)
2. Los marcados se eliminan del store y su embedding del índice
3. Se registra el olvido en un log de auditoría
```

### 3. Parámetros Configurables

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `working_max` | 50 | Máximo de registros en Working Memory |
| `episodic_ttl` | 604800 (7 días) | TTL por defecto para episodios |
| `episodic_max` | 10000 | Máximo de episodios antes de comprimir |
| `semantic_ttl` | None (permanente) | TTL para hechos semánticos |
| `importance_boost_feedback` | 0.3 | Incremento por feedback positivo |
| `importance_decay_per_day` | 0.01 | Decremento diario por falta de acceso |
| `protect_threshold` | 0.8 | Importancia mínima para protección |
| `forget_after_days_low` | 30 | Días sin acceso para olvido (importancia < 0.2) |
| `forget_after_days_med` | 90 | Días sin acceso para olvido (importancia < 0.5) |
| `compress_batch_size` | 1000 | Episodios por lote de compresión |

### 4. Criterios de Calidad

| Métrica | Objetivo | Cómo se mide |
|---------|----------|--------------|
| Tasa de acierto en recuperación | ≥ 80% | ¿El episodio relevante aparece en top-5? |
| Latencia P95 de recuperación | ≤ 200ms | Búsqueda en memoria episódica |
| Tasa de compresión | ≥ 5:1 | Episodios originales / resúmenes generados |
| Precisión de olvido | ≥ 95% | ¿Se olvidó algún registro que debía conservarse? |
| Cobertura de episodios | ≥ 90% | ¿Episodios recuperables dentro del TTL? |

## Consecuencias

### Positivas
- Ciclo de vida completo y predecible
- Parámetros configurables sin cambiar código
- Protección de recuerdos importantes
- Trazabilidad completa (origen → compresión → olvido)

### Negativas
- La abstracción (Episodic → Semantic) requiere LLM (coste operativo)
- La compresión por lotes puede ser costosa en memoria
- El recuento de accesos añade una escritura adicional por consulta

## Compatibilidad
- No requiere cambios en KE existente
- El ciclo de vida es orquestado por un nuevo `MemoryManager`
- Cada etapa del ciclo puede ser reemplazada independientemente

# ADR-028-07: Evolution Strategy

**Status:** Draft  
**Phase:** F28-B1

---

## Version Lifecycle

```
protocol_version = "1.0" → "1.1" → "1.2" → "2.0" → "2.1" → ...
                     │        │        │        │
                   active   active  deprec.  active

Etapas:
  ACTIVE     → versión actual, soporte completo
  DEPRECATED → aún funciona, pero no se recomienda
  SUNSET     → programado para eliminación
  REMOVED    → ya no existe
```

## Timeline

```
Month 0:  v1.0 release (ACTIVE)
Month 6:  v1.1 release (ACTIVE), v1.0 → DEPRECATED
Month 12: v2.0 release (ACTIVE), v1.0 → REMOVED, v1.1 → DEPRECATED
Month 18: v2.1 release (ACTIVE), v1.1 → REMOVED
```

## Migration Process

```
1. Nueva versión coexiste con la anterior (mismos consumers la soportan)
2. Producers migran uno a uno
3. Ningún producer queda en version antigua sin un consumer que la soporte
4. La negociación de versiones (ADR-028-03) garantiza compatibilidad durante la transición
5. Una vez migrados todos los producers, se declara DEPRECATED la versión antigua
6. Se elimina tras un período de solapamiento mínimo de 2 releases
```

## Independent Subsystem Evolution

```
Cada subsistema (F24, F25, F26, F27) puede evolucionar su protocol_version
de forma independiente. No hay version global del sistema.

Ejemplo:

  F25 Knowledge Fusion: protocol_version = "2.3"
  F26 Memory:           protocol_version = "1.7"
  F27 Agents:           protocol_version = "1.2"

Cada par emisor-receptor negocia su versión en el primer intercambio.
```

## Deprecation Policy

```
DP01. Un campo deprecated sigue funcionando por 2 releases MAJOR
DP02. Un message_type deprecated sigue funcionando por 2 releases MAJOR
DP03. Una capability deprecated sigue funcionando por 2 releases MAJOR
DP04. Al deprecar, el emisor emite warning en metadata: {"deprecated": "field_x"}
DP05. Al eliminar, se incrementa MAJOR
DP06. No hay eliminación sin MAJOR bump
```

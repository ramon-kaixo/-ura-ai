# ADR-029-05: Compatibilidad y Evolución

**Estado:** Draft
**Fecha:** 2026-07-19
**Fase:** F29 — Bloque B6
**Dependencias:** F28.1 estable (versionado de protocolo funcional), ADR-029-03 (Operación)

---

## Contexto

La plataforma tiene versionado de protocolo definido (ADR-028-03) pero nunca se ha probado:

- **Rolling upgrade**: Actualizar un componente mientras el resto opera
- **Mixed-version**: Componente v1 habla con componente v2
- **Downgrade**: Volver a versión anterior sin pérdida de datos
- **Forward compatibility**: Componente nuevo recibe mensaje de componente futuro
- **Backward compatibility**: Componente antiguo recibe mensaje de componente nuevo

Sin estas pruebas, una actualización en producción puede causar una caída general.

---

## Opciones Consideradas

### Opción A: Probar solo backward compatibility (la más común)
- **Ventaja:** Menos trabajo, cubre el caso más frecuente.
- **Desventaja:** No detecta problemas de rolling upgrade ni downgrade.
- **Veredicto:** ❌ Rechazado. Una plataforma que no soporta rolling upgrade no puede actualizarse sin downtime.

### Opción B: Probar las 5 dimensiones (SELECCIONADA)
- **Razonamiento:** F28 proporciona el versionado, F29 debe demostrar que funciona. Sin estas pruebas, el versionado es teoría no verificada.
- **Veredicto:** ✅ Seleccionada.

---

## Decisión

Probar 5 dimensiones de compatibilidad utilizando los wrappers de protocolo de F28.1.

### Pruebas

| Dimensión | Configuración | Verificación |
|-----------|--------------|-------------|
| Rolling upgrade | Actualizar F25 mientras F24+F26+F27 operan | 0 errores cross-component durante actualización |
| Mixed-version | F24 v1 → F25 v2 → F26 v1 | Mensajes correctamente serializados/deserializados |
| Downgrade | F25 v2 → F25 v1, con datos generados por v2 | 0 pérdida de datos, 0 errores de formato |
| Forward compat | F24 v1 recibe mensaje de F25 v3 (futuro) | Dead-letter o rechazo graceful |
| Backward compat | F25 v3 recibe mensaje de F24 v1 (antiguo) | Procesado correcto |

### Versiones de prueba

| Componente | v1 (base) | v2 (saltos) |
|-----------|----------|-------------|
| F24 WebPipeline | F28.1 tag | Modificar un campo no crítico |
| F25 FusionPipeline | F28.1 tag | Añadir campo opcional a Fact |
| F26 Memory | F28.1 tag | Modificar metadata |
| F27 Agents | F28.1 tag | Añadir capability |

### Criterios de éxito

| Prueba | Debe pasar | Puede fallar |
|--------|-----------|-------------|
| Rolling upgrade | Sin pérdida de mensajes | Latencia elevada durante transición |
| Mixed-version | Sin errores de protocolo | Sin pérdida de datos |
| Downgrade | Todos los datos previos legibles | Funcionalidad nueva perdida (esperado) |
| Forward compat | Error graceful, no crash | Sin pérdida de datos |
| Backward compat | Mensajes antiguos procesados | Sin errores |

---

## Consecuencias

**Positivas:**
- Demuestra que el versionado de F28 no es teoría
- Permite actualizaciones sin downtime en producción
- Downgrade seguro si una versión nueva tiene problemas

**Negativas:**
- Requiere preparar versiones de prueba (v1/v2) de cada componente
- Las pruebas de rolling upgrade requieren entornos multi-proceso

**Neutras:**
- Se reutiliza F28.1 ProtocolRegistry + VersionNegotiator
- No se modifica código de F24—F27 — solo los wrappers de protocolo

---

## Invariantes

| ID | Invariante | Verificación |
|----|-----------|-------------|
| C01 | Rolling upgrade completa sin pérdida de mensajes | Test de integración |
| C02 | Mixed-version no produce errores de protocolo | Test de integración |
| C03 | Downgrade preserva todos los datos existentes | Test post-downgrade |
| C04 | Forward compatibility produce error graceful, no crash | Test |
| C05 | Backward compatibility procesa mensajes antiguos | Test |
| C06 | Tiempo de convergencia post-upgrade <30s | Medición |
| C07 | Sin cambios en APIs públicas de F24—F27 | Diff de interfaz |

---

## Formato de Prueba

Cada prueba sigue esta plantilla:

```
## Prueba: [Nombre]

Configuración inicial:
- Componentes involucrados: [lista]
- Versión base: [vX]
- Versión destino: [vY]

Procedimiento:
1. [Paso]
2. [Paso]
3. [...]

Resultado esperado:
- [Comportamiento]

Resultado observado:
- [Comportamiento]

Veredicto: ✅ PASA | ⚠️ PASA CON OBSERVACIONES | ❌ FALLA
```

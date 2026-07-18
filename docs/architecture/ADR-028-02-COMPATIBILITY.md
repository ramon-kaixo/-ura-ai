# ADR-028-02: Compatibility Contract

**Status:** Draft  
**Phase:** F28-B1  
**Depends on:** ADR-028-01  

---

## Contract

Every component that sends or receives ProtocolEnvelopes must comply with:

### Backward Compatibility

```
BC01. Un nuevo consumer debe poder procesar mensajes de un producer antiguo.
BC02. Un nuevo producer debe poder enviar mensajes que un consumer antiguo entienda.
BC03. Campos nuevos en el envelope deben ser opcionales (default=None o ausentes).
BC04. El receptor debe ignorar campos que no reconoce (forward compat).
BC05. El emisor no debe enviar campos que el receptor no puede ignorar.
```

### Forward Compatibility

```
FC01. Un consumer antiguo debe poder procesar mensajes de un producer nuevo.
FC02. Si el consumer antiguo no reconoce un campo, lo ignora.
FC03. Si el consumer antiguo no reconoce un message_type, lo rechaza con un error conocido.
```

### Breaking Changes

```
BR01. Eliminar un campo requerido = breaking.
BR02. Cambiar el tipo de un campo existente = breaking.
BR03. Añadir un campo requerido = breaking (solo permitido con MAJOR bump).
BR04. Cambiar semántica de entrega = breaking.
BR05. package: protocol_version MAJOR++
```

### Non-Breaking Changes

```
NB01. Añadir un campo opcional = non-breaking.
NB02. Añadir un nuevo message_type = non-breaking.
NB03. Añadir una nueva capability = non-breaking.
NB04. package: protocol_version MINOR++ (o PATCH si es corrección)
```

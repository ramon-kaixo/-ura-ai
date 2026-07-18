# ADR-028-01: Internal Platform Protocol Architecture

**Status:** Draft  
**Phase:** F28-B1  
**Objective:** Single protocol model for all inter-subsystem communication across F24–F27.  
**Scope:** Local calls, EventBus, Message Queue, RPC, multiprocess, multinode.  
**Transport-independent.**  

---

## 1. ProtocolEnvelope — Raíz de Todos los Mensajes

```python
@dataclass(frozen=True)
class ProtocolEnvelope:
    # Identidad
    message_id: str                    # SHA-256 único
    protocol_version: str              # semver del protocolo ("1.0")
    schema_version: str                # versión del schema del payload ("1.0")
    message_type: str                  # nombre del tipo de mensaje ("ToolRequest")
    message_kind: MessageKind          # COMMAND | QUERY | EVENT | RESPONSE | ERROR

    # Trazabilidad
    correlation_id: str                # trace_id que cruza toda la cadena
    causation_id: str | None           # message_id del mensaje que causó este
    timestamp: float                   # instante de creación (determinista)

    # Enrutamiento
    source: str                        # "fusion" | "memory" | "agents" | "web"
    destination: str                   # componente destino

    # Semántica de entrega
    delivery: DeliverySemantics        # AT_MOST_ONCE | AT_LEAST_ONCE | EXACTLY_ONCE
    idempotency_key: str | None        # para EXACTLY_ONCE

    # Políticas
    retry_policy: RetryPolicy | None
    timeout_ms: int
    cancelable: bool

    # Contenido
    payload: bytes                     # payload serializado (independiente del schema)
    payload_type: str                  # "json" | "msgpack" | "protobuf"
    payload_schema_version: str        # versión del schema del payload

    # Metadatos
    metadata: dict[str, str]           # extensible, sólo strings planos
    size_bytes: int                    # tamaño total del envelope
    checksum: str                      # SHA-256 del contenido completo

    # Evolución
    capabilities: list[str]            # capacidades del emisor ("protocol.v2", "compression.gzip")
    reserved: dict[str, str]           # para evolución futura, ignorado por versiones antiguas
```

---

## 2. Tipos Soportados

```python
class MessageKind(StrEnum):
    COMMAND = "command"      # "haz algo" (create, update, delete)
    QUERY = "query"          # "dime algo" (get, list, search)
    EVENT = "event"          # "algo ocurrió" (notificación)
    RESPONSE = "response"    # respuesta a COMMAND o QUERY
    ERROR = "error"          # error tipificado

class DeliverySemantics(StrEnum):
    AT_MOST_ONCE = "at_most_once"      # fire-and-forget
    AT_LEAST_ONCE = "at_least_once"    # retry hasta ACK
    EXACTLY_ONCE = "exactly_once"      # idempotency_key obligatorio

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_base_ms: int = 100
    backoff_multiplier: float = 2.0
    max_backoff_ms: int = 30000
    retryable_errors: tuple[str, ...] = ("timeout", "transient", "unavailable")

@dataclass(frozen=True)
class ErrorEnvelope:
    error_code: str             # "TOOL_TIMEOUT" | "BUDGET_EXCEEDED" | etc.
    error_message: str
    error_details: dict[str, str]
    component: str              # qué componente generó el error
    original_message_id: str    # qué mensaje causó el error
    retryable: bool
```

---

## 3. Boundaries

```python
class ComponentBoundary:
    """Límite entre componentes del mismo proceso.
    - Misma memoria, mismo ciclo de vida.
    - Sin serialización (punteros directos).
    - ProtocolEnvelope usado solo para auditoría.
    """

class ProtocolBoundary:
    """Límite entre componentes que se comunican vía protocolo.
    - Serialización obligatoria.
    - ProtocolEnvelope requerido.
    - Transporte intercambiable.
    """

class TransportBoundary:
    """Límite entre nodos físicos.
    - Misma semántica que ProtocolBoundary.
    - Añade: autenticación, cifrado, descubrimiento.
    - Transporte: HTTP, gRPC, Message Queue.
    """
```

**Regla:** El mismo `ProtocolEnvelope` se usa en las tres boundaries. El contenido del envelope no cambia. Solo cambia el medio de transporte.

---

## 4. Transport Abstraction

```python
class Transport(ABC):
    @abstractmethod
    async def send(self, envelope: ProtocolEnvelope) -> None: ...
    @abstractmethod
    async def receive(self) -> ProtocolEnvelope: ...
    @abstractmethod
    async def request(self, envelope: ProtocolEnvelope) -> ProtocolEnvelope: ...
```

**Implementaciones:** `InProcessTransport`, `EventBusTransport`, `PulsarTransport`, `GrpcTransport`, `HttpTransport`. Todas intercambiables sin modificar el protocolo.

---

## Invariants

### Identity (I)

```
I01. message_id = SHA-256(source + destination + message_type + timestamp + payload_checksum)[:16]
I02. message_id es inmutable una vez creado
I03. correlation_id no cambia a través de toda la cadena de mensajes
I04. causation_id apunta a un message_id existente (o None)
I05. Dos mensajes con el mismo message_id son el mismo mensaje (idempotencia)
I06. message_id nunca se reutiliza
```

### Compatibility (C)

```
C01. protocol_version usa semver estricto (MAJOR.MINOR)
C02. protocol_version MAJOR diferente = breaking change
C03. protocol_version MINOR diferente = compatible (forward + backward)
C04. Emisor con protocol_version MINOR < receptor MINOR: funciona (backward compat)
C05. Emisor con protocol_version MAJOR == receptor MAJOR: funciona
C06. Emisor con protocol_version MAJOR > receptor MAJOR: no funciona (requiere upgrade)
C07. schema_version independiente de protocol_version
C08. schema_version MAJOR diferente = payload diferente
C09. Todo mensaje debe poder ignorar campos desconocidos (forward compat)
C10. Todo mensaje debe funcionar sin campos nuevos (backward compat)
```

### Versioning (V)

```
V01. protocol_version se negocia en el primer intercambio (version negotiation)
V02. El resultado de la negociación es vinculante para toda la sesión
V03. capabilities lista las extensiones soportadas (compresión, cifrado, etc.)
V04. Una capability no listada = no soportada
V05. reserved se ignora en versiones receptoras que no lo reconocen
V06. La deprecación de un campo sigue: DEPRECATED (n) → REMOVED (n+2)
V07. Ningún cambio breaking sin MAJOR bump
```

### Delivery (D)

```
D01. AT_MOST_ONCE: el mensaje se envía una vez, sin reintentos
D02. AT_LEAST_ONCE: reintento hasta ACK o agotar retry_policy
D03. EXACTLY_ONCE: idempotency_key obligatorio + deduplicación en receptor
D04. idempotency_key único por operación (no reutilizar)
D05. El receptor debe rechazar mensajes con idempotency_key duplicado
D06. timeout_ms se respeta: si no hay respuesta en el plazo, se considera fallo
D07. cancelable=True permite cancelar un mensaje en curso
```

### Serialization (S)

```
S01. payload es bytes. El schema se negocia fuera de banda (schema registry)
S02. payload_type determina el formato de serialización
S03. payload_schema_version identifica la versión exacta del schema
S04. Todo payload debe poder deserializarse con schema_version conocido
S05. checksum verifica integridad del envelope completo
S06. size_bytes ≤ 10 MB por defecto (configurable por mensaje)
S07. compression = "gzip" | "zstd" | "none" (negociado via capabilities)
```

### Observability (O)

```
O01. Todo mensaje tiene message_id, correlation_id, causation_id
O02. correlation_id persiste en todos los mensajes de una misma operación
O03. causation_id permite reconstruir el árbol causal completo
O04. timestamp es determinista (time.time() en origen, no se reasigna)
O05. source y destination permiten enrutamiento y filtrado
O06. ErrorEnvelope siempre acompaña a un mensaje de tipo ERROR
```

### Security (SEC)

```
SEC01. Los mensajes entre nodos deben autenticarse
SEC02. Los mensajes entre nodos deben cifrarse en tránsito
SEC03. reserved no debe usarse para datos sensibles
SEC04. size_bytes protege contra mensajes maliciosos grandes
```

### Evolution (E)

```
E01. Todo mensaje nuevo debe poder añadirse sin cambiar protocol_version MAJOR
E02. Todo campo nuevo debe ser opcional (default=None)
E03. capabilities se extiende sin cambiar protocol_version
E04. reserved está disponible para emergencias sin bump
E05. La negociación de versiones permite coexistencia de nodos con diferentes versiones
E06. Un nodo antiguo nunca recibe mensajes que no puede entender
```

---

## Traceability Matrix

| Finding | ADR | Invariants |
|---------|-----|------------|
| F-01 (No protocol version) | ADR-028-03 | C01-C06, V01-V03 |
| F-02 (No envelope) | ADR-028-01 | I01, D01-D07, S01-S07 |
| F-03 (No correlation ID) | ADR-028-05 | I03, O01-O02 |
| F-04 (No causation ID) | ADR-028-05 | I04, O03 |
| F-05 (No delivery semantics) | ADR-028-04 | D01-D07 |
| F-06 (No schema version) | ADR-028-04 | C07-C10, S03-S04 |
| F-07 (ABC no versioning) | ADR-028-03 | V01-V07 |
| F-08 (No remote protocol) | ADR-028-01 | E01-E06 |
| F-09 (Queue not serializable) | ADR-028-04 | S01-S04 |
| F-10 (No execution_id) | ADR-028-05 | O01-O02 |
| F-11 (EventBus unused) | ADR-028-01 | Transport abstraction |
| F-12 (No size budget) | ADR-028-04 | S06, SEC04 |

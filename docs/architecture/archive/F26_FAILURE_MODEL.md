# F26 — Modelo de Fallos (Failure Model)

## Escenarios y Comportamiento Esperado

| Escenario | Comportamiento | Recuperación |
|-----------|---------------|--------------|
| **Caída del proceso** | El estado en memoria se pierde. El journal en disco tiene todas las entries hasta el último `fsync`. | `Memory(auto_recover=True)` carga snapshot + replay journal. Pérdida máxima = entries entre el último `append` y el `fsync` (prácticamente 0 con fsync síncrono). |
| **Caída del SO** | Similar a caída de proceso. Los `fsync` pendientes pueden perderse. | Misma recuperación. Pérdida máxima = entries no fsynchead. |
| **Pérdida de energía** | Los buffers del sistema de archivos pueden descartarse. | Recovery desde último snapshot + journal. Pérdida potencial = entries desde el último snapshot. Journal truncado se tolera (última línea incompleta omitida). |
| **Disco lleno** | `Journal.append()` lanza `OSError: No space left on device`. El entry NO se pierde (no se escribió). | El sistema debe detectar el error y: (1) rotar el journal si hay espacio en otro disco, (2) forzar un snapshot para liberar espacio, o (3) notificar al operador. |
| **Permisos insuficientes** | `Journal.open()` lanza `PermissionError`. La memoria no puede iniciar. | El operador debe corregir permisos. No hay recuperación automática. |
| **Snapshot corrupto** | `_load_snapshot()` detecta checksum incorrecto y lanza `ValueError`. | `_recover()` captura el error y recupera desde el journal únicamente. El snapshot se descarta. |
| **Journal corrupto** | Líneas corruptas se omiten. Entradas válidas se conservan. | Recovery continúa con las entradas válidas. Las corruptas se pierden. |
| **Snapshot + journal perdidos** | `FileNotFoundError` al iniciar. Memoria vacía. | No hay recuperación posible. El estado del conocimiento se pierde. |
| **Dos procesos escribiendo** | Sin protección. El journal se corrompe (escritura concurrente). | F26 no soporta escritura concurrente. Es responsabilidad del orquestador serializar. |

## Resiliencia

- El sistema tolera corrupción parcial de datos
- El sistema tolera caídas del proceso sin pérdida (fsync)
- El sistema NO tolera escritura concurrente
- El sistema NO tolera pérdida de ambos archivos (snapshot + journal)

## Próximos pasos

Para una versión distribuida o con mayor resiliencia:
- Replicación del journal a otro disco/nodo
- Snapshots periódicos automáticos
- Verificación periódica de checksums
- Alertas de espacio en disco

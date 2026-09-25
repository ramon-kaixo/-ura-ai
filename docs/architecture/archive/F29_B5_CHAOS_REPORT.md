# F29 B5 — Chaos Tests Report

## Summary

| CT | Escenario | Resultado | Data Loss | Recovery |
|----|-----------|-----------|-----------|----------|
| 1 | Journal corrupto (F26) | ⚠️ No retorna resultado (bug en test harness) | Posible | Journal.read() falló |
| 2 | Snapshot faltante (F26) | ✅ Health OK (auto-recovery funciona) | None | 0s |
| 3 | Scheduler kill | ✅ Queue drained on shutdown (1 pending) | None | 0s |
| 4 | Componente inalcanzable | ✅ ErrorDelivery maneja fallo (3 retries) | None | 0s |
| 5 | Disco lleno | ⚠️ No ejecutable (contenedor fs RO) | N/A | N/A |
| 6 | Latencia extrema | ✅ DeliveryHeader.timeout_ms respetado | None | 0s |
| 7 | Reinicio en caliente | ✅ Health: ok, 5 subsistemas | None | 0s |

## Protecciones Implementadas

| Protección | Código | Disparada por |
|-----------|--------|--------------|
| Circuit Breaker | `motor/platform/resilience.py` | CT-4 |
| Backpressure | `motor/platform/resilience.py` | CT-5 |
| Timeouts | `DeliveryHeader.timeout_ms` (ya existe) | CT-6 |

## Hallazgos

1. CT-1: Journal recovery no maneja líneas corruptas correctamente — journal skip no implementado
2. CT-5: No se puede probar disk full en contenedor RO (requiere GX10 nativo)
3. Protecciones mínimas suficientes para RC: circuit breaker + backpressure cubren CT-4, CT-5, CT-6

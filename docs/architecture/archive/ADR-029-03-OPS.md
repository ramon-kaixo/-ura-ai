# ADR-029-03: Operación

**Estado:** Approved
**Fecha:** 2026-07-20
**Fase:** F29 — Bloque B4
**Dependencias:** ADR-029-01 (Observabilidad), ADR-029-02 (Validación)
**Nota:** El contenido preciso de B4 se ajusta según los hallazgos de B2 y B3

---

## Contexto

La plataforma no puede operarse de forma continua:

- **Sin graceful shutdown**: Matar el proceso pierde datos (F26 Journal, F27 cola)
- **Sin health endpoints**: No hay forma de saber si el sistema está vivo
- **Sin backup/restore**: F26 Memory es volátil — un fallo de disco pierde toda la memoria histórica
- **Sin despliegue reproducible**: No hay docker-compose para F24—F28
- **Sin configuración por entorno**: Los mismos valores para dev, staging y prod

---

## Opciones Consideradas

### Opción A: Implementar todo lo posible ahora
- **Ventaja:** Cobertura completa desde el inicio.
- **Desventaja:** Puede implementar cosas que B2/B3 revelen como innecesarias.
- **Veredicto:** ⚠️ Riesgo de sobreingeniería.

### Opción B: Implementar solo lo que B2/B3 revelen como necesario (SELECCIONADA)
- **Razonamiento:** B2 (validación técnica) mostrará cuellos de botella reales. B3 (validación funcional) mostrará qué operaciones importan. Se ajusta el alcance de B4 después de B2/B3.
- **Veredicto:** ✅ Seleccionada.

---

## Decisión

Implementar operaciones en orden de prioridad, ajustando según hallazgos de B2/B3.

### Prioridad Alta (implementar siempre)

| Componente | Acción | Depende de B2/B3 |
|-----------|--------|-----------------|
| Graceful shutdown F26 | Completar `Memory.shutdown(timeout)` | No — siempre necesario |
| Graceful shutdown F27 | Drenar cola + completar ejecuciones activas | No — siempre necesario |
| Health endpoints | `/health`, `/ready`, `/live` en ura-api | No — conectado en B1 |
| Backup F26 script | `backup(path)` + timer diario | No — siempre necesario |
| Restore F26 script | `restore(path)` + verificación checksum | No — siempre necesario |

### Prioridad Media (diseñar ahora, implementar según hallazgos)

| Componente | Acción | Depende de B2/B3 |
|-----------|--------|-----------------|
| Graceful shutdown F24 | Drenar peticiones en curso | Sí — si F24 es cuello de botella |
| Graceful shutdown F25 | Completar fusión actual | Sí — si F25 es cuello de botella |
| docker-compose | Servicios ura-api, ura-memory, prometheus | Sí — saber qué servicios son necesarios |
| Config por entorno | Valores dev/staging/prod | Sí — saber qué varía por entorno |

### Prioridad Baja (puede esperar a versión posterior)

| Componente | Acción |
|-----------|--------|
| docker-compose con Grafana | Se añade después de definir dashboards en B7 |
| Kubernetes manifests | No forma parte de F29 |
| Helm charts | Futuro |

---

## Consecuencias

**Positivas:**
- Operaciones esenciales cubiertas desde el día 1
- Sin sobreingeniería: solo lo necesario
- Backup/restore garantiza que F26 no pierde datos

**Negativas:**
- docker-compose no estará completo hasta después de B2/B3
- La configuración por entorno puede requerir cambios después de B2/B3

**Neutras:**
- F26 ya tiene `shutdown()` implementado (solo verificar cobertura)
- F27 Scheduler ya tiene cola — solo falta drenarla en shutdown

---

## Invariantes

| ID | Invariante | Verificación |
|----|-----------|-------------|
| OP01 | `Memory.shutdown(timeout)` completa todas las escrituras pendientes | Test tras shutdown |
| OP02 | `Scheduler.shutdown(timeout)` drena la cola | Test tras shutdown |
| OP03 | `/health` responde en <100ms | Test HTTP |
| OP04 | `/ready` refleja el estado real de cada subsistema | Test de integración |
| OP05 | Backup de F26 produce archivo con checksum verificable | Test |
| OP06 | Restore de F26 reproduce exactamente el estado respaldado | Test |
| OP07 | Sin cambios en APIs públicas de F24—F27 | Diff de interfaz |

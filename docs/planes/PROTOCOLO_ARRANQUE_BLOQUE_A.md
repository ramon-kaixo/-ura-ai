# PROTOCOLO DE ARRANQUE DEL BLOQUE A — Baseline y Auditoría Real de URA v2.1

_Registrado por WEB (coordinador) el 2026-08-17 a partir de las instrucciones de Ramón._

## Objetivo

Obtener el **baseline real** del repositorio y emitir **hallazgos clasificados P0–P3**
en un máximo de **2 jornadas**. Es la entrada del PLAN DE EJECUCIÓN TÉCNICO v2 (bloques A–F).

## Roles

- **Ejecutor**: TERM — modo auditoría **READ-ONLY** (restricción absoluta, ver abajo).
- **Revisor**: WEB — supervisa, valida evidencia y aprueba hallazgos P0/P1.
- **Aprobador humano**: Ramón — autoriza cualquier modificación.

## Subtareas (todas en PLANNED hasta su turno)

| ID | Subtarea | Contenido |
|----|----------|-----------|
| A0 | Preparación | `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, reporte de cambios sin commitear, referencia de commit para backup. NO modificar nada. |
| A1 | Inventario técnico | Inventario real del repositorio (directorios, módulos, scripts, servicios, configs activos). |
| A2 | Baseline operativo/seguridad | Métricas reales: estado git, secreto/permisos, dependencias, servicios, salud general evidenciada con comandos. |
| A3 | Análisis y priorización | Clasificar hallazgos P0/P1/P2/P3 con evidencia reproducible. |
| A4 | Cierre | Informe consolidado, baseline documentado, veredicto WEB y aprobación Ramón. |

## Restricción absoluta (modo auditoría)

TERM **no puede**: modificar, crear, eliminar, renombrar o mover archivos; modificar
configuración; instalar paquetes; cambiar servicios; modificar `coordination.json`;
modificar UDO; cambiar modelos/providers; realizar migraciones; efectuar commits de código.

Sí puede: inspeccionar, comandos de lectura/diagnóstico, ejecutar tests y herramientas
existentes, medir recursos y generar evidencia de auditoría.

Si encuentra un problema que impida continuar → lo registra y **detiene** esa operación
(no lo corrige). Cualquier modificación requiere autorización **expresa de Ramón**.

## Cierre del bloque (A4)

1. Informe de hallazgos P0–P3 con evidencia reproducible (cada hallazgo cita ruta/línea/comando).
2. Baseline documentado (estado real de repositorio y seguridad).
3. Revisión WEB: hallazgos P0/P1 aprobados/descartados.
4. Aprobación humana de Ramón antes de abrir el Bloque B (hardening).

## Mensaje de lanzamiento para TERM (A0)

Ver anexo: `docs/planes/PROTOCOLO_ARRANQUE_BLOQUE_A.md` (sección anexo, copiada del texto
entregado por Ramón) — listo para pegar en OpenCode Terminal (ASUS).

---

## ANEXO — Mensaje de lanzamiento (texto oficial a pegar en TERM)

```
URA — BLOQUE A — MODO AUDITORÍA

Tu función es realizar una auditoría técnica de solo lectura del repositorio URA.

RESTRICCIÓN ABSOLUTA: no puedes modificar, crear, eliminar, renombrar o mover archivos; modificar configuración; instalar paquetes; cambiar servicios; modificar coordination.json; modificar UDO; cambiar modelos/providers; realizar migraciones; ni efectuar commits de código.

Puedes únicamente inspeccionar, ejecutar comandos de lectura/diagnóstico, ejecutar tests y herramientas existentes, medir recursos y generar evidencia de auditoría.

Si encuentras un problema que impida continuar, regístralo y detén esa operación. No lo corrijas por tu cuenta.

Cualquier modificación requiere autorización expresa de Ramón.

Trabaja sobre la tarea UDO TASK-20260817-014 y sus subtareas A0-A4.

Empieza por A0: Preparación.
- git status --short
- git branch --show-current
- git rev-parse HEAD
- verificar si hay cambios sin commitear (solo reportar)
- crear referencia de commit para backup
- NO modifiques nada.

Devuélveme un resumen de A0 y confirma que puedes continuar con A1.
```
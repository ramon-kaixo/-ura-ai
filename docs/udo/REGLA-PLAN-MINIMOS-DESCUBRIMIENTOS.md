# REGLA PERMANENTE — PLAN, MÍNIMOS Y DESCUBRIMIENTOS

**Fuente:** Directiva de Ramón (2026-08-08) — referencia oficial de esta fase.
**Estado:** Vigente para F3 y fases posteriores. Conservar íntegra en la documentación del proyecto para evitar pérdida de capítulos, requisitos o decisiones.

No elimines, omitas ni sustituyas requisitos del plan sin documentar explícitamente el motivo.

## Clasificación obligatoria por fase

Cada fase debe distinguir obligatoriamente:

### 1. MÍNIMOS OBLIGATORIOS
Requisitos que deben cumplirse necesariamente para poder cerrar la fase.

### 2. MEJORAS O NECESIDADES DESCUBIERTAS
Problemas, requisitos adicionales o mejoras que aparezcan durante la auditoría o implementación.

- Si son **necesarios** para que los mínimos funcionen correctamente → deben incorporarse aunque no estuvieran escritos inicialmente.
- Si son **útiles pero no necesarios** → evaluar si deben implementarse ahora o quedar documentados para una fase posterior.

### 3. FUERA DE ALCANCE / PROHIBIDO
Funcionalidades, arquitectura o cambios que no deben implementarse en esta fase.

## REGLA DE DESCUBRIMIENTO

No te limites a ejecutar literalmente el documento. Después de analizar el código y antes de cerrar la fase, intenta descubrir:

- requisitos que falten;
- casos extremos;
- problemas de seguridad;
- problemas de concurrencia;
- incoherencias;
- dependencias no previstas;
- funcionalidades necesarias para que los mínimos funcionen realmente;
- simplificaciones posibles;
- mejoras de diseño.

- Si descubres algo **necesario** para cumplir correctamente un mínimo → debes resolverlo.
- Si descubres algo **útil pero no necesario** → no lo introduzcas automáticamente si amplía innecesariamente el alcance. Documenta la propuesta y decide si corresponde a esta fase.
- Si descubres algo **fuera de alcance** → NO lo implementes. Regístralo como pendiente para una fase futura.

## REGLA DE CIERRE

Una fase NO puede cerrarse simplemente porque se hayan ejecutado todos los puntos escritos en el plan. Debe cumplir:

- todos los mínimos obligatorios;
- las garantías necesarias para que esos mínimos sean reales;
- las pruebas correspondientes;
- la documentación;
- la auditoría final.

- Si falta algo necesario → la fase permanece **ABIERTA**.
- Si algo del plan resulta incorrecto → no lo implementes ciegamente: analízalo, explica el problema y propone una solución mejor.
- Si encuentras una solución más sencilla que proporciona las mismas garantías → utiliza la solución más sencilla.
- NO utilizar el margen de descubrimiento para introducir sobreingeniería, funcionalidades ajenas al objetivo o infraestructura innecesaria.

## Informe obligatorio al finalizar

Al finalizar, informa separadamente de:

- mínimos cumplidos;
- mínimos pendientes;
- mejoras descubiertas e implementadas;
- mejoras descubiertas y aplazadas;
- elementos fuera de alcance;
- problemas encontrados;
- problemas corregidos;
- riesgos restantes.

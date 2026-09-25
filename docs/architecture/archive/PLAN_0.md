# PLAN 0 — Infraestructura de Ingeniería para Agentes de Programación

**Estado**: ENTREGADO por Ramón — pendiente de auditoría contra infraestructura real (referencia maestra, NO implementar hasta aprobación)
**Fecha**: 2026-08-08
**Veredicto de auditoría**: ver `docs/architecture/PLAN_0_AUDITORIA.md`

---

## 0. Objetivo

Crear una infraestructura de ingeniería que establezca cómo debe trabajar un agente de programación, independientemente de que sea OpenCode Web, OpenCode Terminal o, en el futuro, otra herramienta.

La infraestructura debe conseguir que, cuando se entregue un plan:
NO pase directamente a programar.
Primero debe:
- entender la intención;
- leer todo el plan;
- conocer el contexto;
- inspeccionar el estado real del proyecto;
- revisar documentación y decisiones anteriores;
- buscar problemas;
- buscar cosas que falten;
- buscar contradicciones;
- buscar riesgos;
- buscar casos extremos;
- detectar trabajo prematuro;
- proponer mejoras;
- separar lo obligatorio de lo opcional;
- revisar qué NO debe hacerse;
- devolver su valoración;
- corregir el plan cuando sea necesario;
- y solo después ejecutar.

La finalidad es que el agente no sea un mero ejecutor de instrucciones, sino un ingeniero que analiza antes de actuar.

## 1. Principio rector

La infraestructura debe funcionar así:

```
INTENCIÓN HUMANA
       ↓
PLAN
       ↓
CONTEXTO
       ↓
ANÁLISIS CRÍTICO DEL AGENTE
       ↓
DETECCIÓN DE OMISIONES / RIESGOS / CONTRADICCIONES
       ↓
PROPUESTAS DE MEJORA
       ↓
PLAN REVISADO
       ↓
AUTORIZACIÓN / DECISIÓN
       ↓
EJECUCIÓN
       ↓
REVISIÓN
       ↓
CORRECCIÓN
       ↓
VALIDACIÓN
       ↓
CIERRE
```

La preparación del trabajo forma parte del trabajo de ingeniería.

## 2. La regla más importante

**Un plan nunca debe ejecutarse directamente sin análisis previo.**

Cuando OpenCode recibe un plan debe interpretarlo inicialmente como:
- **propuesta de trabajo pendiente de revisión técnica.**

No como:
- **orden ciega de programación.**

Esto permite que OpenCode utilice el conocimiento que tiene del código real para detectar problemas que no estaban en el plan original.

## 3. Qué debe recibir OpenCode

Un trabajo completo debería proporcionar, cuando exista:

```
PLAN
+
INTENCIÓN
+
CONTEXTO
+
ESTADO ACTUAL
+
OBJETIVO
+
MÍNIMOS
+
PUNTOS CRÍTICOS
+
RESTRICCIONES
+
QUÉ NO HACER
+
VALIDACIÓN
+
CRITERIOS DE CIERRE
```

Si falta información importante, OpenCode debe detectarlo.

## 4. Primera obligación: entender la intención

Antes de analizar la implementación debe determinar:
- qué quiere conseguir el usuario;
- por qué lo quiere;
- qué problema se intenta resolver;
- qué resultado debe existir al terminar;
- qué cosas no forman parte del objetivo.

Debe distinguir:
- **objetivo real** de **método propuesto**.

Esto es importante porque el usuario puede proponer una solución concreta que no sea la mejor forma de conseguir el objetivo.

## 5. Segunda obligación: leer el plan completo

No debe empezar por el primer punto y ejecutar progresivamente sin conocer el resto.
Debe leer:
- todos los capítulos;
- anexos;
- restricciones;
- dependencias;
- mínimos;
- criterios de cierre;
- partes pendientes;
- exclusiones.

Esto evita perder información situada al final del documento.

## 6. Tercera obligación: reconstruir el contexto

Antes de modificar nada debe comprobar el contexto real.
Como mínimo:
- estado de Git;
- arquitectura;
- código relacionado;
- documentación;
- ADRs;
- planes anteriores;
- closeouts;
- decisiones;
- tests;
- configuración;
- dependencias;
- restricciones conocidas.

Si existe una memoria documentada, debe consultarla.

## 7. Memoria

La infraestructura utilizará:
```
Git
+
documentación
+
decisiones
+
planes
+
closeouts
```
como memoria.
No dependerá de:
- conversaciones antiguas;
- memoria implícita del LLM;
- explicaciones verbales;
- información que no esté registrada.

La conversación sirve para interactuar.
La documentación sirve para recordar.

## 8. Cuarta obligación: inspeccionar el código real

OpenCode no puede asumir que el plan describe correctamente el estado del proyecto.
Debe comprobarlo.
Debe preguntarse:
- ¿esto realmente existe?
- ¿está implementado?
- ¿funciona así?
- ¿se usa?
- ¿hay consumidores?
- ¿hay código relacionado?
- ¿existe otra implementación?
- ¿hay restricciones que el plan desconoce?
- ¿la arquitectura actual permite hacerlo como está planteado?

## 9. Quinta obligación: buscar lo que falta

Esta es una obligación, no una sugerencia.
OpenCode debe buscar activamente:
- requisitos ausentes;
- archivos afectados no contemplados;
- tests faltantes;
- documentación faltante;
- casos extremos;
- errores de integración;
- problemas de concurrencia;
- problemas de seguridad;
- problemas operativos;
- incompatibilidades;
- consecuencias sobre otras partes del sistema.

Debe poder responder:
> "El plan dice A, B y C, pero para que A funcione realmente falta D."

## 10. Sexta obligación: buscar contradicciones

Debe comparar:
```
PLAN
vs
CÓDIGO
vs
DOCUMENTACIÓN
vs
DECISIONES ANTERIORES
```
y detectar contradicciones.
Ejemplos:
- el plan dice que una API puede modificarse pero existe un contrato congelado;
- una fase utiliza una funcionalidad que todavía pertenece a otra fase;
- la documentación dice una cosa y el código otra;
- dos decisiones anteriores son incompatibles;
- una reserva contradice otra.

## 11. Séptima obligación: buscar riesgos

Debe analizar al menos:

**Funcionales**: errores; estados imposibles; casos no contemplados.
**Seguridad**: secretos; permisos; bypass; ejecución no autorizada.
**Concurrencia**: carreras; locks; conflictos Web/Terminal; procesos simultáneos.
**Recursos**: memoria; CPU; disco; procesos; conexiones.
**Arquitectura**: acoplamiento; duplicación; nuevas capas innecesarias; deuda técnica.
**Operación**: fallos parciales; recuperación; degradación; reinicios.
**Mantenimiento**: código muerto; complejidad; documentación obsoleta.

## 12. Octava obligación: buscar casos extremos

Debe preguntarse qué ocurre cuando:
- el agente está parado;
- el otro agente está trabajando;
- ambos intentan modificar la misma zona;
- una tarea queda a medias;
- un commit falla;
- una validación falla;
- un proceso desaparece;
- falta configuración;
- falta un secreto;
- el repositorio está sucio;
- se interrumpe el trabajo;
- se reanuda después;
- existe información antigua;
- dos planes se contradicen.

El comportamiento degradado debe formar parte del diseño, no aparecer accidentalmente después.

## 13. Novena obligación: detectar trabajo prematuro

Cada plan debe indicar claramente:
- **FASE ACTUAL**
y qué pertenece a:
- **FASES POSTERIORES**

Si OpenCode descubre trabajo de una fase futura:
- debe señalarlo, pero no implementarlo automáticamente.

Esto corrige específicamente el problema ocurrido con F3 durante F2.

## 14. Décima obligación: buscar mejoras

OpenCode debe preguntarse:
> "¿Existe una forma más sencilla, segura, mantenible o fiable de conseguir exactamente el mismo objetivo?"

Debe poder proponer:
- simplificaciones;
- eliminación de pasos innecesarios;
- reutilización de código existente;
- reducción de complejidad;
- mejoras de validación;
- mejoras de documentación;
- mejoras de seguridad;
- mejoras de trazabilidad.

Pero buscar mejoras no significa ampliar el alcance sin control.

## 15. Clasificación obligatoria de cada descubrimiento

Todo descubrimiento debe clasificarse:

| Clase | Definición |
|-------|------------|
| **OBLIGATORIO** | Sin resolverlo no se puede cumplir el objetivo. |
| **NECESARIO** | No estaba explícito, pero es necesario para que la solución sea correcta. |
| **MEJORA** | Aumenta calidad, pero el objetivo puede cumplirse sin ella. |
| **DESCUBRIMIENTO** | Problema relevante descubierto durante la investigación que debe quedar registrado. |
| **PENDIENTE** | Debe resolverse posteriormente. |
| **FUERA DE ALCANCE** | No debe tocarse ahora. |

Esta clasificación evita que OpenCode convierta cada descubrimiento en trabajo nuevo.

## 16. Mínimos obligatorios

Todo plan tendrá una sección:
**MÍNIMOS OBLIGATORIOS**

Son las condiciones que sí o sí deben cumplirse.
El agente puede hacer más si está autorizado, pero nunca menos.
Si un mínimo no puede cumplirse:
- no puede declarar el trabajo terminado.

## 17. Puntos críticos

Todo plan tendrá:
**PUNTOS CRÍTICOS / INVARIANTES**

Son las cosas que no deben perderse aunque cambie la implementación.
Ejemplos:
- trazabilidad;
- contexto;
- seguridad;
- compatibilidad;
- reversibilidad;
- contratos;
- documentación;
- integridad;
- ausencia de regresiones.

## 18. Comportamiento obligatorio

Todo plan tendrá una sección:
**COMPORTAMIENTO ESPERADO**

No solo describirá qué archivos modificar.
Definirá:
- cómo debe comportarse el sistema después del cambio.

Esto evita planes excesivamente centrados en implementación.

## 19. Qué NO hacer

Todo plan tendrá:
**NO HACER**

Debe especificar:
- qué zonas no tocar;
- qué funcionalidades no implementar;
- qué fases no adelantar;
- qué dependencias no introducir;
- qué decisiones no cambiar;
- qué comportamientos no modificar;
- qué mejoras no están autorizadas.

Además existirán reglas universales permanentes de "NO HACER".

## 20. Regla contra la sobreingeniería

El agente debe buscar la solución:
- más sencilla que cumpla todos los mínimos y puntos críticos.

No debe crear:
- bases de datos;
- servicios;
- APIs;
- capas;
- agentes;
- colas;
- paneles;

si un mecanismo existente resuelve correctamente el problema.
La complejidad debe estar justificada.

## 21. Regla de reutilización

Antes de crear algo nuevo:
- buscar si ya existe;
- comprobar si puede reutilizarse;
- comprobar si puede extenderse;
- comprobar si existe una herramienta estándar del proyecto.

Solo crear algo nuevo cuando esté justificado.

## 22. Revisión del propio plan

Antes de ejecutar, OpenCode debe producir una evaluación:
**ANÁLISIS DEL PLAN**

Como mínimo:
- qué entiendo;
- qué he comprobado;
- qué coincide;
- qué falta;
- qué contradicciones existen;
- qué riesgos existen;
- qué casos extremos existen;
- qué cambiaría;
- qué no tocaría;
- qué es obligatorio;
- qué es opcional;
- qué pertenece a otra fase;
- propuesta de plan corregido;
- valoración final.

## 23. Veredicto previo

Debe terminar con uno de estos:

| Veredicto | Significado |
|-----------|-------------|
| **GO** | El plan es suficientemente sólido para ejecutar. |
| **GO CON CAMBIOS** | Hay modificaciones que deben incorporarse antes. |
| **NO-GO** | Existe un problema que impide ejecutar correctamente. |

No se trata de una autorización automática del agente.
Es una valoración técnica para que Ramón pueda decidir.

## 24. El usuario mantiene la decisión

OpenCode puede:
- analizar;
- cuestionar;
- proponer;
- detectar;
- recomendar.

Pero no debe asumir que una mejora descubierta está automáticamente autorizada.
La autoridad sobre el alcance sigue siendo del coordinador humano.

## 25. Ejecución

Una vez aprobado el plan revisado:

```
PLAN APROBADO
      ↓
RESERVAS
      ↓
EJECUCIÓN
      ↓
COMMITS
      ↓
VALIDACIÓN
```

Durante la ejecución seguirá buscando problemas.

## 26. Problemas descubiertos durante la ejecución

Si aparece algo nuevo:

```
PROBLEMA
   ↓
CLASIFICAR
   ↓
¿BLOQUEA?
   ├── SÍ → resolver / detener
   └── NO
        ↓
¿NECESARIO?
   ├── SÍ → incorporar
   └── NO → documentar
```

No se ignorará.
Pero tampoco se ampliará el proyecto arbitrariamente.

## 27. Alternancia programador/revisor

El modelo de trabajo será:

```
PREPARADOR
    ↓
EJECUTOR
    ↓
REVISOR
    ↓
CORRECCIÓN
    ↓
VALIDACIÓN
```

El ejecutor no debería ser el único que certifique su propio trabajo.

## 28. Roles actuales

Actualmente:

```
OpenCode Web
    ↓
PROGRAMADOR PRINCIPAL

OpenCode Terminal
    ↓
REVISOR
```

Pero estos son roles, no dependencias arquitectónicas.

## 29. Futuro

Cuando desaparezca OpenCode Web:

```
OpenCode Terminal A
    ↓
PROGRAMADOR

OpenCode Terminal B
    ↓
REVISOR
```

Y podrían alternarse:
- A programa, B revisa
- B programa, A revisa

La infraestructura no cambia.

## 30. Regla de contexto entre agentes

Cuando un agente prepara un trabajo para otro, debe transmitir:
- intención;
- plan;
- contexto;
- mínimos;
- puntos críticos;
- restricciones;
- NO HACER;
- archivos afectados;
- reservas;
- estado;
- commits relevantes;
- problemas encontrados;
- decisiones tomadas.

No debe depender de:
> "el otro ya sabe lo que estoy haciendo".

## 31. Archivos que va a tocar

En los trabajos coordinados debe quedar identificado:
**ARCHIVOS / ZONAS DE TRABAJO**

Esto permite que el otro agente sepa qué está ocupado y evita conflictos.
No significa que el agente tenga prohibido tocar cualquier otra cosa bajo cualquier circunstancia: si descubre una dependencia necesaria, debe parar, informar y actualizar el alcance/reserva antes de modificarla.

## 32. Reserva y conflicto

Se mantiene el mecanismo UDO existente.
Regla:
- **detectar un conflicto no equivale a resolverlo.**

Si una zona pertenece al otro agente:
- no tocarla;
- informar;
- esperar;
- o solicitar autorización explícita.

El `--force`, si existe, debe seguir siendo una operación excepcional y auditada.

## 33. Degradación

La infraestructura debe contemplar que un agente pueda estar:
- apagado;
- idle;
- desconectado;
- bloqueado;
- sin credenciales;
- sin acceso;
- sin terminar su trabajo.

No se puede asumir que ambos agentes estarán disponibles siempre.
Si el revisor no está disponible:
- no se debe fingir que la revisión ha ocurrido.

La tarea deberá quedar claramente:
- **PENDIENTE DE REVISIÓN**
o utilizar el procedimiento de revisión alternativa que se defina.

## 34. Trazabilidad

Cada trabajo debe poder reconstruirse posteriormente:

```
PLAN
 ↓
TAREA
 ↓
RESERVA
 ↓
CAMBIOS
 ↓
COMMIT
 ↓
VALIDACIÓN
 ↓
REVISIÓN
 ↓
CIERRE
```

Debe ser posible responder:
- qué se pidió;
- qué se hizo;
- quién lo hizo;
- qué commit produjo;
- quién lo revisó;
- qué pruebas pasaron;
- qué problemas aparecieron;
- qué quedó pendiente.

## 35. Git como fuente de verdad

No crear una base de datos para duplicar:
- tareas;
- commits;
- estados;
- revisiones;
- decisiones.

La información debe permanecer en Git siempre que sea razonable.

## 36. Documentación universal

Crear:

```
docs/engineering/
├── README.md
├── ENGINEERING_PROCESS.md
├── PLAN_TEMPLATE.md
├── PLAN_REVIEW_TEMPLATE.md
└── ROLE_MODEL.md
```

- **ENGINEERING_PROCESS.md**: Explicará todo el ciclo.
- **PLAN_TEMPLATE.md**: Cómo preparar un plan.
- **PLAN_REVIEW_TEMPLATE.md**: Cómo debe analizarlo OpenCode.
- **ROLE_MODEL.md**: Cómo funcionan preparador, ejecutor y revisor.

## 37. Reglas globales de OpenCode

Crear/configurar las reglas globales que recibirán:
- OpenCode Web;
- OpenCode Terminal;
- futuros agentes OpenCode.

La regla universal contendrá principalmente:
- análisis previo;
- búsqueda de omisiones;
- búsqueda de riesgos;
- mínimos;
- críticos;
- NO HACER;
- clasificación de descubrimientos;
- no ejecutar fases futuras;
- trazabilidad;
- revisión;
- honestidad sobre validaciones.

## 38. Reglas específicas de URA

`AGENTS.md` continuará conteniendo las reglas específicas de URA.
No duplicar toda la metodología universal.
Debe decir, esencialmente:
> "Aplicar la metodología universal de ingeniería y, además, estas restricciones específicas de URA."

## 39. Integración desde Terminal

Terminal se utilizará para instalar, configurar y mantener esta metodología en OpenCode.
No necesitamos crear un segundo sistema de agentes.
La idea es:

```
Terminal
   ↓
configura reglas
   ↓
OpenCode Web
OpenCode Terminal
```

La configuración debe ser reproducible.

## 40. Comprobación de que las reglas están instaladas

Crear una comprobación que permita saber:
- qué versión de las reglas está instalada;
- dónde están;
- si existen;
- si están sincronizadas;
- si hay diferencias entre instalaciones.

No debe depender de revisar archivos manualmente.

## 41. No duplicar reglas entre Web y Terminal

Debe existir una fuente única para la metodología universal.
Si se modifica:

```
metodología v1
        ↓
actualización
        ↓
Web + Terminal
```

No:
```
Web = versión A
Terminal = versión B
```

## 42. Versionado

La metodología universal deberá estar versionada.
Ejemplo:
- Engineering Process v1.0

Una modificación importante debe quedar registrada.
Esto permite saber bajo qué metodología se realizó un trabajo.

## 43. Compatibilidad futura

Plan 0 no debe depender de:
- un modelo concreto;
- Qwen;
- OpenCode Web;
- OpenCode Terminal;
- Ollama;
- una máquina concreta.

La metodología debe poder trasladarse.

## 44. Pruebas reales

Antes de cerrar Plan 0 se probarán casos reales:

| Caso | Qué debe ocurrir |
|------|------------------|
| 1 — Plan correcto | Debe identificarlo como ejecutable. |
| 2 — Plan incompleto | Debe detectar lo que falta. |
| 3 — Plan contradictorio | Debe señalar la contradicción. |
| 4 — Plan con una fase posterior | Debe detectar el adelanto. |
| 5 — Plan excesivamente complejo | Debe proponer simplificación. |
| 6 — Plan con requisito oculto | Debe detectarlo al inspeccionar el código. |
| 7 — Agente ejecutor parado | Debe existir comportamiento de degradación. |
| 8 — Conflicto de archivos | Debe detectarse antes de modificar. |
| 9 — Cambio necesario fuera del alcance | Debe detenerse y solicitar actualización. |
| 10 — Mejora opcional | Debe distinguirla de un requisito. |

## 45. Auditoría del Plan 0

Aquí aplicaremos exactamente la nueva metodología que estamos creando.
Antes de implementarlo:
- se entrega este Plan 0 a OpenCode.

OpenCode deberá:
- leerlo entero;
- revisar la configuración real de Web;
- revisar la configuración real de Terminal;
- revisar cómo se cargan actualmente las reglas;
- revisar UDO;
- revisar ura-opencode;
- revisar AGENTS.md;
- comprobar qué existe ya;
- detectar duplicaciones;
- detectar contradicciones;
- detectar mecanismos innecesarios;
- detectar problemas de seguridad;
- detectar problemas de sincronización;
- buscar qué nos hemos dejado;
- proponer simplificaciones;
- proponer mejoras;
- decir qué partes considera obligatorias;
- decir qué partes considera innecesarias;
- entregar un Plan 0 revisado.

No empezará a implementar Plan 0 hasta terminar esta auditoría.

## 46. Regla de mejora continua

La infraestructura tampoco se considera perfecta para siempre.
Después de cada problema importante:

```
PROBLEMA
 ↓
ANÁLISIS
 ↓
¿Es un fallo del proceso?
 ↓
SI
 ↓
mejorar metodología
```

Pero:
- No se modifica la metodología por cualquier incidente aislado.
- Debe existir evidencia de que el cambio aporta valor.

## 47. Lo que queda fuera

Plan 0 NO construirá:
- un sistema distribuido;
- una base de datos;
- un servidor de orquestación;
- un dispatcher;
- un panel;
- una cola;
- un sistema multiagente autónomo;
- una memoria vectorial;
- un nuevo gestor de proyectos;
- un agente auditor permanente;
- infraestructura cloud.

Si alguna de estas cosas se necesita realmente en el futuro, se analizará entonces.

## 48. Criterio de cierre

Plan 0 no se cerrará porque "los archivos existen".
Se cerrará cuando podamos demostrar que:

- OpenCode Web recibe la metodología y la aplica.
- OpenCode Terminal recibe la misma metodología y la aplica.
- Ambos pueden analizar un plan antes de ejecutarlo.
- Ambos pueden detectar omisiones.
- Ambos pueden proponer mejoras.
- Ambos distinguen obligatorio / mejora / pendiente / fuera de alcance.
- Ambos respetan las restricciones.
- Ambos mantienen trazabilidad.
- El sistema funciona aunque Web no esté disponible.
- El sistema funciona si en el futuro hay dos Terminal.

## 49. Secuencia definitiva

No mezclaremos esto con F3.

```
AHORA
  │
  ▼
F3
  │
  ▼
auditoría F3
  │
  ▼
closeout F3
  │
  ▼
árbol limpio
  │
  ▼
PLAN 0
  │
  ▼
OpenCode audita PLAN 0
  │
  ▼
correcciones
  │
  ▼
aprobación
  │
  ▼
implementación
  │
  ▼
pruebas Web
  │
  ▼
pruebas Terminal
  │
  ▼
pruebas coordinadas
  │
  ▼
auditoría final
  │
  ▼
closeout PLAN 0
```

## 50. Regla permanente para todos los planes futuros

A partir de Plan 0, todo plan nuevo deberá responder obligatoriamente a estas preguntas:

**Del plan:**
- ¿QUÉ QUIERO CONSEGUIR?
- ¿POR QUÉ?
- ¿QUÉ CONTEXTO EXISTE?
- ¿QUÉ TIENE QUE HACER?
- ¿QUÉ ES MÍNIMO?
- ¿QUÉ ES CRÍTICO?
- ¿CÓMO DEBE COMPORTARSE?
- ¿QUÉ NO DEBE HACER?
- ¿QUÉ ESTÁ FUERA DE ALCANCE?
- ¿CÓMO SE VALIDARÁ?
- ¿CÓMO SE SABRÁ QUE ESTÁ TERMINADO?

**Y OpenCode añadirá:**
- ¿QUÉ FALTA?
- ¿QUÉ ESTÁ MAL?
- ¿QUÉ CONTRADICCIONES HAY?
- ¿QUÉ RIESGOS EXISTEN?
- ¿QUÉ CASOS EXTREMOS FALTAN?
- ¿QUÉ SE PUEDE SIMPLIFICAR?
- ¿QUÉ SE PUEDE MEJORAR?
- ¿QUÉ NO DEBERÍAMOS HACER?
- ¿QUÉ PERTENECE A OTRA FASE?

## La regla que resume todo

1. El humano define la intención y los límites.
2. El plan define el trabajo propuesto.
3. OpenCode analiza el plan contra la realidad del código.
4. OpenCode detecta lo que falta y propone mejoras.
5. Se fija el plan definitivo.
6. Un agente ejecuta.
7. Otro agente revisa.
8. Git y la documentación conservan la evidencia.
9. Nada se declara terminado sin cumplir los mínimos y poder demostrarlo.

---

*Nota del autor (Ramón, 2026-08-08): este es el Plan 0 que conservaría como referencia maestra. No lo implementaría durante F3. Cuando F3 cierre, se entrega este documento a OpenCode para que primero lo critique contra la infraestructura real, y solo después de incorporar sus hallazgos se ejecuta.*

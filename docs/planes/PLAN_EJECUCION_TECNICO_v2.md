# PLAN DE EJECUCIÓN TÉCNICO v2 — URA

_Registrado por WEB (coordinador) el 2026-08-17 a partir de las instrucciones de Ramón.
Si Ramón dispone del documento maestro completo, este archivo se reemplaza por la versión oficial._

## Estructura: Bloques A–F

| Bloque | Contenido | Secuencia |
|--------|-----------|-----------|
| **A** | Baseline y Auditoría Real de URA v2.1 (A0–A4) | 1º — auditoría |
| **B** | Hardening (post-hallazgos P0/P1) | 2º — hardening |
| **C** | Arquitectura | 3º — arquitectura |
| **D** | Plataforma LLM | 4º — plataforma LLM |
| **E** | Automatización | 5º — automatización |
| **F** | Evolución controlada | 6º — evolución controlada |

## Priorización

- **P0** — crítico: impide operar o riesgo de seguridad/datos → resolución inmediata en bloque B.
- **P1** — alto: degradación funcional o riesgo relevante → resuelve en el bloque correspondiente.
- **P2** — medio: deuda/mantenibilidad → programable.
- **P3** — bajo: mejora/observación → backlog.

## Regla de ejecución

- **NO implementar las 26 fases seguidas.** Trabajar por bloques certificables:
  cada bloque se cierra con hallazgos clasificados, veredicto del revisor (WEB),
  aprobación humana (Ramón) y registro UDO antes de abrir el siguiente.
- Secuencia global: auditoría → hardening → arquitectura → plataforma LLM →
  automatización → evolución controlada.

## Salvaguardas

- RESTRICCIÓN de modo auditoría: solo lectura total hasta autorización expresa de Ramón.
- Toda resolución de hallazgo P0/P1 exige TASK UDO nueva con su plan antes de tocar código.
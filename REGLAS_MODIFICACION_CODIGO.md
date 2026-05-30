# Reglas obligatorias para modificar codigo en URA

## Version 1.0 — Activa desde 13 mayo 2026

## REGLA 1 — Nunca tocar produccion directo

PROHIBIDO modificar archivos en:
- ~/URA/ura_ia_1972/core/
- ~/URA/ura_ia_1972/agents/
- ~/URA/ura_ia_1972/api/
- ~/URA/ura_ia_1972/services/
- ~/URA/ura_ia_1972/handlers/
- ~/URA/ura_ia_1972/ui/
- ~/URA/ura_ia_1972/dashboard/
- ~/URA/ura_ia_1972/gateway/

OBLIGATORIO modificar en:
- ~/URA/sandbox/pendientes/  (en GX10)

## REGLA 2 — Flujo unico de cambio

Para CUALQUIER modificacion:

1. Copiar el archivo a sandbox/pendientes/
2. Modificar SOLO en sandbox
3. agente_sandbox_codigo procesa automatico: tests + ramal + aviso
4. Ramon aprueba/rechaza
5. Solo entonces el cambio entra a produccion

## REGLA 3 — Avisar siempre

Antes de cualquier modificacion:
- Decir a Ramon que se va a tocar
- Esperar confirmacion
- Despues seguir flujo de la REGLA 2

## REGLA 4 — Archivos criticos (aprobacion obligatoria)

Estos archivos NUNCA se modifican sin aprobacion manual:
- core/central_router.py
- core/sandbox_orchestrator.py
- core/forensic_scribe.py
- api/main.py
- core/timeout_manager.py
- core/payment_guardian.py

## REGLA 5 — Cero archivos en el aire

Cada archivo esta en UNO de estos sitios:
- PRODUCCION (Mac, ~/URA/ura_ia_1972/)
- SANDBOX (GX10, ~/URA/sandbox/)
- BACKUP (GX10, ~/URA/backup_versiones/)

NUNCA suelto. NUNCA en /tmp/. NUNCA copia "para probar".

## Para todos los agentes (OpenCode, Windsurf, qwen, etc)

Si vas a modificar codigo:
1. ¿Sabes la regla 1? → No modificar produccion
2. ¿Sabes la regla 2? → Pasa por sandbox
3. ¿Avisaste a Ramon? → REGLA 3

Si la respuesta a alguna es NO → PARA Y AVISA.

## Excepciones

NINGUNA. Sin excepciones.

Si parece urgente → avisa a Ramon.
Si parece pequeño → avisa a Ramon.
Si parece obvio → avisa a Ramon.

Ramon decide.

## Recordatorio constante

Esta regla debe leerse al inicio de cada sesion.
Esta regla debe respetarse hasta que se modifique con aprobacion de Ramon.

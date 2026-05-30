# Propuesta de cambio: Duplicado funcional: agente_creativo_marketing vs agente_lenguaje_creativo

- **ID**: `20260507_193502_creativo-marketing-vs-lenguaje-creativo`
- **Fecha**: 2026-05-07T19:35:02
- **Autor**: ura.coherence_review
- **Tipo**: docs
- **Estado**: ejecutada
- **Validada**: 2026-05-07T19:41:57
- **Ejecutada**: 2026-05-07T19:41:57

## Descripción

## Análisis

**agente_creativo_marketing.py** (876 líneas)
- Clase: `AgenteCreativoMarketing(AgentStabilityBase)`.
- Dependencias: `PIL` (Image, ImageDraw, ImageFont).
- Propósito: GENERACIÓN VISUAL — banners, menús del día, carteles, contenido para redes con paletas de marca.

**agente_lenguaje_creativo.py** (363 líneas)
- Funciones módulo: librería de SINONIMOS, ANTONIMOS, TERMINOS_MARKETING.
- Dependencia: SQLite local.
- Propósito: COPYWRITING — diccionarios para enriquecer textos publicitarios.

## Diagnóstico

**Solapamiento parcial REAL** pero NO duplicación funcional. Comparten dominio "marketing" pero:
- Uno produce imágenes (output visual).
- Otro produce texto (output lingüístico).

Son complementarios.

## Recomendación

**MANTENER AMBOS** con roles diferenciados:
- `agente_creativo_marketing` -> `diseno_visual_marketing`
- `agente_lenguaje_creativo` -> `copywriting_sinonimos_terminos`

Acción opcional posterior (propuesta separada): integrar `lenguaje_creativo` como dependencia interna del `creativo_marketing` para enriquecer copys de banners.

## Riesgos
Ninguno en la separación de intenciones.

## Archivos afectados

- `agents/agente_creativo_marketing.py`
- `agents/agente_lenguaje_creativo.py`

<!--META
{
  "id": "20260507_193502_creativo-marketing-vs-lenguaje-creativo",
  "titulo": "Duplicado funcional: agente_creativo_marketing vs agente_lenguaje_creativo",
  "descripcion": "## Análisis\n\n**agente_creativo_marketing.py** (876 líneas)\n- Clase: `AgenteCreativoMarketing(AgentStabilityBase)`.\n- Dependencias: `PIL` (Image, ImageDraw, ImageFont).\n- Propósito: GENERACIÓN VISUAL — banners, menús del día, carteles, contenido para redes con paletas de marca.\n\n**agente_lenguaje_creativo.py** (363 líneas)\n- Funciones módulo: librería de SINONIMOS, ANTONIMOS, TERMINOS_MARKETING.\n- Dependencia: SQLite local.\n- Propósito: COPYWRITING — diccionarios para enriquecer textos publicitarios.\n\n## Diagnóstico\n\n**Solapamiento parcial REAL** pero NO duplicación funcional. Comparten dominio \"marketing\" pero:\n- Uno produce imágenes (output visual).\n- Otro produce texto (output lingüístico).\n\nSon complementarios.\n\n## Recomendación\n\n**MANTENER AMBOS** con roles diferenciados:\n- `agente_creativo_marketing` -> `diseno_visual_marketing`\n- `agente_lenguaje_creativo` -> `copywriting_sinonimos_terminos`\n\nAcción opcional posterior (propuesta separada): integrar `lenguaje_creativo` como dependencia interna del `creativo_marketing` para enriquecer copys de banners.\n\n## Riesgos\nNinguno en la separación de intenciones.",
  "archivos_afectados": [
    "agents/agente_creativo_marketing.py",
    "agents/agente_lenguaje_creativo.py"
  ],
  "tipo": "docs",
  "autor": "ura.coherence_review",
  "fecha_creacion": "2026-05-07T19:35:02",
  "estado": "ejecutada",
  "motivo_rechazo": "",
  "fecha_validacion": "2026-05-07T19:41:57",
  "fecha_ejecucion": "2026-05-07T19:41:57",
  "ejecutor_cambios": [
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_creativo_marketing.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_creativo_marketing.py/agente_creativo_marketing.v002.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_lenguaje_creativo.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_lenguaje_creativo.py/agente_lenguaje_creativo.v001.py"
    }
  ]
}
-->

# Propuesta de cambio: Falso duplicado funcional: grupo agente_documentos_* (5 agentes)

- **ID**: `20260507_193503_grupo-documentos-5-agentes`
- **Fecha**: 2026-05-07T19:35:03
- **Autor**: ura.coherence_review
- **Tipo**: docs
- **Estado**: ejecutada
- **Validada**: 2026-05-07T19:41:57
- **Ejecutada**: 2026-05-07T19:41:57

## Descripción

## Análisis

Cinco agentes con la MISMA arquitectura (escanear + indexar + persistir en `board.db`) pero apuntando a FORMATOS DISTINTOS:

| Agente | Extensiones | Carpeta biblioteca |
|--------|-------------|--------------------|
| `agente_documentos_excel` | `.xlsx, .xls, .csv` | `biblioteca/excel` |
| `agente_documentos_pdf` | `.pdf` | `biblioteca/pdf` |
| `agente_documentos_presentaciones` | `.ppt, .pptx, .odp` | `biblioteca/presentaciones` |
| `agente_documentos_texto` | `.txt, .md, .rtf, .log, .json, .xml, .yaml` | `biblioteca/texto` |
| `agente_documentos_word` | `.doc, .docx, .odt` | `biblioteca/word` |

Existe `agents/agente_orquestador_documentacion.py` que ya los coordina.

## Diagnóstico

**Falso positivo.** La separación por formato es DELIBERADA y correcta.

## Recomendación

**MANTENER LOS 5 SEPARADOS.** Refinar intenciones por formato:
- `agente_documentos_excel` -> `gestion_excel`
- `agente_documentos_pdf` -> `gestion_pdf`
- `agente_documentos_presentaciones` -> `gestion_presentaciones`
- `agente_documentos_texto` -> `gestion_texto_plano`
- `agente_documentos_word` -> `gestion_word`

## Alternativa descartada

Refactorizar a un único `agente_documentos` con dispatcher por extensión:
- Pros: menos archivos, lógica centralizada.
- Contras: rompe orquestador, mezcla parsers, dificulta tests aislados.
- **NO RECOMENDADO**.

## Riesgos
Ninguno. Solo cambio metadata.

## Archivos afectados

- `agents/agente_documentos_excel.py`
- `agents/agente_documentos_pdf.py`
- `agents/agente_documentos_presentaciones.py`
- `agents/agente_documentos_texto.py`
- `agents/agente_documentos_word.py`

<!--META
{
  "id": "20260507_193503_grupo-documentos-5-agentes",
  "titulo": "Falso duplicado funcional: grupo agente_documentos_* (5 agentes)",
  "descripcion": "## Análisis\n\nCinco agentes con la MISMA arquitectura (escanear + indexar + persistir en `board.db`) pero apuntando a FORMATOS DISTINTOS:\n\n| Agente | Extensiones | Carpeta biblioteca |\n|--------|-------------|--------------------|\n| `agente_documentos_excel` | `.xlsx, .xls, .csv` | `biblioteca/excel` |\n| `agente_documentos_pdf` | `.pdf` | `biblioteca/pdf` |\n| `agente_documentos_presentaciones` | `.ppt, .pptx, .odp` | `biblioteca/presentaciones` |\n| `agente_documentos_texto` | `.txt, .md, .rtf, .log, .json, .xml, .yaml` | `biblioteca/texto` |\n| `agente_documentos_word` | `.doc, .docx, .odt` | `biblioteca/word` |\n\nExiste `agents/agente_orquestador_documentacion.py` que ya los coordina.\n\n## Diagnóstico\n\n**Falso positivo.** La separación por formato es DELIBERADA y correcta.\n\n## Recomendación\n\n**MANTENER LOS 5 SEPARADOS.** Refinar intenciones por formato:\n- `agente_documentos_excel` -> `gestion_excel`\n- `agente_documentos_pdf` -> `gestion_pdf`\n- `agente_documentos_presentaciones` -> `gestion_presentaciones`\n- `agente_documentos_texto` -> `gestion_texto_plano`\n- `agente_documentos_word` -> `gestion_word`\n\n## Alternativa descartada\n\nRefactorizar a un único `agente_documentos` con dispatcher por extensión:\n- Pros: menos archivos, lógica centralizada.\n- Contras: rompe orquestador, mezcla parsers, dificulta tests aislados.\n- **NO RECOMENDADO**.\n\n## Riesgos\nNinguno. Solo cambio metadata.",
  "archivos_afectados": [
    "agents/agente_documentos_excel.py",
    "agents/agente_documentos_pdf.py",
    "agents/agente_documentos_presentaciones.py",
    "agents/agente_documentos_texto.py",
    "agents/agente_documentos_word.py"
  ],
  "tipo": "docs",
  "autor": "ura.coherence_review",
  "fecha_creacion": "2026-05-07T19:35:03",
  "estado": "ejecutada",
  "motivo_rechazo": "",
  "fecha_validacion": "2026-05-07T19:41:57",
  "fecha_ejecucion": "2026-05-07T19:41:57",
  "ejecutor_cambios": [
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_documentos_excel.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_documentos_excel.py/agente_documentos_excel.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_documentos_pdf.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_documentos_pdf.py/agente_documentos_pdf.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_documentos_presentaciones.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_documentos_presentaciones.py/agente_documentos_presentaciones.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_documentos_texto.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_documentos_texto.py/agente_documentos_texto.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_documentos_word.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_documentos_word.py/agente_documentos_word.v001.py"
    }
  ]
}
-->

# Propuesta de cambio: Duplicado funcional: agente_automatizacion vs agente_automatizador

- **ID**: `20260507_193501_automatizacion-vs-automatizador`
- **Fecha**: 2026-05-07T19:35:01
- **Autor**: ura.coherence_review
- **Tipo**: docs
- **Estado**: ejecutada
- **Validada**: 2026-05-07T19:41:57
- **Ejecutada**: 2026-05-07T19:41:57

## Descripción

## Análisis

**agente_automatizacion.py**
- Funciones módulo: `mover_mouse`, `click`, `escribir`, `presionar_tecla`, `combinacion`, `buscar_en_pantalla`.
- Dependencia: `pyautogui` (control nativo de mouse/teclado).
- Propósito: AUTOMATIZACIÓN LOW-LEVEL de input del sistema operativo.

**agente_automatizador.py**
- Clase: `AgenteAutomatizador` con método `automatizar_tarea(descripcion)`.
- Dependencias internas: `core.repetition_detector`, `core.n8n_workflow_builder`.
- Propósito: AUTOMATIZACIÓN HIGH-LEVEL — recibe lenguaje natural y construye workflows n8n.

## Diagnóstico

**Falso positivo.** Son dos capas distintas:
- Una opera sobre el OS (mouse/teclado).
- La otra orquesta workflows externos (n8n).

## Recomendación

**MANTENER AMBOS**. Refinar heurísticas:
- `agente_automatizacion` -> `automatizacion_input_nativo`
- `agente_automatizador` -> `automatizacion_workflows_n8n`

## Riesgos
Ninguno. Cambio metadata.

## Archivos afectados

- `agents/agente_automatizacion.py`
- `agents/agente_automatizador.py`

<!--META
{
  "id": "20260507_193501_automatizacion-vs-automatizador",
  "titulo": "Duplicado funcional: agente_automatizacion vs agente_automatizador",
  "descripcion": "## Análisis\n\n**agente_automatizacion.py**\n- Funciones módulo: `mover_mouse`, `click`, `escribir`, `presionar_tecla`, `combinacion`, `buscar_en_pantalla`.\n- Dependencia: `pyautogui` (control nativo de mouse/teclado).\n- Propósito: AUTOMATIZACIÓN LOW-LEVEL de input del sistema operativo.\n\n**agente_automatizador.py**\n- Clase: `AgenteAutomatizador` con método `automatizar_tarea(descripcion)`.\n- Dependencias internas: `core.repetition_detector`, `core.n8n_workflow_builder`.\n- Propósito: AUTOMATIZACIÓN HIGH-LEVEL — recibe lenguaje natural y construye workflows n8n.\n\n## Diagnóstico\n\n**Falso positivo.** Son dos capas distintas:\n- Una opera sobre el OS (mouse/teclado).\n- La otra orquesta workflows externos (n8n).\n\n## Recomendación\n\n**MANTENER AMBOS**. Refinar heurísticas:\n- `agente_automatizacion` -> `automatizacion_input_nativo`\n- `agente_automatizador` -> `automatizacion_workflows_n8n`\n\n## Riesgos\nNinguno. Cambio metadata.",
  "archivos_afectados": [
    "agents/agente_automatizacion.py",
    "agents/agente_automatizador.py"
  ],
  "tipo": "docs",
  "autor": "ura.coherence_review",
  "fecha_creacion": "2026-05-07T19:35:01",
  "estado": "ejecutada",
  "motivo_rechazo": "",
  "fecha_validacion": "2026-05-07T19:41:57",
  "fecha_ejecucion": "2026-05-07T19:41:57",
  "ejecutor_cambios": [
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_automatizacion.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_automatizacion.py/agente_automatizacion.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_automatizador.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_automatizador.py/agente_automatizador.v001.py"
    }
  ]
}
-->

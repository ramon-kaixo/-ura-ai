# Propuesta de cambio: Reparar agentes rotos: indentación de wrappers procesar/ejecutar/consultar/responder

- **ID**: `20260507_165916_reparar-agentes-rotos-indentaci-n-de-wra`
- **Fecha**: 2026-05-07T16:59:16
- **Autor**: ura.maintenance
- **Tipo**: bugfix
- **Estado**: ejecutada
- **Validada**: 2026-05-07T16:59:16
- **Ejecutada**: 2026-05-07T16:59:16

## Descripción

El catálogo URA detectó dos agentes en estado 'roto' por SyntaxError. Ambos comparten el mismo patrón de indentación incorrecta en los métodos wrapper auto-generados (procesar, ejecutar, consultar, responder, get_agent_capabilities). El cuerpo de procesar tiene 4 espacios cuando debería tener 8, y los siguientes def están a nivel módulo en lugar de dentro de la clase. Esta propuesta los re-indenta correctamente y rellena el cuerpo vacío de responder con `return self.procesar(texto)`. Los archivos originales se mueven a la papelera del Toshiba antes de aplicar.

## Archivos afectados

- `agents/agente_administrativo_contable.py`
- `agents/agente_creativo_marketing.py`

<!--META
{
  "id": "20260507_165916_reparar-agentes-rotos-indentaci-n-de-wra",
  "titulo": "Reparar agentes rotos: indentación de wrappers procesar/ejecutar/consultar/responder",
  "descripcion": "El catálogo URA detectó dos agentes en estado 'roto' por SyntaxError. Ambos comparten el mismo patrón de indentación incorrecta en los métodos wrapper auto-generados (procesar, ejecutar, consultar, responder, get_agent_capabilities). El cuerpo de procesar tiene 4 espacios cuando debería tener 8, y los siguientes def están a nivel módulo en lugar de dentro de la clase. Esta propuesta los re-indenta correctamente y rellena el cuerpo vacío de responder con `return self.procesar(texto)`. Los archivos originales se mueven a la papelera del Toshiba antes de aplicar.",
  "archivos_afectados": [
    "agents/agente_administrativo_contable.py",
    "agents/agente_creativo_marketing.py"
  ],
  "tipo": "bugfix",
  "autor": "ura.maintenance",
  "fecha_creacion": "2026-05-07T16:59:16",
  "estado": "ejecutada",
  "motivo_rechazo": "",
  "fecha_validacion": "2026-05-07T16:59:16",
  "fecha_ejecucion": "2026-05-07T16:59:16",
  "ejecutor_cambios": [
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_administrativo_contable.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_administrativo_contable.py/agente_administrativo_contable.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_creativo_marketing.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_creativo_marketing.py/agente_creativo_marketing.v001.py"
    },
    {
      "accion": "reescribir_archivo",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_administrativo_contable.py",
      "papelera": ""
    },
    {
      "accion": "reescribir_archivo",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_creativo_marketing.py",
      "papelera": ""
    }
  ]
}
-->

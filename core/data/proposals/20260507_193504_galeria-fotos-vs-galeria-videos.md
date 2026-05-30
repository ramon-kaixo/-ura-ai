# Propuesta de cambio: Falso duplicado funcional: agente_galeria_fotos vs agente_galeria_videos

- **ID**: `20260507_193504_galeria-fotos-vs-galeria-videos`
- **Fecha**: 2026-05-07T19:35:04
- **Autor**: ura.coherence_review
- **Tipo**: docs
- **Estado**: ejecutada
- **Validada**: 2026-05-07T19:41:57
- **Ejecutada**: 2026-05-07T19:41:57

## Descripción

## Análisis

**agente_galeria_fotos.py**
- Funciones: `escanear_fotos`, `indexar_foto`, `obtener_metadatos`.
- Extensiones: `.jpg, .jpeg, .png, .gif, .webp, .heic, .tiff, .bmp`.
- Carpeta: `biblioteca/galeria`.

**agente_galeria_videos.py**
- Funciones: `escanear_videos`, `indexar_video`, `obtener_metadatos`.
- Extensiones: `.mp4, .mov, .avi, .mkv, .webm, .m4v, .wmv`.
- Carpeta: `biblioteca/videos`.

## Diagnóstico

**Falso positivo.** Misma estructura, propósitos análogos pero SOBRE TIPOS DE MEDIA DISTINTOS.

## Recomendación

**MANTENER AMBOS SEPARADOS.** Refinar intenciones:
- `agente_galeria_fotos` -> `gestion_fotos`
- `agente_galeria_videos` -> `gestion_videos`

## Riesgos
Ninguno.

## Archivos afectados

- `agents/agente_galeria_fotos.py`
- `agents/agente_galeria_videos.py`

<!--META
{
  "id": "20260507_193504_galeria-fotos-vs-galeria-videos",
  "titulo": "Falso duplicado funcional: agente_galeria_fotos vs agente_galeria_videos",
  "descripcion": "## Análisis\n\n**agente_galeria_fotos.py**\n- Funciones: `escanear_fotos`, `indexar_foto`, `obtener_metadatos`.\n- Extensiones: `.jpg, .jpeg, .png, .gif, .webp, .heic, .tiff, .bmp`.\n- Carpeta: `biblioteca/galeria`.\n\n**agente_galeria_videos.py**\n- Funciones: `escanear_videos`, `indexar_video`, `obtener_metadatos`.\n- Extensiones: `.mp4, .mov, .avi, .mkv, .webm, .m4v, .wmv`.\n- Carpeta: `biblioteca/videos`.\n\n## Diagnóstico\n\n**Falso positivo.** Misma estructura, propósitos análogos pero SOBRE TIPOS DE MEDIA DISTINTOS.\n\n## Recomendación\n\n**MANTENER AMBOS SEPARADOS.** Refinar intenciones:\n- `agente_galeria_fotos` -> `gestion_fotos`\n- `agente_galeria_videos` -> `gestion_videos`\n\n## Riesgos\nNinguno.",
  "archivos_afectados": [
    "agents/agente_galeria_fotos.py",
    "agents/agente_galeria_videos.py"
  ],
  "tipo": "docs",
  "autor": "ura.coherence_review",
  "fecha_creacion": "2026-05-07T19:35:04",
  "estado": "ejecutada",
  "motivo_rechazo": "",
  "fecha_validacion": "2026-05-07T19:41:57",
  "fecha_ejecucion": "2026-05-07T19:41:57",
  "ejecutor_cambios": [
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_galeria_fotos.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_galeria_fotos.py/agente_galeria_fotos.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_galeria_videos.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_galeria_videos.py/agente_galeria_videos.v001.py"
    }
  ]
}
-->

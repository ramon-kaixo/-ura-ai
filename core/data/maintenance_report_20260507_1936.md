# Informe de mantenimiento — 2026-05-07T19:36:47

- **Modo conservación**: ACTIVADO
- **Duración**: 2.639 s
- **Fin**: 2026-05-07T19:36:49

## 0. Catálogo URA (AgenteDocumentador)

- Ruta: `/Users/ramonesnaola/URA/ura_ia_1972/core/data/catalogo_ura.json`
- Agentes catalogados: **78**
- Módulos catalogados: **298**
- Aplicaciones detectadas: 4
- Screens documentados: 2
- Problemas de coherencia: 0
- Duplicados funcionales: 5

## 1. Propuestas ejecutadas

- Aprobadas encontradas: 0
- Ejecutadas: 0
- Fallidas: 0

## 2. ChangeLogger

- Momento anterior: 2026-05-07T16:59:00
- Cambios detectados: 2

## 3. Auditoría de coherencia

- Hallazgos totales: **5**
  - Errores: 0
  - Warnings: 5
  - Infos: 0

- Papelera (/Volumes/TOSHIBA_NUEVO/URA_papelera):
  - Archivos distintos: 2
  - Versiones totales: 2

### Propuestas pendientes/aprobadas

- `agents/agente_auditor.py`
- `agents/agente_auditor_externo.py`
- `agents/agente_automatizacion.py`
- `agents/agente_automatizador.py`
- `agents/agente_creativo_marketing.py`
- `agents/agente_documentos_excel.py`
- `agents/agente_documentos_pdf.py`
- `agents/agente_documentos_presentaciones.py`
- `agents/agente_documentos_texto.py`
- `agents/agente_documentos_word.py`
- `agents/agente_galeria_fotos.py`
- `agents/agente_galeria_videos.py`
- `agents/agente_lenguaje_creativo.py`

### Hallazgos destacados

- [WARNING] `agente_auditor, agente_auditor_externo` — Varios agentes comparten intención 'auditoria': ['agente_auditor', 'agente_auditor_externo'] (catalogo:duplicado_funcional)
- [WARNING] `agente_automatizacion, agente_automatizador` — Varios agentes comparten intención 'automatizacion': ['agente_automatizacion', 'agente_automatizador'] (catalogo:duplicado_funcional)
- [WARNING] `agente_creativo_marketing, agente_lenguaje_creativo` — Varios agentes comparten intención 'generacion_contenido': ['agente_creativo_marketing', 'agente_lenguaje_creativo'] (catalogo:duplicado_funcional)
- [WARNING] `agente_documentos_excel, agente_documentos_pdf, agente_documentos_presentaciones, agente_documentos_texto, agente_documentos_word` — Varios agentes comparten intención 'gestion_documental': ['agente_documentos_excel', 'agente_documentos_pdf', 'agente_documentos_presentaciones', 'agente_documentos_texto', 'agente_documentos_word'] (catalogo:duplicado_funcional)
- [WARNING] `agente_galeria_fotos, agente_galeria_videos` — Varios agentes comparten intención 'gestion_imagenes': ['agente_galeria_fotos', 'agente_galeria_videos'] (catalogo:duplicado_funcional)

## 4. Rotación de papelera

- Modo conservación: ACTIVADO (no se rota nada)
- MAX_VERSIONS: 10
- Rotados en este ciclo: 0

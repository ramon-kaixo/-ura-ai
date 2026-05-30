# Informe de mantenimiento — 2026-05-07T16:51:46

- **Modo conservación**: ACTIVADO
- **Duración**: 1.873 s
- **Fin**: 2026-05-07T16:51:48

## 0. Catálogo URA (AgenteDocumentador)

- Ruta: `/Users/ramonesnaola/URA/ura_ia_1972/core/data/catalogo_ura.json`
- Agentes catalogados: **78**
- Módulos catalogados: **297**
- Aplicaciones detectadas: 4
- Screens documentados: 2
- Problemas de coherencia: 2
- Duplicados funcionales: 5

## 1. Propuestas ejecutadas

- Aprobadas encontradas: 0
- Ejecutadas: 0
- Fallidas: 0

## 2. ChangeLogger

- Momento anterior: 2026-05-07T16:49:00
- Cambios detectados: 0

## 3. Auditoría de coherencia

- Hallazgos totales: **9**
  - Errores: 4
  - Warnings: 5
  - Infos: 0

- Papelera (/Volumes/TOSHIBA_NUEVO/URA_papelera):
  - Archivos distintos: 0
  - Versiones totales: 0

### Propuestas pendientes/aprobadas

- _(ninguna)_

### Hallazgos destacados

- [ERROR] `agents/agente_administrativo_contable.py` — SyntaxError: expected an indented block after function definition on line 51 (línea 52) (sintaxis)
- [ERROR] `agents/agente_creativo_marketing.py` — SyntaxError: expected an indented block after function definition on line 280 (línea 281) (sintaxis)
- [ERROR] `agents/agente_administrativo_contable.py` — Catálogo: agente_roto en agente 'agente_administrativo_contable' (catalogo:agente_roto)
- [ERROR] `agents/agente_creativo_marketing.py` — Catálogo: agente_roto en agente 'agente_creativo_marketing' (catalogo:agente_roto)
- [WARNING] `agente_auditor, agente_auditor_externo` — Varios agentes comparten intención 'auditoria': ['agente_auditor', 'agente_auditor_externo'] (catalogo:duplicado_funcional)
- [WARNING] `agente_automatizacion, agente_automatizador` — Varios agentes comparten intención 'automatizacion': ['agente_automatizacion', 'agente_automatizador'] (catalogo:duplicado_funcional)
- [WARNING] `agente_creativo_marketing, agente_lenguaje_creativo` — Varios agentes comparten intención 'generacion_contenido': ['agente_creativo_marketing', 'agente_lenguaje_creativo'] (catalogo:duplicado_funcional)
- [WARNING] `agente_documentos_excel, agente_documentos_pdf, agente_documentos_presentaciones, agente_documentos_texto, agente_documentos_word` — Varios agentes comparten intención 'gestion_documental': ['agente_documentos_excel', 'agente_documentos_pdf', 'agente_documentos_presentaciones', 'agente_documentos_texto', 'agente_documentos_word'] (catalogo:duplicado_funcional)
- [WARNING] `agente_galeria_fotos, agente_galeria_videos` — Varios agentes comparten intención 'gestion_imagenes': ['agente_galeria_fotos', 'agente_galeria_videos'] (catalogo:duplicado_funcional)

## 4. Rotación de papelera

- Modo conservación: ACTIVADO (no se rota nada)
- MAX_VERSIONS: 10
- Rotados en este ciclo: 0

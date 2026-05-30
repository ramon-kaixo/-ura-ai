# URA — Registro de problemas

Cada entrada documenta: fecha, síntoma, causa raíz, solución aplicada y si
funcionó. Si un mismo síntoma aparece dos veces, la entrada anterior es de
**lectura obligatoria** antes de proponer nada nuevo (REGLA 9).

---

## 2026-05-07 16:59 — Duplicados funcionales en el catálogo URA

**Síntoma**
El paso 0 del ciclo de mantenimiento (`AgenteDocumentador`) reporta 5 grupos
de agentes con la misma intención. El `CoherenceAuditor` los emite como
`WARNING` con categoría `catalogo:duplicado_funcional`.

**Grupos detectados**

| Intención inferida | Agentes implicados | ¿Falso positivo? |
|---|---|---|
| `auditoria` | `agente_auditor`, `agente_auditor_externo` | A revisar — posiblemente roles distintos |
| `automatizacion` | `agente_automatizacion`, `agente_automatizador` | Probable typo histórico, uno sobra |
| `generacion_contenido` | `agente_creativo_marketing`, `agente_lenguaje_creativo` | Solapamiento real, candidato a fusión |
| `gestion_documental` | `agente_documentos_excel`, `agente_documentos_pdf`, `agente_documentos_presentaciones`, `agente_documentos_texto`, `agente_documentos_word` | Falso positivo — separados por formato; ya hay `agente_orquestador_documentacion` que los coordina |
| `gestion_imagenes` | `agente_galeria_fotos`, `agente_galeria_videos` | Falso positivo — uno es fotos, otro es vídeo |

**Causa raíz**
Las heurísticas de intención en `core/agente_documentador.py` (constante
`_INTENT_KEYWORDS`) usan keywords muy genéricas (`documentos` →
`gestion_documental`, `galeria` → `gestion_imagenes`). Esto agrupa agentes
que en realidad están separados por formato/tipo de contenido.

**Decisión**
Mantener los warnings sin actuar. No son bugs — solo señales para revisar
más adelante.

**Solución aplicada**
Ninguna por ahora. Documentado aquí para no olvidarlo.

**¿Funcionó?**
N/A (decisión aplazada).

**Próxima acción si vuelve a aparecer**
Si en una revisión futura este síntoma persiste, las opciones son:
1. Refinar `_INTENT_KEYWORDS` para añadir granularidad por formato
   (`documentos_excel` → `gestion_excel`, `galeria_fotos` → `gestion_fotos`,
   etc.). Eliminaría 2 de los 5 grupos como falsos positivos.
2. Crear propuestas individuales para los 3 grupos reales
   (`auditor/auditor_externo`, `automatizacion/automatizador`,
   `creativo_marketing/lenguaje_creativo`) con análisis de fusión, renombrado
   o mantenimiento por separado.

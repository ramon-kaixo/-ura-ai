# Propuesta de cambio: Duplicado funcional: agente_auditor vs agente_auditor_externo

- **ID**: `20260507_193500_auditor-vs-auditor-externo`
- **Fecha**: 2026-05-07T19:35:00
- **Autor**: ura.coherence_review
- **Tipo**: docs
- **Estado**: ejecutada
- **Validada**: 2026-05-07T19:41:57
- **Ejecutada**: 2026-05-07T19:41:57

## Descripción

## Análisis

**agente_auditor.py** (183 líneas)
- Funciones módulo (sin clase): `registrar_accion`, `listar_auditoria`.
- Persistencia: SQLite local en `board.db` tabla `auditoria`.
- Propósito real: REGISTRO INTERNO de acciones del propio sistema URA con su motivo.

**agente_auditor_externo.py** (269 líneas)
- Funciones módulo (sin clase): `buscar_en_github`, `trending_github`, `guardar_auditoria_externa`.
- Dependencias externas: `urllib.request` (GitHub API, Reddit, HN).
- Persistencia: SQLite local en `board.db`.
- Propósito real: AUDITORÍA EXTERNA de plataformas (tendencias, repos, news).

## Diagnóstico

**Falso positivo.** Los dos agentes tienen propósitos opuestos. Comparten la palabra "auditor" en el nombre, lo que hace que la heurística `_INTENT_KEYWORDS["auditor"] = "auditoria"` los agrupe. En realidad son complementarios y necesarios ambos.

## Recomendación

**MANTENER AMBOS**. Refinar heurísticas en `core/agente_documentador.py`:
- `agente_auditor` -> intención `auditoria_interna_acciones`
- `agente_auditor_externo` -> intención `auditoria_externa_plataformas`

Esto eliminaría el warning del catálogo sin tocar los agentes.

## Riesgos
Ninguno. Cambio puramente metadata; no afecta funcionalidad.

## Archivos afectados

- `agents/agente_auditor.py`
- `agents/agente_auditor_externo.py`

<!--META
{
  "id": "20260507_193500_auditor-vs-auditor-externo",
  "titulo": "Duplicado funcional: agente_auditor vs agente_auditor_externo",
  "descripcion": "## Análisis\n\n**agente_auditor.py** (183 líneas)\n- Funciones módulo (sin clase): `registrar_accion`, `listar_auditoria`.\n- Persistencia: SQLite local en `board.db` tabla `auditoria`.\n- Propósito real: REGISTRO INTERNO de acciones del propio sistema URA con su motivo.\n\n**agente_auditor_externo.py** (269 líneas)\n- Funciones módulo (sin clase): `buscar_en_github`, `trending_github`, `guardar_auditoria_externa`.\n- Dependencias externas: `urllib.request` (GitHub API, Reddit, HN).\n- Persistencia: SQLite local en `board.db`.\n- Propósito real: AUDITORÍA EXTERNA de plataformas (tendencias, repos, news).\n\n## Diagnóstico\n\n**Falso positivo.** Los dos agentes tienen propósitos opuestos. Comparten la palabra \"auditor\" en el nombre, lo que hace que la heurística `_INTENT_KEYWORDS[\"auditor\"] = \"auditoria\"` los agrupe. En realidad son complementarios y necesarios ambos.\n\n## Recomendación\n\n**MANTENER AMBOS**. Refinar heurísticas en `core/agente_documentador.py`:\n- `agente_auditor` -> intención `auditoria_interna_acciones`\n- `agente_auditor_externo` -> intención `auditoria_externa_plataformas`\n\nEsto eliminaría el warning del catálogo sin tocar los agentes.\n\n## Riesgos\nNinguno. Cambio puramente metadata; no afecta funcionalidad.",
  "archivos_afectados": [
    "agents/agente_auditor.py",
    "agents/agente_auditor_externo.py"
  ],
  "tipo": "docs",
  "autor": "ura.coherence_review",
  "fecha_creacion": "2026-05-07T19:35:00",
  "estado": "ejecutada",
  "motivo_rechazo": "",
  "fecha_validacion": "2026-05-07T19:41:57",
  "fecha_ejecucion": "2026-05-07T19:41:57",
  "ejecutor_cambios": [
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_auditor.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_auditor.py/agente_auditor.v001.py"
    },
    {
      "accion": "backup_papelera",
      "archivo": "/Users/ramonesnaola/URA/ura_ia_1972/agents/agente_auditor_externo.py",
      "papelera": "/Volumes/TOSHIBA_NUEVO/URA_papelera/agents/agente_auditor_externo.py/agente_auditor_externo.v001.py"
    }
  ]
}
-->

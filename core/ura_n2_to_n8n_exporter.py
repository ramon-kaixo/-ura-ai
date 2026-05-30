#!/usr/bin/env python3
"""
URA N2 → n8n Exporter — N2 Infrastructure (Esqueleto, Fase 4)

Esqueleto para exportar una maleta madura como workflow de n8n (N1 automático).
La lógica interna se implementará en Fase 4 cuando se haya alcanzado el umbral
de maduración real (confianza ≥ 0.95 y 20+ usos).

Contrato externo (firmas) definido para que otros módulos puedan referenciarlo
sin esperar a la implementación final.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("ura_n2_to_n8n_exporter")


@dataclass
class N8nExportResult:
    """Resultado de una exportación a n8n."""

    ok: bool
    workflow_id: str | None = None
    workflow_json_path: Path | None = None
    detalles: dict[str, Any] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)


class N2ToN8nExporter:
    """
    Esqueleto de exportador de maletas N2 → workflows n8n (N1).

    Fase 4 implementará:
      - Traducción de la maleta a nodos n8n (HTTP Request, Set, IF, Schedule)
      - POST al endpoint de n8n (/rest/workflows) si hay token configurado
      - Versionado del workflow (maleta_id + version)
      - Verificación de que el workflow pasa un dry-run antes de activarse
    """

    def __init__(
        self,
        *,
        n8n_base_url: str | None = None,
        api_token: str | None = None,
        export_dir: Path | None = None,
    ) -> None:
        self.n8n_base_url = n8n_base_url
        self.api_token = api_token
        self.export_dir = Path(export_dir) if export_dir else (Path.home() / ".ura" / "n8n_exports")

    def is_eligible(self, maleta: dict[str, Any], uses: int) -> bool:
        """Decide si una maleta cumple los criterios de promoción a N1.

        Criterios (plan v3):
          - confianza ≥ 0.95
          - uses ≥ 20
          - validadores presentes en la maleta
        """
        try:
            conf = float(maleta.get("confianza", 0.0))
        except (TypeError, ValueError):
            return False
        validadores_ok = bool((maleta.get("herramientas") or {}).get("validadores"))
        return conf >= 0.95 and uses >= 20 and validadores_ok

    def build_workflow_json(self, maleta: dict[str, Any]) -> dict[str, Any]:
        """
        Traducir la maleta a un JSON de workflow de n8n con nodos básicos:

          ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
          │ Schedule │ →  │ Set vars │ →  │ HTTP Req │ →  │  Filter  │
          └──────────┘    └──────────┘    └──────────┘    └──────────┘

        El workflow queda inactivo (`active=False`) hasta que el usuario lo
        revise y lo active manualmente en n8n.
        """
        maleta_id = maleta.get("maleta_id", "desconocida")
        tema = maleta.get("tema", "")
        buscadores = (maleta.get("herramientas") or {}).get("buscadores", []) or []
        validadores = (maleta.get("herramientas") or {}).get("validadores", []) or []
        fuentes = maleta.get("fuentes_blancas") or {}
        cache_h = (maleta.get("anti_repeticion") or {}).get("cache_duracion_horas", 24)

        # Nodos
        nodes = [
            {
                "id": "node_schedule",
                "name": "Schedule",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "rule": {"interval": [{"field": "hours", "hoursInterval": int(cache_h)}]},
                },
            },
            {
                "id": "node_set",
                "name": "Set vars",
                "type": "n8n-nodes-base.set",
                "typeVersion": 1,
                "position": [460, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "maleta_id", "value": maleta_id},
                            {"name": "tema", "value": tema},
                            {"name": "version", "value": str(maleta.get("version", 1))},
                        ],
                    },
                },
            },
            {
                "id": "node_http_search",
                "name": "DDG Search",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [700, 300],
                "parameters": {
                    "url": "https://duckduckgo.com/html/",
                    "method": "GET",
                    "queryParameters": {
                        "parameters": [
                            {"name": "q", "value": "={{$json.tema}}"},
                            {"name": "kl", "value": "es-es"},
                        ],
                    },
                    "options": {"timeout": 20000},
                },
            },
            {
                "id": "node_filter",
                "name": "Filter live URLs",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [940, 300],
                "parameters": {
                    "conditions": {
                        "boolean": [],
                        "string": [
                            {
                                "value1": "={{$json.body}}",
                                "operation": "isNotEmpty",
                            }
                        ],
                    },
                },
            },
        ]

        connections = {
            "Schedule": {"main": [[{"node": "Set vars", "type": "main", "index": 0}]]},
            "Set vars": {"main": [[{"node": "DDG Search", "type": "main", "index": 0}]]},
            "DDG Search": {"main": [[{"node": "Filter live URLs", "type": "main", "index": 0}]]},
        }

        return {
            "name": f"URA N2→N1 · {maleta_id}",
            "nodes": nodes,
            "connections": connections,
            "active": False,
            "settings": {"executionOrder": "v1"},
            "staticData": None,
            "meta": {
                "source": "URA N2 exporter",
                "maleta_id": maleta_id,
                "version": maleta.get("version", 1),
                "buscadores_count": len(buscadores),
                "validadores_count": len(validadores),
                "fuentes_oficiales": [f.get("dominio") for f in fuentes.get("oficiales", [])],
                "cache_duracion_horas": cache_h,
            },
        }

    async def export(self, maleta: dict[str, Any], *, uses: int) -> N8nExportResult:
        """
        [STUB] Exportar una maleta a n8n.

        Fase 4 completará esto con:
          - Construcción real del workflow JSON
          - POST a /rest/workflows con auth
          - Retorno del workflow_id asignado
        """
        result = N8nExportResult(ok=False)
        if not self.is_eligible(maleta, uses):
            result.errores.append(
                f"Maleta no elegible (conf={maleta.get('confianza')}, uses={uses})"
            )
            return result

        # Persist local JSON copy regardless of remote POST
        self.export_dir.mkdir(parents=True, exist_ok=True)
        workflow = self.build_workflow_json(maleta)
        out_path = self.export_dir / f"{maleta['maleta_id']}.workflow.json"
        try:
            import json

            with out_path.open("w", encoding="utf-8") as f:
                json.dump(workflow, f, ensure_ascii=False, indent=2)
            result.workflow_json_path = out_path
            result.detalles["local_only"] = True
            result.ok = True
            logger.info("Exportado workflow (stub) a %s", out_path)
        except Exception as e:  # noqa: BLE001
            result.errores.append(f"Error escribiendo workflow local: {e}")
            return result

        if self.n8n_base_url and self.api_token:
            result.errores.append("Upload remoto pendiente (Fase 4)")
        return result

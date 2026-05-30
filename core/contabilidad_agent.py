#!/usr/bin/env python3
"""
Agente de Contabilidad - Fase 4
Gestión contable española: PGC, IVA, IRPF, modelos oficiales.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).parent / "contabilidad_knowledge.json"


class ContabilidadAgent:
    """Agente de contabilidad especializado en normativa española."""

    def __init__(self, knowledge_path: Path = None):
        if knowledge_path is None:
            knowledge_path = KNOWLEDGE_PATH
        self.knowledge_path = knowledge_path
        self.knowledge = self._load_knowledge()

    def _load_knowledge(self) -> dict:
        """Cargar conocimiento contable desde JSON."""
        if self.knowledge_path.exists():
            try:
                with open(self.knowledge_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando conocimiento: {e}")
        return self._default_knowledge()

    def _default_knowledge(self) -> dict:
        """Conocimiento por defecto."""
        return {
            "iva": {"general": 21, "reducido": 10, "superreducido": 4},
            "modelos": {
                "303": "IVA trimestral",
                "130": "IVA mensual",
                "390": "Resumen anual IVA",
                "347": "Operaciones con terceros",
            },
            "deducciones_navarra": [
                "Deducción por inversiones en activos fijos",
                "Deducción por gastos de formación",
                "Deducción por I+D+I",
            ],
            "software": [
                {"nombre": "GnuCash", "tipo": "open_source", "recomendado": True},
                {"nombre": "Ledger", "tipo": "open_source", "recomendado": True},
                {"nombre": "Odoo", "tipo": "erp", "recomendado": False},
                {"nombre": "Akaunting", "tipo": "cloud", "recomendado": True},
            ],
        }

    def generar_asiento(
        self, desc: str, debe: float, haber: float, importe: float, iva: float = 0.0
    ) -> dict:
        """Generar asiento contable."""
        iva_general = self.knowledge.get("iva", {}).get("general", 21)
        base_imponible = importe / (1 + iva_general / 100) if iva_general > 0 else importe

        return {
            "descripcion": desc,
            "debe": debe,
            "haber": haber,
            "importe": importe,
            "iva": iva,
            "base_imponible": base_imponible,
            "tipo_iva": iva_general,
        }

    def consultar_deduccion(self, tema: str) -> dict | None:
        """Consultar deducción por tema."""
        deducciones = self.knowledge.get("deducciones_navarra", [])
        for ded in deducciones:
            if tema.lower() in ded.lower():
                return {"tema": ded, "aplicable": True}
        return None

    def recomendar_software(self) -> str:
        """Recomendar software contabilidad."""
        software = self.knowledge.get("software", [])
        recomendados = [s for s in software if s.get("recomendado", False)]
        if recomendados:
            return f"Recomendado: {recomendados[0]['nombre']} ({recomendados[0]['tipo']})"
        return "GnuCash (open source, gratuito)"


if __name__ == "__main__":
    agent = ContabilidadAgent()
    print("Software:", agent.recomendar_software())
    print("Asiento:", agent.generar_asiento("Venta", 100, 0, 121, 21))

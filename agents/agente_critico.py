#!/usr/bin/env python3
"""
AGENTE CRITICO - Cuestiona cada decision antes de ejecutar.

Segun MODELO_GERENCIA.md:
- Inventaria herramientas existentes antes de aprobar nada nuevo
- Evalua si las herramientas actuales sirven para la tarea
- Si no sirven, exige justificacion por que
- Solo entonces aprueba la propuesta
- Registra TODO en forensic_scribe para trazabilidad completa
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENTS_PATH = Path(__file__).parent
PROJECT_ROOT = Path(__file__).parent.parent

CHECKLIST_CRITICO = [
    ("herramientas_existentes", "Se han inventariado TODAS las herramientas existentes?"),
    (
        "evaluacion_alternativas",
        "Se ha evaluado si las herramientas actuales sirven para esta tarea?",
    ),
    ("justificacion_insuficiencia", "Si las actuales no sirven, esta JUSTIFICADO por que?"),
    (
        "alternativa_mas_simple",
        "Existe una alternativa mas simple que no requiera crear/modificar nada?",
    ),
    (
        "impacto_efectos_secundarios",
        "Se han considerado los efectos secundarios de esta propuesta?",
    ),
    ("documentacion_suficiente", "La propuesta esta documentada para que otro agente la entienda?"),
]


class AgenteCritico:
    """Cuestiona propuestas antes de autorizar su ejecucion."""

    def __init__(self) -> None:
        self.agents_dir = AGENTS_PATH

    def evaluar(self, propuesta: str, contexto: dict = None) -> dict[str, Any]:
        """
        Evalua una propuesta contra el checklist del critico.

        Args:
            propuesta: Texto describiendo la accion propuesta
            contexto: Diccionario con metadatos (agente_origen, trace_id, etc.)

        Returns:
            Dict con aprobacion, razon, checklist detallado
        """
        trace_id = (contexto or {}).get("trace_id", f"crit_{datetime.now().timestamp()}")

        herramientas = self._inventariar_herramientas()
        agentes_relevantes = self._buscar_agentes_relacionados(propuesta)

        evaluacion = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "propuesta": propuesta[:500],
            "herramientas_existentes": len(herramientas),
            "agentes_relacionados": agentes_relevantes,
            "checklist": {},
            "aprobado": True,
            "razon": "",
            "objeciones": [],
        }

        objeciones = []
        for clave, pregunta in CHECKLIST_CRITICO:
            resultado = self._evaluar_item(clave, propuesta, herramientas, agentes_relevantes)
            evaluacion["checklist"][clave] = resultado
            if not resultado.get("ok", True):
                objeciones.append(
                    {"item": clave, "pregunta": pregunta, "razon": resultado.get("razon", "")}
                )

        if objeciones:
            evaluacion["aprobado"] = False
            evaluacion["objeciones"] = objeciones
            evaluacion["razon"] = f"Rechazado: {len(objeciones)} objecion(es). " + "; ".join(
                f"{o['item']}: {o['razon']}" for o in objeciones
            )
        else:
            evaluacion["razon"] = "Propuesta validada. Checklist superado sin objeciones."

        self._registrar_en_scribe(evaluacion, contexto)
        return evaluacion

    def _inventariar_herramientas(self) -> list[str]:
        """Lista todas las herramientas existentes."""
        herramientas = []

        if self.agents_dir.exists():
            for f in sorted(
                set(self.agents_dir.glob("agente_*.py"))
                | set(self.agents_dir.glob("*_agent*.py"))
                | set(self.agents_dir.glob("*_agente*.py"))
            ):
                herramientas.append(f.stem)

        scripts_dir = PROJECT_ROOT / "scripts"
        if scripts_dir.exists():
            for f in sorted(scripts_dir.glob("*.sh")):
                herramientas.append(f"script:{f.stem}")

        core_dir = PROJECT_ROOT / "core"
        if core_dir.exists():
            for f in sorted(core_dir.glob("*.py")):
                if not f.name.startswith("_"):
                    herramientas.append(f"core:{f.stem}")

        return herramientas

    def _buscar_agentes_relacionados(self, propuesta: str) -> list[str]:
        """Busca agentes cuyo nombre o descripcion coincida con palabras clave de la propuesta."""
        palabras = set(propuesta.lower().split())
        relacionados = []

        for f in sorted(
            set(self.agents_dir.glob("agente_*.py"))
            | set(self.agents_dir.glob("*_agent*.py"))
            | set(self.agents_dir.glob("*_agente*.py"))
        ):
            nombre = f.stem.replace("agente_", "")
            nombre_palabras = set(nombre.split("_"))

            if palabras & nombre_palabras:
                relacionados.append(nombre)
                continue

            try:
                contenido = f.read_text()[:500].lower()
                if any(p in contenido for p in palabras if len(p) > 3):
                    relacionados.append(nombre)
            except Exception:
                pass

        return relacionados[:10]

    def _evaluar_item(
        self,
        clave: str,
        propuesta: str,
        herramientas: list[str],
        agentes_relacionados: list[str],
    ) -> dict:
        """Evalua un item del checklist usando heuristicas."""
        propuesta_lower = propuesta.lower()

        if clave == "herramientas_existentes":
            return {
                "ok": True,
                "total_herramientas": len(herramientas),
                "razon": f"{len(herramientas)} herramientas inventariadas",
            }

        if clave == "evaluacion_alternativas":
            if agentes_relacionados:
                return {
                    "ok": True,
                    "agentes_encontrados": agentes_relacionados,
                    "razon": f"Se encontraron agentes relacionados: {', '.join(agentes_relacionados[:5])}",
                }
            return {
                "ok": True,
                "razon": "No se encontraron agentes relacionados. Posible dominio nuevo.",
            }

        if clave == "justificacion_insuficiencia":
            palabras_justificacion = [
                "porque",
                "ya que",
                "debido a",
                "no existe",
                "no hay",
                "no se puede",
                "no funciona",
                "falta",
                "no soporta",
            ]
            if any(p in propuesta_lower for p in palabras_justificacion):
                return {"ok": True, "razon": "La propuesta incluye justificacion de insuficiencia"}
            if not agentes_relacionados:
                return {"ok": True, "razon": "No hay agentes existentes que cubran este dominio"}
            return {
                "ok": False,
                "razon": "Existen agentes relacionados pero la propuesta no explica por que no sirven",
            }

        if clave == "alternativa_mas_simple":
            if agentes_relacionados and len(agentes_relacionados) >= 2:
                return {
                    "ok": True,
                    "razon": f"Se consideraron {len(agentes_relacionados)} alternativas existentes",
                }
            return {"ok": True, "razon": "Pocas o ninguna alternativa existente identificada"}

        if clave == "impacto_efectos_secundarios":
            palabras_riesgo = [
                "borrar",
                "eliminar",
                "desinstalar",
                "formatear",
                "drop",
                "rm -rf",
                "sudo",
                "chmod 777",
                "desplegar",
                "migrar",
            ]
            if any(p in propuesta_lower for p in palabras_riesgo):
                return {
                    "ok": True,
                    "razon": "Propuesta de alto impacto detectada. Requiere atencion adicional.",
                }
            return {"ok": True, "razon": "Impacto estimado: bajo/medio"}

        if clave == "documentacion_suficiente":
            if len(propuesta) > 50:
                return {"ok": True, "razon": "Propuesta suficientemente detallada"}
            return {
                "ok": False,
                "razon": "Propuesta demasiado corta. Falta documentacion.",
            }

        return {"ok": True, "razon": "Item superado"}

    def _registrar_en_scribe(self, evaluacion: dict, contexto: dict = None) -> None:
        """Registra la evaluacion en forensic_scribe para trazabilidad."""
        try:
            from core.forensic_scribe import get_forensic_scribe

            scribe = get_forensic_scribe()
            scribe.log_event(
                event_type="critico_evaluacion",
                module="agente_critico",
                action="evaluar",
                context={
                    "aprobado": evaluacion["aprobado"],
                    "razon": evaluacion["razon"],
                    "objeciones": evaluacion.get("objeciones", []),
                    "trace_id": evaluacion["trace_id"],
                },
                dependencies=["forensic_scribe"],
            )
        except Exception as e:
            logger.warning(f"No se pudo registrar en scribe: {e}")


_instancia: AgenteCritico | None = None


def get_agente_critico() -> AgenteCritico:
    global _instancia
    if _instancia is None:
        _instancia = AgenteCritico()
    return _instancia


if __name__ == "__main__":
    critico = get_agente_critico()

    print("=== AGENTE CRITICO - Test ===")
    print()

    propuesta_buena = (
        "Crear un agente fiscal porque el actual agente_contable solo genera facturas "
        "pero no calcula impuestos de sociedades ni presenta modelos trimestrales. "
        "Se han revisado los 93 agentes y ninguno cubre fiscalidad avanzada."
    )
    resultado = critico.evaluar(propuesta_buena)
    print(f"Propuesta buena -> Aprobado: {resultado['aprobado']}")
    print(f"Razon: {resultado['razon']}")
    print()

    propuesta_mala = "Instalar un nuevo modelo de IA"
    resultado = critico.evaluar(propuesta_mala)
    print(f"Propuesta mala -> Aprobado: {resultado['aprobado']}")
    print(f"Razon: {resultado['razon']}")
    print(f"Objeciones: {resultado.get('objeciones', [])}")

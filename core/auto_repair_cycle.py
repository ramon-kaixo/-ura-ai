#!/usr/bin/env python3
"""
URA - Auto Repair Cycle

Cierra el ciclo completo de auto-reparación:
    Error detectado → generator_repair genera parche → validación
    sintáctica → validación de seguridad (agente_policia) → aplicación

El parche solo se escribe a disco si:
    - El generator devuelve ok=True
    - El parche es Python sintácticamente válido (ast.parse)
    - agente_policia no lo bloquea
    - La confianza del generator es 'alta'

Si la confianza no es alta, el ciclo termina en estado
'pendiente_confirmacion' y queda registrado en el historial.
"""

import ast
import logging
import pathlib

from core.code_agents.generators import generar

logger = logging.getLogger(__name__)


def _validar_seguridad(codigo: str) -> dict:
    """
    Adaptador de validación de seguridad.

    Intenta primero `validar_comando` (si se añade en el futuro), y
    cae al API actual `get_agente_policia().validar()`. Devuelve siempre
    un dict con la forma {'permitido': bool, 'motivo': str}.

    Si el módulo no está disponible, fail-open (permitido=True).
    """
    try:
        try:
            from core.agente_policia_v2 import validar_comando

            res = validar_comando(codigo)
            return {
                "permitido": res.get("permitido", True),
                "motivo": res.get("motivo", "seguridad"),
            }
        except ImportError:
            from core.agente_policia_v2 import get_agente_policia

            resultado = get_agente_policia().validar(codigo)
            veredicto = (resultado.get("veredicto") or "").upper()
            permitido = veredicto != "RECHAZADO"
            razones = resultado.get("razon", [])
            motivo = "; ".join(razones) if isinstance(razones, list) else str(razones)
            return {"permitido": permitido, "motivo": motivo}
    except Exception as exc:
        logger.error(f"Validación de seguridad falló (fail-open): {exc}")
        return {"permitido": True, "motivo": f"validación no disponible: {exc}"}


class AutoRepairCycle:
    """
    Orquesta el ciclo de auto-reparación de archivos Python.

    Uso:
        cycle = AutoRepairCycle()
        result = cycle.reparar(archivo, error, traceback)
        if result["ok"] and result["etapa"] == "aplicado":
            print("Parche aplicado")
    """

    def __init__(self):
        self.repair_log: list[dict] = []

    def reparar(self, archivo: str, error: str, traceback: str) -> dict:
        """Ciclo completo: detecta → genera → valida → aplica.

        Args:
            archivo: ruta absoluta o relativa al archivo a reparar.
            error: mensaje corto del error detectado.
            traceback: traceback completo del error.

        Returns:
            dict con claves 'ok', 'etapa' y campos adicionales según la etapa.
        """
        path = pathlib.Path(archivo)

        # 0. Pre-condición: archivo existe y se puede leer
        try:
            codigo_actual = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"ok": False, "etapa": "lectura", "error": f"Archivo no encontrado: {archivo}"}
        except Exception as exc:
            return {"ok": False, "etapa": "lectura", "error": str(exc)}

        # 1. Generar parche con generator_repair
        tarea = (
            f"Archivo: {archivo}\nError: {error}\nTraceback: {traceback}\nCódigo:\n{codigo_actual}"
        )
        resultado = generar("repair", tarea)

        if not resultado.get("ok"):
            return {
                "ok": False,
                "etapa": "generacion",
                "error": resultado.get("error", "generator_repair falló"),
            }

        codigo_nuevo = resultado.get("codigo", "")
        if not codigo_nuevo:
            return {
                "ok": False,
                "etapa": "generacion",
                "error": "generator_repair devolvió código vacío",
            }

        # 2. Validar sintaxis Python con ast
        try:
            ast.parse(codigo_nuevo)
        except SyntaxError as e:
            return {"ok": False, "etapa": "validacion_sintaxis", "error": str(e)}

        # 3. Validar seguridad con agente_policia
        validacion = _validar_seguridad(codigo_nuevo)
        if not validacion.get("permitido", True):
            return {
                "ok": False,
                "etapa": "validacion_seguridad",
                "error": validacion.get("motivo", "rechazado por agente_policia"),
            }

        # 4. Aplicar solo si confianza alta
        confianza = resultado.get("confianza")
        if confianza == "alta":
            try:
                path.write_text(codigo_nuevo, encoding="utf-8")
            except Exception as exc:
                return {"ok": False, "etapa": "escritura", "error": str(exc)}

            self.repair_log.append({"archivo": archivo, "error": error, "aplicado": True})
            logger.info(f"AutoRepair aplicado a {archivo} (confianza alta)")
            return {"ok": True, "etapa": "aplicado", "confianza": "alta"}

        # 5. Confianza no alta — pendiente de confirmación
        self.repair_log.append({"archivo": archivo, "error": error, "aplicado": False})
        logger.info(f"AutoRepair pendiente de confirmación para {archivo} (confianza {confianza})")
        return {
            "ok": True,
            "etapa": "pendiente_confirmacion",
            "confianza": confianza,
            "codigo": codigo_nuevo,
        }

    def historial(self) -> list:
        """Devuelve el historial de reparaciones de esta instancia."""
        return self.repair_log

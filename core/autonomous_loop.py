#!/usr/bin/env python3
"""Bucle autónomo de Laia — Nivel 3.

Corre en segundo plano y decide qué hacer basándose en el estado del sistema
(stock, afluencia, productividad) sin esperar órdenes humanas.
"""

import logging
import time

from core.governance import Governance
from core.planner import TaskPlanner
from agents.laia_agent import LaiaAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/laia_autonomous.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 600


def get_system_status() -> dict:
    """Consulta el estado del sistema vía health_api de Tuneladora."""
    import requests

    try:
        resp = requests.get("http://127.0.0.1:5103/health", timeout=10)
        return resp.json()
    except Exception as exc:
        logger.warning("No se pudo obtener estado del sistema: %s", exc)
        return {}


def detect_needs(status: dict) -> list[str]:
    """Detecta necesidades basándose en el estado del sistema."""
    needs: list[str] = []

    stock_cerveza = status.get("stock_cerveza")
    if stock_cerveza is not None and stock_cerveza < 10:
        needs.append("reponer stock de cerveza")

    afluencia = status.get("afluencia_hoy")
    personal = status.get("personal_en_sala")
    if afluencia is not None and afluencia > 100 and personal is not None and personal < 3:
        needs.append("avisar a refuerzos")

    tiempo_atencion = status.get("tiempo_medio_atencion")
    if tiempo_atencion is not None and tiempo_atencion > 15:
        needs.append("optimizar servicio en barra")

    servicios = status.get("servicios", {})
    for nombre, data in servicios.items():
        if isinstance(data, dict) and data.get("status") != "ok":
            needs.append(f"verificar servicio {nombre}")

    return needs


def main() -> None:
    agent = LaiaAgent()
    gov = Governance()
    planner = TaskPlanner()

    logger.info("Bucle autónomo iniciado (intervalo=%ds)", INTERVAL_SECONDS)

    while True:
        try:
            status = get_system_status()
            needs = detect_needs(status)

            if not needs:
                logger.info("Sin necesidades detectadas")
            else:
                logger.info("Necesidades detectadas: %s", needs)
                for need in needs:
                    if gov.should_ask_human(need):
                        logger.info("Necesidad de riesgo alto, esperando confirmacion: %s", need)
                        if agent.safety.confirm_action(f"Propongo: {need}. ¿Ejecuto?"):
                            plan = planner.plan(need)
                            planner.execute_plan(plan, agent.executor, agent.reader)
                    else:
                        logger.info("Ejecutando autonomamente: %s", need)
                        plan = planner.plan(need)
                        planner.execute_plan(plan, agent.executor, agent.reader)

        except Exception as exc:
            logger.error("Error en bucle autónomo: %s", exc)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

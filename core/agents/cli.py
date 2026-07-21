"""CLI entry point for the multi-agent system."""

import sys

from core.agents.conciencia import Conciencia
from core.agents.healing import SelfHealingLoop
from core.agents.orquestador import AgenteOrquestador
from core.agents.reparador import AgenteReparador
from core.agents.telemetry import Telemetria


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="URA Multi-Agent System")
    parser.add_argument(
        "--modo",
        choices=["orquestar", "reparar", "ciclo"],
        default="ciclo",
        help="Modo de operación",
    )
    parser.add_argument("--archivo", help="Archivo a reparar (solo con --modo reparar)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    loop = SelfHealingLoop()

    if args.modo == "reparar" and args.archivo:
        reparador = AgenteReparador()
        reparado, nivel, _msg = reparador.reparar(args.archivo, [])
        if args.json:
            pass
        else:
            {1: "🔧", 2: "🤖", 3: "🧠"}.get(nivel, "❌")
        sys.exit(0 if reparado else 1)

    elif args.modo == "orquestar":
        tele = Telemetria().reporte_completo()
        conciencia = Conciencia.leer()
        _accion, _razon = AgenteOrquestador().decidir(tele, conciencia)

    else:
        loop.ejecutar()
        if args.json:
            pass
        else:
            pass


if __name__ == "__main__":
    main()

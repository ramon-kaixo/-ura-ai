"""CLI: agent list, run."""

import sys
from pathlib import Path

from knowledge.engine.cli.main import _resolve_db_path


def cmd_agent_list(args) -> int:
    from knowledge.engine.agent import list_agents

    agents = list_agents()
    if not agents:
        print("No hay agentes registrados.")
        return 0
    print("Agentes disponibles:")
    for a in agents:
        print(f"  - {a}")
    return 0


def cmd_agent_run(args) -> int:
    from knowledge.engine.agent import AgentGoal, get_agent

    agent_id = args.agent_id
    db_path = _resolve_db_path(args)
    kind = args.kind if hasattr(args, "kind") and args.kind else "audit"

    agent = get_agent(agent_id, db_path=db_path)
    if agent is None:
        print(f"Agente no encontrado: {agent_id}", file=sys.stderr)
        return 1

    goal = AgentGoal(kind=kind, description=f"CLI run: {kind}")
    findings = agent.execute(goal)

    if not findings:
        print(f"Agente {agent_id}: sin hallazgos.")
        return 0

    for f in findings:
        sev = {"INFO": "\u2139\ufe0f", "WARN": "\u26a0\ufe0f", "ERROR": "\u274c"}.get(f.severity, "?")
        print(f"{sev} [{f.kind}] {f.title}")
        print(f"     {f.description}")
    print(f"\nTotal: {len(findings)} hallazgos")
    return 0

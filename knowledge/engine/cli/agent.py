"""CLI: agent list, run."""

from knowledge.engine.cli.main import _resolve_db_path


def cmd_agent_list(args) -> int:
    from knowledge.engine.agent import list_agents

    agents = list_agents()
    if not agents:
        return 0
    for _a in agents:
        pass
    return 0


def cmd_agent_run(args) -> int:
    from knowledge.engine.agent import AgentGoal, get_agent

    agent_id = args.agent_id
    db_path = _resolve_db_path(args)
    kind = args.kind if hasattr(args, "kind") and args.kind else "audit"

    agent = get_agent(agent_id, db_path=db_path)
    if agent is None:
        return 1

    goal = AgentGoal(kind=kind, description=f"CLI run: {kind}")
    findings = agent.execute(goal)

    if not findings:
        return 0

    for f in findings:
        {"INFO": "\u2139\ufe0f", "WARN": "\u26a0\ufe0f", "ERROR": "\u274c"}.get(f.severity, "?")
    return 0

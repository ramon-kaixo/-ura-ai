"""SecurityAgent — auditorías, secretos, permisos."""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.swarm.agent_base import AgentBase


class SecurityAgent(AgentBase):
    """Audita seguridad del proyecto."""

    def __init__(self, engine) -> None:
        super().__init__("guardian", "security", engine)

    def work(self, goal: dict) -> dict[str, Any]:
        self.log(f"Auditando seguridad: {goal.get('title')}")
        result = self._engine.run_script("scripts/pro/check_secrets.py", timeout=60)
        issues = result.returncode
        self.log(f"Problemas de seguridad: {issues}")
        return {"status": "ok" if issues == 0 else "issues", "security_issues": issues}

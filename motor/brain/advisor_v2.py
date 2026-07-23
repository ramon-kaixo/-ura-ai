"""Advisor con memoria — no repite lo que fallo."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from motor.brain.analyzer import CodeAnalyzer
from motor.brain.memory import BrainMemory, ProposalRecord


class SmartAdvisor:
    def __init__(self) -> None:
        self.analyzer = CodeAnalyzer()
        self.memory = BrainMemory()

    def propose(self, module_path: str) -> list[dict[str, Any]]:
        raw = self._generate_raw(module_path)
        filtered: list[dict[str, Any]] = []
        for p in raw:
            if self.memory.should_propose_again(p["target"], p["type"]):
                filtered.append(p)
            else:
                filtered.append({**p, "skipped": True, "reason_skip": "Previously failed or succeeded"})
        return filtered

    def _generate_raw(self, module_path: str) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        for result in self.analyzer.analyze_module(Path(module_path)):
            if result.get("complex_functions"):
                proposals.append({"type": "refactor", "target": result["file"], "reason": f"Complex: {result['complex_functions']}", "priority": "high"})
        return proposals

    def record_result(self, proposal: dict[str, Any], approved: bool, result: str, notes: str = "") -> None:
        self.memory.save(ProposalRecord(target_file=proposal.get("target", ""), proposal_type=proposal.get("type", ""), reason=proposal.get("reason", ""), priority=proposal.get("priority", "low"), approved=approved, result=result, notes=notes))

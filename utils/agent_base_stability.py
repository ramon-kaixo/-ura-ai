"""
Stub de AgentStabilityBase para resolver dependencias faltantes
"""


class AgentStabilityBase:
    """Base class stub para agentes con stability"""

    def __init__(self, name):
        self.name = name

    def log_reasoning_step(self, step, data, confidence=1.0):
        """Stub de log_reasoning_step"""

    def get_agent_capabilities(self):
        """Stub de get_agent_capabilities"""
        return {}

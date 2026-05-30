#!/usr/bin/env python3
"""
Gestor de metadata de agentes para URA
Encapsula la lógica de generación de metadata de agentes
"""


class AgentMetadata:
    """Gestor de metadata de agentes."""

    def __init__(self, intent_keywords: dict[str, list[str]] = None):
        self.intent_keywords = intent_keywords or {}

    def get_metadata(self, intent: str, agent_path: str, routing_method: str = "keywords") -> dict:
        """
        Obtener metadata del agente.

        Args:
            intent: Intención detectada
            agent_path: Ruta del agente
            routing_method: Método de routing usado

        Returns:
            Dict con metadata
        """
        keywords = self.intent_keywords.get(intent, [])

        # Buscar agentes relacionados por palabras clave comunes
        related_agents = []
        for other_intent, other_keywords in self.intent_keywords.items():
            if other_intent != intent:
                common_keywords = set(keywords) & set(other_keywords)
                if len(common_keywords) > 0:
                    related_agents.append(
                        {"intent": other_intent, "common_keywords": list(common_keywords)}
                    )

        # Ordenar por número de keywords comunes y limitar a 3
        related_agents.sort(key=lambda x: len(x["common_keywords"]), reverse=True)
        related_agents = related_agents[:3]

        return {
            "keywords": keywords,
            "related_agents": related_agents,
            "routing_method": routing_method,
            "agent_path": agent_path,
        }

    def set_keywords(self, intent_keywords: dict[str, list[str]]) -> None:
        """Establecer keywords por intención."""
        self.intent_keywords = intent_keywords

#!/usr/bin/env python3
"""
URA GraphQL API
"""

from core.logging_config import get_logger
from strawberry import Schema, field, type
from strawberry.fastapi import GraphQLRouter
from datetime import UTC

logger = get_logger("graphql_api", log_dir="./logs")


@type
class ChatMessage:
    """Tipo de mensaje de chat"""

    id: str
    role: str
    content: str
    timestamp: str


@type
class ChatResponse:
    """Tipo de respuesta de chat"""

    response: str
    model: str
    timestamp: str


@type
class HealthStatus:
    """Tipo de estado de salud"""

    status: str
    ollama_connected: bool
    cpu_usage: float


@type
class Query:
    """Queries de GraphQL"""

    @field
    def health(self) -> HealthStatus:
        """Query de health check"""
        import psutil

        return HealthStatus(status="healthy", ollama_connected=True, cpu_usage=psutil.cpu_percent())

    @field
    def chat_history(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        """Query de historial de chat"""
        # Simulado - en producción usaría database
        return [
            ChatMessage(id="1", role="user", content="Hola", timestamp="2026-04-24T09:00:00"),
            ChatMessage(
                id="2",
                role="assistant",
                content="Hola, ¿en qué puedo ayudarte?",
                timestamp="2026-04-24T09:00:01",
            ),
        ]


@type
class Mutation:
    """Mutations de GraphQL"""

    @field
    def send_chat(self, message: str, model: str = "llama3.2:1b") -> ChatResponse:
        """Mutation de chat"""
        from datetime import datetime

        logger.info(f"GraphQL chat: {message[:50]}...")
        return ChatResponse(
            response=f"Respuesta: {message}",
            model=model,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )


# Crear schema
schema = Schema(query=Query, mutation=Mutation)

# Crear router
graphql_app = GraphQLRouter(schema)


if __name__ == "__main__":
    # Test GraphQL schema
    print("GraphQL schema created successfully")

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class ProviderError(Exception):
    def __init__(self, message: str, provider: str, status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message)


class Provider(ABC):
    @property
    @abstractmethod
    def nombre(self) -> str: ...

    @property
    @abstractmethod
    def timeout(self) -> int: ...

    @abstractmethod
    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]: ...

    @abstractmethod
    async def health(self) -> dict: ...

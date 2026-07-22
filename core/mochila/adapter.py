import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

log = logging.getLogger(__name__)


def _messages_to_prompt(mensajes: list) -> str:
    partes: list[str] = []
    for m in mensajes:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            content = "\n".join(texts)
        partes.append(f"<{role}>{content}</{role}>")
    return "\n".join(partes)


class _MotorChatAdapter:
    def __init__(self, name: str, provider: Any) -> None:
        self._name = name
        self._provider = provider

    @property
    def nombre(self) -> str:
        return self._name

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        prompt = _messages_to_prompt(mensajes)
        loop = asyncio.get_running_loop()
        try:
            text = await loop.run_in_executor(
                None,
                self._provider.generate,
                prompt,
                modelo,
                {"temperature": temperature, "num_predict": max_tokens},
            )
        except Exception as e:
            yield {"error": str(e), "type": "provider_error"}
            return
        yield {
            "choices": [{"delta": {"content": text}, "finish_reason": "stop", "index": 0}],
            "model": modelo,
        }

    async def health(self) -> dict:
        return self._provider.health()

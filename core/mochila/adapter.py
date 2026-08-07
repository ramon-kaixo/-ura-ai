"""Adapter de paridad v1: adapta motor.core.llm (v2) al contrato mochila (v1).

El contrato v1 (core/mochila/providers/) exige:
  - chat() async generator con forma OpenAI: choices[0].message (no-stream)
    o choices[0].delta (stream) + chunk final {delta:{}, finish_reason}
  - tool_calls en message/delta
  - usage en la respuesta
  - ProviderError(provider, status_code) para errores

Este adapter emite exactamente ese contrato usando motor.core.llm (v2):
  - streaming real vía provider.generate_stream() (si existe; si no, degrada)
  - tools vía provider.chat_generate() (si existe; si no, degrada)
  - errores convertidos a ProviderError con status_code 502
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from core.mochila.providers.base import ProviderError

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


def _extraer_tool_call(content: str) -> list | None:
    try:
        obj = json.loads(content) if isinstance(content, str) else None
        if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
            args = obj["arguments"]
            return [
                {
                    "id": "call_0",
                    "type": "function",
                    "function": {
                        "name": obj["name"],
                        "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
                    },
                },
            ]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


_FIN_ITER = object()


def _next_trozo(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return _FIN_ITER


class _MotorChatAdapter:
    def __init__(self, name: str, provider: Any) -> None:
        self._name = name
        self._provider = provider

    @property
    def nombre(self) -> str:
        return self._name

    @property
    def timeout(self) -> int:
        return getattr(self._provider, "_timeout", 60)

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        options = {"temperature": temperature, "num_predict": max_tokens}
        if stream:
            async for chunk in self._stream(modelo, mensajes, tools, options):
                yield chunk
            return
        yield await self._no_stream(modelo, mensajes, tools, options)

    async def _no_stream(self, modelo: str, mensajes: list, tools: list | None, options: dict) -> dict:
        loop = asyncio.get_running_loop()
        try:
            if tools and hasattr(self._provider, "chat_generate"):
                result = await loop.run_in_executor(
                    None,
                    lambda: self._provider.chat_generate(mensajes, modelo, tools, options),
                )
                content = result.get("content", "")
                tool_calls = result.get("tool_calls")
                usage = result.get("usage") or {}
            else:
                prompt = _messages_to_prompt(mensajes)
                text = await loop.run_in_executor(
                    None,
                    lambda: self._provider.generate(prompt, modelo, options),
                )
                if isinstance(text, str) and text.startswith("Error: "):
                    raise ProviderError(text, provider=self._name, status_code=502)
                content = text
                tool_calls = _extraer_tool_call(content)
                usage = {}
            message: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                message["tool_calls"] = tool_calls
            return {
                "id": f"mochila-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": modelo,
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if tool_calls else "stop",
                    },
                ],
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
                    "completion_tokens": usage.get("completion_tokens", 0) or 0,
                    "total_tokens": usage.get("total_tokens", 0) or 0,
                },
            }
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e), provider=self._name, status_code=502) from e

    async def _stream(
        self,
        modelo: str,
        mensajes: list,
        tools: list | None,
        options: dict,
    ) -> AsyncGenerator[dict, None]:
        prompt = _messages_to_prompt(mensajes)
        loop = asyncio.get_running_loop()
        chunks = 0
        usage: dict = {}
        try:
            if tools and hasattr(self._provider, "chat_generate"):
                result = await loop.run_in_executor(
                    None,
                    lambda: self._provider.chat_generate(mensajes, modelo, tools, options),
                )
                content = result.get("content", "")
                usage = result.get("usage") or {}
                if content:
                    yield _chunk_delta(modelo, {"content": content}, None)
                chunks += 1
            elif hasattr(self._provider, "generate_stream"):
                iterator = self._provider.generate_stream(prompt, modelo, options)
                while True:
                    trozo = await loop.run_in_executor(None, _next_trozo, iterator)
                    if trozo is _FIN_ITER:
                        break
                    if trozo:
                        yield _chunk_delta(modelo, {"content": trozo}, None)
                        chunks += 1
            else:
                text = await loop.run_in_executor(
                    None,
                    lambda: self._provider.generate(prompt, modelo, options),
                )
                if isinstance(text, str) and text.startswith("Error: "):
                    raise ProviderError(text, provider=self._name, status_code=502)
                if text:
                    yield _chunk_delta(modelo, {"content": text}, None)
                chunks += 1
            yield _chunk_fin(modelo, usage if chunks else {})
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e), provider=self._name, status_code=502) from e

    async def health(self) -> dict:
        return self._provider.health()


def _chunk_delta(modelo: str, delta: dict, finish_reason: str | None) -> dict:
    return {
        "id": f"mochila-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": modelo,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def _chunk_fin(modelo: str, usage: dict) -> dict:
    return {
        "id": f"mochila-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": modelo,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
            "completion_tokens": usage.get("completion_tokens", 0) or 0,
            "total_tokens": usage.get("total_tokens", 0) or 0,
        },
    }

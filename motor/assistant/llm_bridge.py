"""LLM integration bridge — conecta ConversationEngine con Model Router."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from motor.assistant.config import config as app_config
from motor.assistant.models import ConversationMode

if TYPE_CHECKING:
    from motor.assistant.conversation import ConversationEngine


class LLMBridge:
    """Puente entre ConversationEngine y el Model Router / LLM providers.

    Estrategia multi-modelo:
      - conversacion: modelo rápido y ligero (7B)
      - trabajo: modelo de código (14B-32B)
      - explicacion: modelo de razonamiento profundo (32B+)
    """

    def __init__(
        self,
        engine: ConversationEngine,
        router: Any | None = None,
        fallback_model: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self._engine = engine
        self._router = router
        self._fallback = fallback_model or app_config.llm_model_fast
        self._timeout = timeout_seconds or app_config.llm_timeout

    def build_messages(
        self,
        conversation_id: str,
        system_prompt: str = "",
        user_message: str = "",
        max_context: int = 4096,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        ctx = self._engine.get_context(conversation_id)
        token_estimate = 0
        for msg in reversed(ctx):
            cost = len(msg.content) // 4 + 1
            if token_estimate + cost > max_context:
                break
            messages.insert(1 if system_prompt else 0, {
                "role": msg.role, "content": msg.content,
            })
            token_estimate += cost

        if user_message:
            last_ctx = ctx[-1] if ctx else None
            if last_ctx is None or last_ctx.content != user_message:
                messages.append({"role": "user", "content": user_message})

        return messages

    def select_model(self, mode: ConversationMode, intent_value: str = "") -> str:
        if mode == ConversationMode.EXPLANATION:
            return self._fallback
        if mode == ConversationMode.WORK:
            return "qwen2.5-coder:14b"
        if intent_value in ("command", "search"):
            return "qwen2.5:7b"
        return self._fallback

    async def generate_async(
        self,
        conversation_id: str,
        user_message: str,
        mode: ConversationMode,
        intent_value: str = "",
        system_prompt: str = "",
    ) -> str:
        import asyncio
        return await asyncio.to_thread(
            self.generate, conversation_id, user_message,
            mode, intent_value, system_prompt,
        )

    async def generate_stream(
        self,
        conversation_id: str,
        user_message: str,
        mode: ConversationMode,
        intent_value: str = "",
        system_prompt: str = "",
    ):
        import httpx

        model_key = self.select_model(mode, intent_value)
        messages = self.build_messages(
            conversation_id, system_prompt, user_message,
        )
        prompt = self._messages_to_prompt(messages)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client, client.stream(
                "POST",
                "http://localhost:11434/api/generate",
                json={"model": model_key, "prompt": prompt, "stream": True},
            ) as response:
                full = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    import json
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            full += token
                            yield token
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
                yield full
        except Exception as exc:
            yield f"[Error de streaming: {exc}]"

    def generate(
        self,
        conversation_id: str,
        user_message: str,
        mode: ConversationMode,
        intent_value: str = "",
        system_prompt: str = "",
    ) -> str:
        import concurrent.futures

        model_key = self.select_model(mode, intent_value)
        messages = self.build_messages(
            conversation_id, system_prompt, user_message,
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._do_generate, messages, model_key)
            try:
                return future.result(timeout=self._timeout)
            except concurrent.futures.TimeoutError:
                return "[Error: LLM no respondió en el tiempo límite]"
            except Exception:
                return self._local_generate(messages, model_key)

    def _do_generate(self, messages: list[dict[str, str]], model_key: str) -> str:
        if self._router is not None:
            try:
                prompt = self._messages_to_prompt(messages)
                response = self._router.generate(prompt, model=model_key)
                if response and not response.startswith("[Error"):
                    return str(response)
            except Exception:  # noqa: S110
                pass
        return self._local_generate(messages, model_key)

    def _local_generate(self, messages: list[dict[str, str]], model_key: str) -> str:
        try:
            from motor.core.llm.ollama import OllamaProvider
            provider = OllamaProvider()
            prompt = self._messages_to_prompt(messages)
            return provider.generate(prompt, model=model_key)
        except Exception as exc:
            return f"[Error al conectar con LLM: {exc}]"

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for msg in messages:
            role_prefix = (
                "System: " if msg["role"] == "system"
                else "User: " if msg["role"] == "user"
                else "Assistant: "
            )
            parts.append(f"{role_prefix}{msg['content']}")
        parts.append("Assistant: ")
        return "\n".join(parts)

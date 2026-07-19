"""LLM integration bridge — conecta ConversationEngine con Model Router."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
        fallback_model: str = "qwen2.5:7b",
        timeout_seconds: int = 30,
    ):
        self._engine = engine
        self._router = router
        self._fallback = fallback_model
        self._timeout = timeout_seconds

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
            messages.append({"role": "user", "content": user_message})

        return messages

    def select_model(self, mode: ConversationMode, intent_value: str = "") -> str:
        if mode == ConversationMode.EXPLANATION:
            return "razonamiento"
        if mode == ConversationMode.WORK:
            return "codigo_complejo"
        if intent_value in ("command", "search"):
            return "codigo_rapido"
        return "respuesta_rapida"

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
    ) -> str:
        import asyncio
        return await asyncio.to_thread(
            self.generate, conversation_id, user_message,
            mode, intent_value, system_prompt,
        )

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
                response = self._router.generate(messages, task=model_key)
                if response:
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

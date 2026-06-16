import json
from typing import AsyncGenerator


import httpx


from .base import Provider, ProviderError


# OLLAMA_BASE is http://127.0.0.1:11434

OLLAMA_TIMEOUT = 180

OLLAMA_HTTPX_KW: dict = {}


class OllamaProvider(Provider):
    @property
    def nombre(self) -> str:
        return "ollama"

    @property
    def timeout(self) -> int:
        return OLLAMA_TIMEOUT

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        payload = {
            "model": modelo,
            "messages": mensajes,
            "stream": stream,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(**OLLAMA_HTTPX_KW, timeout=httpx.Timeout(self.timeout)) as client:
            if stream:
                async with client.stream(
                    "POST", "http://127.0.0.1:11434/api/chat", json=payload
                ) as resp:
                    if resp.is_error:
                        text = await resp.aread()
                        raise ProviderError(
                            f"Ollama error: {resp.status_code} {text.decode(errors='replace')[:200]}",
                            provider=self.nombre,
                            status_code=resp.status_code,
                        )
                    async for line in resp.aiter_lines():
                        if line.strip():
                            chunk = json.loads(line)
                            yield self._to_openai_chunk(chunk, modelo)
                    return

            resp = await client.post(
                "http://127.0.0.1:11434/api/chat", json=payload
            )
            if resp.is_error:
                raise ProviderError(
                    f"Ollama error: {resp.status_code} {resp.text[:200]}",
                    provider=self.nombre,
                    status_code=resp.status_code,
                )
            yield self._to_openai(resp.json(), modelo)

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(**OLLAMA_HTTPX_KW, timeout=5) as client:
                resp = await client.get("http://127.0.0.1:11434/api/tags")
                if resp.is_error:
                    return {"status": "error", "detail": resp.text[:100]}
                modelos = resp.json().get("models", [])
                return {
                    "status": "ok",
                    "modelos_disponibles": [m["name"] for m in modelos],
                    "latencia_ms": resp.elapsed.total_seconds() * 1000,
                }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    @staticmethod
    def _to_openai_chunk(chunk: dict, modelo: str) -> dict:
        done = chunk.get("done", False)
        msg = chunk.get("message", {})
        content = msg.get("content", "")
        delta: dict[str, object] = {}
        if msg.get("role"):
            delta["role"] = msg.get("role")
        if msg.get("tool_calls"):
            delta["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"].get("arguments", "{}") if isinstance(tc["function"].get("arguments"), str) else json.dumps(tc["function"]["arguments"], ensure_ascii=False),
                    },
                }
                for i, tc in enumerate(msg["tool_calls"])
            ]
        elif content and isinstance(content, str):
            extraido = OllamaProvider._extraer_tool_call(content)
            if extraido:
                delta["tool_calls"] = extraido
                delta["content"] = None
            elif content:
                delta["content"] = content
        if not delta and not done:
            return {}
        tiene_tc = "tool_calls" in delta
        finish = "tool_calls" if tiene_tc else ("stop" if done else None)
        return {
            "id": chunk.get("id", "ollama-unknown"),
            "object": "chat.completion.chunk",
            "created": chunk.get("created_at", ""),
            "model": modelo,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            if done
            else None,
        }

    @staticmethod
    def _extraer_tool_call(content: str) -> list | None:
        try:
            obj = json.loads(content) if isinstance(content, str) else None
            if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                args = obj["arguments"]
                return [{
                    "id": "call_0",
                    "type": "function",
                    "function": {
                        "name": obj["name"],
                        "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False),
                    },
                }]
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    @staticmethod
    def _to_openai(data: dict, modelo: str) -> dict:
        msg = data.get("message", {})
        content = msg.get("content", "")
        message: dict[str, object] = {
            "role": msg.get("role", "assistant"),
            "content": content,
        }
        if "tool_calls" in msg:
            message["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"].get("arguments", "{}") if isinstance(tc["function"].get("arguments"), str) else json.dumps(tc["function"]["arguments"], ensure_ascii=False),
                    },
                }
                for i, tc in enumerate(msg["tool_calls"])
            ]
        elif content and isinstance(content, str):
            extraido = OllamaProvider._extraer_tool_call(content)
            if extraido:
                message["tool_calls"] = extraido
                message["content"] = ""
        finish = "tool_calls" if message.get("tool_calls") else "stop"
        return {
            "id": data.get("id", "ollama-unknown"),
            "object": "chat.completion",
            "created": data.get("created_at", ""),
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish,
                }
            ],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": (data.get("prompt_eval_count", 0) + data.get("eval_count", 0)),
            },
        }

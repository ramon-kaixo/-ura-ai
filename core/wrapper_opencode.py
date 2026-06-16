import json
import logging
import os
import sys
import time
from typing import Any

import httpx

from core.seguridad.rollback_manager import RollbackManager

logger = logging.getLogger("ura.wrapper")

MOCHILA_URL = os.getenv("MOCHILA_URL", "http://127.0.0.1:4098")
MAX_RETRIES = 3
TEMPS = [0.0, 0.3, 0.6]


class OpenCodeWrapper:
    def __init__(self, repo_path: str | None = None):
        self.rollback = RollbackManager(repo_path=repo_path or "/home/ramon/URA/ura_ia_1972")
        self._http = httpx.AsyncClient(timeout=180.0)

    async def _chat(
        self,
        prompt: str,
        model: str = "ollama/qwen2.5-coder:14b",
        temperature: float = 0.0,
        penalty_context: str = "",
    ) -> dict[str, Any]:
        messages = [
            {"role": "system",
             "content": "Eres un ingeniero de software preciso. "
                        "Genera código COMPLETO y FUNCIONAL. "
                        "Prohibido usar elipsis, 'rest of the code', 'unchanged', "
                        "o cualquier abreviatura que omita lineas."},
            {"role": "user", "content": prompt},
        ]
        if penalty_context:
            messages.append({"role": "system", "content": penalty_context})

        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "force_guardian": True,
            "temperature": temperature,
            "max_tokens": 8192,
        }

        accumulated = ""
        async with self._http.stream(
            "POST", f"{MOCHILA_URL}/v1/chat/completions", json=body
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "error" in chunk:
                            return chunk
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        accumulated += delta
                    except json.JSONDecodeError:
                        continue

        return {"response": accumulated, "choices": [{"message": {"content": accumulated}}]}

    async def generate_and_apply(
        self,
        target_file: str,
        prompt: str,
        model: str = "ollama/qwen2.5-coder:14b",
        task_id: str = "auto",
    ) -> tuple[bool, str]:
        abs_path = os.path.abspath(target_file)
        rel_path = os.path.relpath(abs_path, self.rollback.repo_path)

        logger.info("[WRAPPER] Inicio generacion para %s (task=%s)", rel_path, task_id)

        self.rollback.pre_write(abs_path)

        penalty = ""
        for attempt in range(MAX_RETRIES):
            temp = TEMPS[attempt]
            logger.info(
                "[WRAPPER] Intento %d/%d temp=%.1f para %s",
                attempt + 1, MAX_RETRIES, temp, rel_path,
            )

            resp = await self._chat(prompt, model=model, temperature=temp, penalty_context=penalty)

            error = resp.get("error", {})
            if error.get("message") == "STREAM_ABORTED_BY_GUARDIAN":
                penalty = error.get("penalty_context", "")
                logger.warning(
                    "[WRAPPER] Intento %d abortado por guardian. Penalty=%s",
                    attempt + 1, penalty[:60],
                )
                continue

            content = (
                resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", resp.get("response", ""))
            )
            if not content.strip():
                logger.warning("[WRAPPER] Intento %d respuesta vacia", attempt + 1)
                continue

            tmp_path = self.rollback.safe_write(abs_path, content)
            logger.info("[WRAPPER] Escritura temporal OK: %s", tmp_path)

            ok = self.rollback.commit_if_valid(abs_path, task_id)
            if ok:
                logger.info("[WRAPPER] Commit exitoso para %s", rel_path)
                return True, content
            else:
                self.rollback.rollback(abs_path)
                logger.error("[WRAPPER] Commit fallido, rollback ejecutado para %s", rel_path)
                return False, ""

        self.rollback.rollback(abs_path)
        msg = f"[WRAPPER] 3 intentos agotados para {rel_path}. Rollback final."
        logger.critical(msg)
        return False, msg

    async def close(self):
        await self._http.aclose()

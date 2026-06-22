import asyncio
import json
import random
import logging
import os
from typing import Any

import httpx

from core.seguridad.rollback_manager import RollbackManager
from core.infra.state_manager import save_checkpoint, load_checkpoint, clear_checkpoint
from sandbox.sandbox_runner import SandboxClient

logger = logging.getLogger("ura.wrapper")

MOCHILA_URL = os.getenv("MOCHILA_URL", "http://127.0.0.1:4098")
MAX_RETRIES = 3
TEMPS = [0.0, 0.3, 0.6]


async def solicitar_inferencia_con_backoff(client, payload: dict, max_retries: int = 5) -> dict:
    """Petición HTTP con backoff exponencial y jitter. Resuelve Tarea 2.5."""
    url = f"{MOCHILA_URL}/v1/chat/completions"
    for intento in range(max_retries):
        try:
            response = await client.post(url, json=payload)
            if response.status_code in (429, 502, 503, 504):
                logger.warning("API saturada (HTTP %s). Aplicando backoff...", response.status_code)
                raise httpx.HTTPStatusError(
                    "Servicio temporalmente indisponible",
                    request=response.request, response=response,
                )
            response.raise_for_status()
            return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if intento == max_retries - 1:
                logger.error("Agotados %d reintentos. Fallo: %s", max_retries, e)
                raise
            base_delay = 2 ** intento
            jitter = random.uniform(0.5, 1.5)
            delay = base_delay * jitter
            logger.info("[Reintento %d/%d] Esperando %.2fs...", intento + 1, max_retries, delay)
            await asyncio.sleep(delay)


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
        attempt: int = 1,
    ) -> dict[str, Any]:
        system_msg = (
            "Eres un ingeniero de software preciso. "
            "Genera codigo COMPLETO y FUNCIONAL. "
            "Prohibido usar elipsis, 'rest of the code', 'unchanged', "
            "o cualquier abreviatura que omita lineas."
        )
        if attempt > 1:
            system_msg += (
                "\n\n[SYSTEM: RESPUESTA RECHAZADA. PLANIFICA LA SOLUCION "
                "PASO A PASO ANTES DE ESCRIBIR CODIGO (CoT) Y EVITA "
                "CODIGO ESPAGUETI.]"
            )
        messages = [
            {"role": "system", "content": system_msg},
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

        checkpoint = load_checkpoint()
        if checkpoint and checkpoint.get("target_file") == abs_path:
            logger.info("[WRAPPER] Checkpoint encontrado, reanudando task=%s attempt=%d",
                         checkpoint.get("task_id"), checkpoint.get("attempt", 1))

        logger.info("[WRAPPER] Inicio generacion para %s (task=%s)", rel_path, task_id)

        self.rollback.pre_write(abs_path)

        penalty = ""
        for attempt in range(MAX_RETRIES):
            temp = TEMPS[attempt]
            logger.info(
                "[WRAPPER] Intento %d/%d temp=%.1f para %s",
                attempt + 1, MAX_RETRIES, temp, rel_path,
            )

            resp = await self._chat(prompt, model=model, temperature=temp, penalty_context=penalty, attempt=attempt)

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

            save_checkpoint(task_id, abs_path, content, attempt + 1)
            tmp_path = self.rollback.safe_write(abs_path, content)
            logger.info("[WRAPPER] Escritura temporal OK: %s", tmp_path)

            try:
                sandbox = SandboxClient()
                sandbox_result = sandbox.run_validation(tmp_path, rel_path, model=model)
                if not sandbox_result.get("passed", False):
                    logger.error(
                        "[WRAPPER] Sandbox rechazo para %s: %s",
                        rel_path, sandbox_result.get("errors"),
                    )
                    self.rollback.rollback(abs_path)
                    return False, f"Sandbox: {sandbox_result.get('errors', ['unknown'])}"
                logger.info("[WRAPPER] Sandbox OK para %s", rel_path)
            except Exception as e:
                logger.warning("[WRAPPER] Sandbox no disponible, saltando: %s", e)

            ok = self.rollback.commit_if_valid(abs_path, task_id)
            if ok:
                clear_checkpoint()
                logger.info("[WRAPPER] Commit exitoso para %s", rel_path)
                return True, content
            else:
                self.rollback.rollback(abs_path)
                clear_checkpoint()
                logger.error("[WRAPPER] Commit fallido, rollback ejecutado para %s", rel_path)
                return False, ""

        self.rollback.rollback(abs_path)
        clear_checkpoint()
        msg = f"[WRAPPER] 3 intentos agotados para {rel_path}. Rollback final."
        logger.critical(msg)
        return False, msg

    async def close(self):
        await self._http.aclose()

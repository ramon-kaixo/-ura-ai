from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue

log = logging.getLogger("tuneladora.llm_fallback")


LLM_FALLBACK_PROMPT = """Eres experto en Python. Error detectado por {herramienta}:
{error_raw}

Código (5 líneas de contexto alrededor del error):
{code_context}

Genera ÚNICAMENTE un diff patch en formato unified diff (git diff).
NO reescribas el archivo entero. NO expliques nada. Solo el diff."""


class LLMFallback:
    def __init__(self, cfg: Configuration, pending_queue: PendingQueue) -> None:
        self.cfg = cfg
        self.queue = pending_queue
        self._patches_dir = cfg.tuneladora_dir / "patches"
        self._patches_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self, error_raw: str, archivo: str, tool_name: str = "ruff") -> str | None:
        try:
            code_context = self._get_code_context(archivo)
            prompt = LLM_FALLBACK_PROMPT.format(herramienta=tool_name, error_raw=error_raw, code_context=code_context)
            patch = self._call_ollama(prompt, tool_name=tool_name, archivo=archivo)
            if not patch or not patch.strip():
                log.warning("LLM returned empty patch for %s", archivo)
                return None
            patch_path = self._save_patch(archivo, patch)
            log.info("Patch saved: %s", patch_path)
            return patch
        except Exception as e:
            log.error("LLM fallback failed: %s", e)
            return None

    def _get_code_context(self, archivo: str, context_lines: int = 5) -> str:
        path = Path(archivo)
        if not path.exists():
            return ""
        lines = path.read_text().split("\n")
        return "\n".join(lines[: context_lines + 10])

    def _call_ollama(self, prompt: str, tool_name: str = "ruff", archivo: str = "") -> str | None:
        url = f"{self.cfg.ollama_url}/api/generate"

        # Ajustar contexto óptimo para el LLM según tamaño del prompt
        try:
            from scripts.pro import ajustar_contexto as _ajustar_contexto

            tokens_prompt = _ajustar_contexto.estimar_tokens(prompt)
            num_predict = _ajustar_contexto.ajustar_contexto(tokens_prompt, max_modelo=100000, factor_colchon=1.5)
        except Exception:
            num_predict = 200  # fallback conservador

        for attempt in range(1, self.cfg.llm_retries + 2):
            try:
                r = requests.post(
                    url,
                    json={
                        "model": self.cfg.llm_fallback_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": num_predict},
                    },
                    timeout=self.cfg.timeout_llm,
                )
                r.raise_for_status()
                data = r.json()
                return data.get("response", "")
            except requests.Timeout:
                log.warning("LLM timeout (attempt %d/%d)", attempt, self.cfg.llm_retries + 1)
            except requests.RequestException as e:
                log.warning("LLM error (attempt %d/%d): %s", attempt, self.cfg.llm_retries + 1, e)
        self.queue.add(
            archivo=archivo or ".",
            herramienta=tool_name,
            severidad="high",
            error_raw=f"Ollama no responde tras {self.cfg.llm_retries + 1} intentos",
            bloque="llm_fallback",
            estado="imposible",
        )
        return None

    def _save_patch(self, archivo: str, patch: str) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = Path(archivo).name
        patch_path = self._patches_dir / f"{ts}_{fname}.diff"
        patch_path.write_text(patch)
        return patch_path

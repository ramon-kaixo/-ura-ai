#!/usr/bin/env python3
"""
URA OpenClaw Client — N3 Infrastructure (Fase 3, scaffold)

Cliente local para invocar OpenClaw (agente open source que corre en local
contra Ollama). NO realiza llamadas externas de pago. Diseñado para enchufarse
cuando el binario `openclaw` esté instalado en el sistema.

Modos de operación:
  - "subprocess"  → ejecuta `openclaw <args>` y parsea stdout
  - "http"        → habla con un endpoint local (típico: http://127.0.0.1:11434
                    si va vía Ollama directamente, o un puerto propio de openclaw)
  - "stub"        → devuelve respuesta sintética sin llamar a nada (modo de test)

El modo se autodetecta. Si no encuentra binario ni endpoint → "stub".

Salida normalizada (siempre):
    {
        "tema": str,
        "nivel": "N3",
        "estado": "ok" | "stub_noop" | "error",
        "resultados": [ {titulo, url, snippet, fuente, score_relevancia, fecha} ],
        "razonamiento": str | None,        # cadena de pensamiento si openclaw la entrega
        "modelo": str | None,              # nombre del modelo Ollama usado
        "duracion_segundos": float,
        "raw": dict | str | None,          # respuesta cruda (debugging)
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("ura_openclaw_client")

# Configuración por env vars (lo que el usuario podrá cambiar después)
ENV_BIN = "URA_OPENCLAW_BIN"  # ruta al binario openclaw
ENV_HTTP_URL = "URA_OPENCLAW_HTTP"  # ej: http://127.0.0.1:11435
ENV_MODEL = "URA_OPENCLAW_MODEL"  # ej: llama3, qwen2:7b
ENV_TIMEOUT = "URA_OPENCLAW_TIMEOUT"  # segundos
ENV_FORCE_STUB = "URA_OPENCLAW_STUB"  # "1" para forzar stub aunque haya binario

DEFAULT_BIN = "openclaw"
DEFAULT_TIMEOUT_S = 300
DEFAULT_OLLAMA_PORT = 11435


@dataclass
class OpenClawAvailability:
    mode: str  # "subprocess" | "http" | "ollama_direct" | "stub"
    binary_path: str | None = None
    http_url: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "binary_path": self.binary_path,
            "http_url": self.http_url,
            "reason": self.reason,
        }


def detect_openclaw() -> OpenClawAvailability:
    """Decide qué modo usar según el entorno."""
    if os.environ.get(ENV_FORCE_STUB) == "1":
        return OpenClawAvailability(mode="stub", reason="forzado por URA_OPENCLAW_STUB=1")

    http_url = os.environ.get(ENV_HTTP_URL)
    if http_url:
        return OpenClawAvailability(mode="http", http_url=http_url, reason="env URA_OPENCLAW_HTTP")

    # Verificar si Ollama directo está disponible (puerto 11434 - URA principal)
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result_ollama = sock.connect_ex(("127.0.0.1", 11434))
    sock.close()

    if result_ollama == 0:
        # Ollama directo está disponible - usar cliente directo
        return OpenClawAvailability(
            mode="ollama_direct", reason="Ollama directo disponible en puerto 11434"
        )

    # Si no hay Ollama directo, verificar puerto separado para OpenClaw
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", DEFAULT_OLLAMA_PORT))
    sock.close()

    if result == 0:
        # Ollama está corriendo en el puerto separado
        return OpenClawAvailability(
            mode="http",
            http_url=f"http://127.0.0.1:{DEFAULT_OLLAMA_PORT}",
            reason=f"OpenClaw Ollama en puerto separado {DEFAULT_OLLAMA_PORT}",
        )
    else:
        # Ollama no está corriendo en el puerto separado, intentar con subprocess
        bin_env = os.environ.get(ENV_BIN)
        if bin_env and os.path.isfile(bin_env) and os.access(bin_env, os.X_OK):
            return OpenClawAvailability(
                mode="subprocess",
                binary_path=bin_env,
                reason="env URA_OPENCLAW_BIN (Ollama separado no disponible)",
            )

        found = shutil.which(DEFAULT_BIN)
        if found:
            return OpenClawAvailability(
                mode="subprocess",
                binary_path=found,
                reason=f"PATH: {found} (Ollama separado no disponible)",
            )

        return OpenClawAvailability(
            mode="stub",
            reason="Ollama directo no disponible, Ollama separado no disponible y no se encontró binario openclaw",
        )


class OpenClawClient:
    """Cliente async que invoca OpenClaw localmente."""

    def __init__(
        self,
        *,
        availability: OpenClawAvailability | None = None,
        model: str | None = None,
        timeout_s: int | None = None,
    ) -> None:
        self.availability = availability or detect_openclaw()
        self.model = model or os.environ.get(ENV_MODEL)
        self.timeout_s = timeout_s or int(os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT_S))

    @property
    def mode(self) -> str:
        return self.availability.mode

    @property
    def is_real(self) -> bool:
        return self.availability.mode in ("subprocess", "http", "ollama_direct")

    # -------------------------------------------------------------- API ---

    async def search(self, tema: str, *, contexto: str | None = None) -> dict[str, Any]:
        """Ejecuta búsqueda en OpenClaw con logging detallado y tracking para URA."""
        start = time.monotonic()
        search_id = f"openclaw_{int(start * 1000)}"

        # Registrar operación en tracker para URA
        try:
            from core.openclaw_tracker import get_openclaw_tracker

            tracker = get_openclaw_tracker()
            tracker.start_operation(
                search_id, tema, self.mode, self.model, self.availability.reason
            )
        except ImportError:
            tracker = None

        logger.info(
            f"[{search_id}] OpenClaw search iniciado - tema: {tema[:50]}... modo: {self.mode}"
        )
        logger.info(
            f"[{search_id}] Configuración - modelo: {self.model}, timeout: {self.timeout_s}s, availability: {self.availability.reason}"
        )

        try:
            if self.availability.mode == "subprocess":
                logger.info(f"[{search_id}] Ejecutando en modo subprocess")
                payload = await self._run_subprocess(tema, contexto)
            elif self.availability.mode == "http":
                logger.info(
                    f"[{search_id}] Ejecutando en modo HTTP - URL: {self.availability.http_url}"
                )
                payload = await self._run_http(tema, contexto)
            elif self.availability.mode == "ollama_direct":
                logger.info(f"[{search_id}] Ejecutando en modo Ollama directo")
                payload = await self._run_ollama_direct(tema, contexto)
            else:
                logger.info(f"[{search_id}] Ejecutando en modo stub")
                payload = self._stub_response(tema)

            logger.info(
                f"[{search_id}] OpenClaw search completado - estado: {payload.get('estado')}, resultados: {len(payload.get('resultados', []))}"
            )
        except TimeoutError:
            logger.error(f"[{search_id}] OpenClaw timeout después de {self.timeout_s}s")
            payload = {
                "tema": tema,
                "nivel": "N3",
                "estado": "error",
                "resultados": [],
                "razonamiento": None,
                "modelo": self.model,
                "raw": None,
                "error": f"timeout {self.timeout_s}s",
            }
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{search_id}] OpenClaw error: {type(e).__name__}: {e}", exc_info=True)
            payload = {
                "tema": tema,
                "nivel": "N3",
                "estado": "error",
                "resultados": [],
                "razonamiento": None,
                "modelo": self.model,
                "raw": None,
                "error": f"{type(e).__name__}: {e}",
            }

        payload["duracion_segundos"] = round(time.monotonic() - start, 3)
        payload.setdefault("nivel", "N3")
        payload.setdefault("modelo", self.model)
        payload["search_id"] = search_id
        payload["openclaw_mode"] = self.mode
        payload["openclaw_availability"] = self.availability.reason

        # Completar operación en tracker
        if tracker:
            tracker.complete_operation(
                search_id,
                payload.get("estado", "unknown"),
                payload["duracion_segundos"],
                len(payload.get("resultados", [])),
                payload.get("error"),
            )

        logger.info(
            f"[{search_id}] Resultado final - duración: {payload['duracion_segundos']}s, nivel: {payload['nivel']}"
        )
        return payload

    # ------------------------------------------------------- subprocess ---

    async def _run_subprocess(self, tema: str, contexto: str | None) -> dict[str, Any]:
        bin_path = self.availability.binary_path or DEFAULT_BIN
        # Comando convencional: openclaw agent --agent main --message "<tema>" --json
        # --agent main usa el agente por defecto configurado en OpenClaw
        args = [bin_path, "agent", "--agent", "main", "--message", tema, "--json"]
        if contexto:
            args += ["--context", contexto]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(f"No se pudo ejecutar openclaw ({bin_path}): {e}") from e
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_s)
        except TimeoutError:
            proc.kill()
            raise

        if proc.returncode != 0:
            raise RuntimeError(
                f"openclaw exit={proc.returncode}: {stderr_b.decode(errors='ignore')[:500]}"
            )

        out_text = stdout_b.decode(errors="ignore").strip()
        try:
            raw = json.loads(out_text) if out_text else {}
        except json.JSONDecodeError:
            raw = {"text": out_text}

        return self._normalize(tema, raw)

    # -------------------------------------------------------------- http ---

    async def _run_http(self, tema: str, contexto: str | None) -> dict[str, Any]:
        try:
            import aiohttp  # type: ignore
        except ImportError as e:
            raise RuntimeError("aiohttp no instalado para modo HTTP") from e

        url = self.availability.http_url or ""
        body = {
            "tema": tema,
            "context": contexto,
            "model": self.model,
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=body) as resp:
                if resp.status >= 400:
                    err = await resp.text()
                    raise RuntimeError(f"openclaw HTTP {resp.status}: {err[:200]}")
                raw = await resp.json(content_type=None)
        return self._normalize(tema, raw)

    # ---------------------------------------------------------- ollama_direct ---

    async def _run_ollama_direct(self, tema: str, contexto: str | None) -> dict[str, Any]:
        """Usa cliente directo a Ollama para N3."""
        try:
            from core.ollama_n3_client import OllamaN3Client
        except ImportError as e:
            raise RuntimeError("ollama_n3_client no disponible") from e

        model_to_use = self.model or "llama3.2:latest"

        # Construir prompt con contexto si existe
        prompt = tema
        if contexto:
            prompt = f"Contexto: {contexto}\n\nPregunta: {tema}"

        # Usar context manager para asegurar cierre de sesión
        async with OllamaN3Client() as client:
            result = await client.search(query=prompt, model=model_to_use, max_tokens=2000)

        if not result.success:
            raise RuntimeError(f"Ollama directo falló: {result.error}")

        # Normalizar respuesta al formato URA
        raw = {"text": result.response, "model": result.model, "tokens": result.tokens}

        return self._normalize(tema, raw)

    # -------------------------------------------------------------- stub --

    def _stub_response(self, tema: str) -> dict[str, Any]:
        return {
            "tema": tema,
            "nivel": "N3",
            "estado": "stub_noop",
            "resultados": [],
            "razonamiento": (
                "OpenClaw no está instalado. Modo stub: ningún razonamiento real generado. "
                "Configura URA_OPENCLAW_BIN o URA_OPENCLAW_HTTP para activar N3."
            ),
            "modelo": self.model,
            "raw": None,
        }

    # -------------------------------------------------------- normalize ----

    def _normalize(self, tema: str, raw: Any) -> dict[str, Any]:
        """Convertir la salida cruda de OpenClaw al schema URA estándar."""
        resultados: list[dict[str, Any]] = []
        razonamiento: str | None = None
        modelo: str | None = self.model

        if isinstance(raw, dict):
            razonamiento = raw.get("reasoning") or raw.get("razonamiento") or raw.get("text")
            modelo = raw.get("model") or modelo
            for r in raw.get("results", []) or raw.get("resultados", []) or []:
                if not isinstance(r, dict):
                    continue
                resultados.append(
                    {
                        "titulo": r.get("title") or r.get("titulo") or "",
                        "url": r.get("url") or r.get("link") or "",
                        "snippet": r.get("snippet") or r.get("resumen") or r.get("body") or "",
                        "fuente": r.get("source") or r.get("fuente") or "openclaw",
                        "fecha": r.get("date") or r.get("fecha"),
                        "score_relevancia": float(r.get("score_relevancia", r.get("score", 0.7))),
                    }
                )

        return {
            "tema": tema,
            "nivel": "N3",
            "estado": "ok",
            "resultados": resultados,
            "razonamiento": razonamiento,
            "modelo": modelo,
            "raw": raw if isinstance(raw, dict) else {"text": str(raw)},
        }


# Module-level singleton
_client: OpenClawClient | None = None


def get_openclaw_client() -> OpenClawClient:
    global _client
    if _client is None:
        _client = OpenClawClient()
    return _client


def reset_openclaw_client() -> None:
    """Forzar redetección (útil tras instalar OpenClaw o cambiar env vars)."""
    global _client
    _client = None


def get_openclaw_status() -> dict[str, Any]:
    """
    Retorna el estado actual de OpenClaw para URA.
    URA puede llamar esta función en cualquier momento para saber qué hace OpenClaw.
    """
    try:
        from core.openclaw_tracker import get_openclaw_tracker

        tracker = get_openclaw_tracker()
        status = tracker.get_current_status()
        stats = tracker.get_stats()
        return {
            "status": status,
            "stats": stats,
            "client_mode": get_openclaw_client().mode,
            "client_availability": get_openclaw_client().availability.to_dict(),
        }
    except ImportError:
        return {
            "status": {"status": "tracker_no_disponible"},
            "stats": {"total": 0},
            "client_mode": get_openclaw_client().mode,
            "client_availability": get_openclaw_client().availability.to_dict(),
        }

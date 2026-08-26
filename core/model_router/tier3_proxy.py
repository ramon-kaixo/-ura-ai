"""Tier-3 Proxy — Cascada de modelos: OpenCode → Groq → Ollama local.

Intercepta peticiones y las enruta en cascada:
  Nivel 1: OpenCode Account A (Mac) → Account B (GX10)
  Nivel 2: Groq API (Llama 3.3 70B)
  Nivel 3: Ollama local (qwen3-coder:30b)

Detecta HTTP 429 y ejecuta fallback automático con circuit breaker por provider.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN = 4.0
CONTEXT_WARN_TOKENS = 12_000
CONTEXT_CRITICAL_TOKENS = 24_000
MAX_RETRIES_PER_TIER = 3
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_S = 300.0  # 5 min


class ProviderState(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    COOLDOWN = "cooldown"


@dataclass
class ProviderConfig:
    name: str
    tier: int
    url: str
    api_key: str = ""
    model: str = ""
    network: str = "standard"  # "standard" or "tunnel"
    timeout_s: float = 60.0
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ProviderStats:
    name: str
    tier: int
    total_requests: int = 0
    success: int = 0
    failures_429: int = 0
    failures_other: int = 0
    state: ProviderState = ProviderState.HEALTHY
    last_error: str = ""
    last_error_time: float = 0.0
    consecutive_429: int = 0
    consecutive_failures: int = 0
    last_success_time: float = 0.0


# ---------------------------------------------------------------------------
# Circuit Breaker per provider
# ---------------------------------------------------------------------------


class ProviderCircuitBreaker:
    """Circuit breaker que abre tras CIRCUIT_BREAKER_THRESHOLD 429 consecutivos."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self._failure_count = 0
        self._state = ProviderState.HEALTHY
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> ProviderState:
        with self._lock:
            if (
                self._state == ProviderState.COOLDOWN
                and time.monotonic() - self._opened_at > CIRCUIT_BREAKER_RECOVERY_S
            ):
                self._state = ProviderState.HEALTHY
                self._failure_count = 0
                log.info("[CIRCUIT] %s → HEALTHY (recovery timeout)", self.provider_name)
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = ProviderState.HEALTHY

    def record_429(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= CIRCUIT_BREAKER_THRESHOLD:
                self._state = ProviderState.COOLDOWN
                self._opened_at = time.monotonic()
                log.warning(
                    "[CIRCUIT] %s → COOLDOWN (%d 429 consecutivos, recovery %ds)",
                    self.provider_name,
                    self._failure_count,
                    CIRCUIT_BREAKER_RECOVERY_S,
                )

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1

    def is_available(self) -> bool:
        return self.state in (ProviderState.HEALTHY, ProviderState.DEGRADED)

    def reset(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = ProviderState.HEALTHY
            self._opened_at = 0.0


# ---------------------------------------------------------------------------
# Context Bridge — preservación de contexto al cambiar de modelo
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN)


def _build_context_header(
    prev_model: str,
    new_model: str,
    messages: list[dict],
    max_tokens: int = 8000,
) -> list[dict]:
    """Construye un header de contexto para el nuevo modelo.

    Serializa el historial previo en un formato neutro (texto plano)
    compatible con cualquier arquitectura de modelo.
    """
    if not messages:
        return []

    # Extraer system prompt
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    system_text = "\n".join(system_parts) if system_parts else ""

    # Extraer código generado (últimos mensajes con tool_calls o bloques de código)
    code_blocks = []
    for m in reversed(messages):
        content = m.get("content", "")
        if "```" in content or m.get("role") == "assistant":
            code_blocks.append(content)
        if len(code_blocks) >= 3:
            break

    # Extraer resumen de fases completadas
    phase_markers = []
    for m in messages:
        content = m.get("content", "")
        if any(kw in content.lower() for kw in ["fase", "phase", "completado", "done", "task-"]):
            phase_markers.append(content[:200])

    # Construir header neutro
    header_parts = [
        "[CONTEXT_TRANSFER]",
        f"Modelo anterior: {prev_model}",
        f"Modelo actual: {new_model}",
        f"Histórico de la sesión: {len(messages)} mensajes",
        "",
    ]

    if system_text:
        truncated_system = system_text[:2000]
        header_parts.extend(["## Instrucciones del sistema:", truncated_system, ""])

    if phase_markers:
        header_parts.append("## Fases/completados recientes:")
        for pm in phase_markers[-5:]:
            header_parts.append(f"- {pm[:150]}")
        header_parts.append("")

    if code_blocks:
        header_parts.append("## Código generado reciente:")
        for cb in reversed(code_blocks):
            truncated = cb[:3000]
            header_parts.append(f"```\n{truncated}\n```")
        header_parts.append("")

    header_parts.append("[FIN CONTEXT_TRANSFER — Continúa desde donde se quedó]")

    header_text = "\n".join(header_parts)

    # Token budget check
    header_tokens = _estimate_tokens(header_text)
    if header_tokens > max_tokens:
        # Truncar agresivamente
        max_chars = max_tokens * CHARS_PER_TOKEN
        header_text = header_text[: int(max_chars)]
        log.warning("[CONTEXT_BRIDGE] Header truncado a %d tokens (original: %d)", max_tokens, header_tokens)

    return [{"role": "system", "content": header_text}]


# ---------------------------------------------------------------------------
# Tier-3 Proxy
# ---------------------------------------------------------------------------


class Tier3Proxy:
    """Proxy con cascada de 3 niveles y fallback automático."""

    def __init__(self, config_path: str | None = None) -> None:
        self._providers: list[ProviderConfig] = []
        self._breakers: dict[str, ProviderCircuitBreaker] = {}
        self._stats: dict[str, ProviderStats] = {}
        self._last_tier_used: int = 0
        self._prev_model: str = ""
        self._lock = threading.Lock()

        if config_path and Path(config_path).exists():
            self._load_config(config_path)
        else:
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Carga configuración por defecto desde variables de entorno."""
        # Tier 1: OpenCode accounts
        opencode_url = os.environ.get("OPENCODE_API_URL", "http://localhost:8081")
        opencode_key_a = os.environ.get("OPENCODE_API_KEY_A", "")
        opencode_key_b = os.environ.get("OPENCODE_API_KEY_B", "")

        if opencode_key_a:
            self._providers.append(
                ProviderConfig(
                    name="opencode-a",
                    tier=1,
                    url=opencode_url,
                    api_key=opencode_key_a,
                    model="qwen3-coder:30b",
                    network="standard",
                    timeout_s=120.0,
                )
            )
        if opencode_key_b:
            self._providers.append(
                ProviderConfig(
                    name="opencode-b",
                    tier=1,
                    url=opencode_url,
                    api_key=opencode_key_b,
                    model="qwen3-coder:30b",
                    network="tunnel",
                    timeout_s=120.0,
                )
            )

        # Tier 2: Groq
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            self._providers.append(
                ProviderConfig(
                    name="groq",
                    tier=2,
                    url="https://api.groq.com/openai/v1",
                    api_key=groq_key,
                    model="llama-3.3-70b-versatile",
                    timeout_s=30.0,
                    headers={"Authorization": f"Bearer {groq_key}"},
                )
            )

        # Tier 3: Ollama local (GX10)
        ollama_url = os.environ.get("OLLAMA_LOCAL_URL", "http://100.72.103.12:11434")
        self._providers.append(
            ProviderConfig(
                name="ollama-local",
                tier=3,
                url=ollama_url,
                model="qwen3-coder:30b",
                timeout_s=120.0,
            )
        )

        for p in self._providers:
            self._breakers[p.name] = ProviderCircuitBreaker(p.name)
            self._stats[p.name] = ProviderStats(name=p.name, tier=p.tier)

        log.info(
            "[TIER3] %d providers configurados: %s",
            len(self._providers),
            [f"{p.name}(T{p.tier})" for p in self._providers],
        )

    def _load_config(self, path: str) -> None:
        """Carga configuración desde JSON."""
        with Path(path).open() as f:
            cfg = json.load(f)
        for p_cfg in cfg.get("providers", []):
            p = ProviderConfig(**p_cfg)
            self._providers.append(p)
            self._breakers[p.name] = ProviderCircuitBreaker(p.name)
            self._stats[p.name] = ProviderStats(name=p.name, tier=p.tier)

    def _try_provider(
        self, provider: ProviderConfig, path: str, body: bytes | None, method: str = "POST"
    ) -> tuple[int, dict, bytes]:
        """Intenta una petición a un provider específico."""
        url = f"{provider.url}{path}"
        headers = {"Content-Type": "application/json"}
        headers.update(provider.headers)

        req = urllib.request.Request(  # noqa: S310
            url,
            data=body if method == "POST" else None,
            method=method,
        )
        for k, v in headers.items():
            req.add_header(k, v)

        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=provider.timeout_s) as resp:  # noqa: S310
                latency = time.monotonic() - start
                data = resp.read()
                log.info(
                    "[TIER3] %s → OK (%d) en %.1fs",
                    provider.name,
                    resp.status,
                    latency,
                )
                return resp.status, dict(resp.headers), data

        except urllib.error.HTTPError as e:
            latency = time.monotonic() - start
            error_body = e.read()
            if e.code == 429:
                self._breakers[provider.name].record_429()
                self._stats[provider.name].failures_429 += 1
                self._stats[provider.name].consecutive_429 += 1
                log.warning(
                    "[TIER3] %s → 429 Rate Limit (%.1fs) consecutivo=%d",
                    provider.name,
                    latency,
                    self._stats[provider.name].consecutive_429,
                )
            else:
                self._breakers[provider.name].record_failure()
                self._stats[provider.name].failures_other += 1
                self._stats[provider.name].consecutive_failures += 1
                log.warning("[TIER3] %s → HTTP %d (%.1fs)", provider.name, e.code, latency)

            self._stats[provider.name].last_error = f"HTTP {e.code}"
            self._stats[provider.name].last_error_time = time.time()
            return e.code, {}, error_body

        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            self._breakers[provider.name].record_failure()
            self._stats[provider.name].failures_other += 1
            self._stats[provider.name].consecutive_failures += 1
            self._stats[provider.name].last_error = str(e)
            self._stats[provider.name].last_error_time = time.time()
            log.warning("[TIER3] %s → %s", provider.name, type(e).__name__)
            return 503, {}, json.dumps({"error": str(e)}).encode()

    def _inject_context_if_needed(self, data: dict, prev_model: str, new_model: str) -> dict:
        """Inyecta context bridge si hubo cambio de modelo."""
        if not prev_model or prev_model == new_model:
            return data

        # Normalize model names for comparison
        prev_arch = self._extract_arch(prev_model)
        new_arch = self._extract_arch(new_model)

        if prev_arch == new_arch:
            return data  # Same architecture, no bridge needed

        messages = data.get("messages", [])
        if messages:
            context_header = _build_context_header(prev_model, new_model, messages)
            data["messages"] = context_header + messages
            log.info(
                "[CONTEXT_BRIDGE] %s → %s: +%d mensajes de contexto",
                prev_model,
                new_model,
                len(context_header),
            )
        return data

    def _extract_arch(self, model_name: str) -> str:
        """Extrae la arquitectura base del nombre del modelo."""
        name = model_name.lower()
        if "qwen" in name:
            return "qwen"
        if "llama" in name or "groq" in name:
            return "llama"
        if "gemma" in name:
            return "gemma"
        if "nemotron" in name:
            return "nemotron"
        return "unknown"

    def proxy(self, path: str, body: bytes | None, method: str = "POST") -> tuple[int, dict, bytes]:
        """Envía petición con cascada tier-3. Retorna (status, headers, body)."""
        data = {}
        if body:
            with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
                data = json.loads(body)

        model = data.get("model", "")

        # Group providers by tier
        tiers: dict[int, list[ProviderConfig]] = {}
        for p in self._providers:
            tiers.setdefault(p.tier, []).append(p)

        last_status = 503
        last_headers: dict = {}
        last_body = b'{"error": "all providers failed"}'

        for tier_num in sorted(tiers.keys()):
            providers = tiers[tier_num]
            for provider in providers:
                if not self._breakers[provider.name].is_available():
                    log.debug("[TIER3] %s skip (circuit breaker OPEN)", provider.name)
                    continue

                # Set model for provider
                if provider.model:
                    data["model"] = provider.model
                    body_to_send = json.dumps(data).encode()

                status, headers, resp_body = self._try_provider(provider, path, body_to_send, method)

                if status == 200:
                    # Success — record and return
                    self._stats[provider.name].success += 1
                    self._stats[provider.name].total_requests += 1
                    self._stats[provider.name].consecutive_429 = 0
                    self._stats[provider.name].consecutive_failures = 0
                    self._stats[provider.name].last_success_time = time.time()
                    self._breakers[provider.name].record_success()

                    with self._lock:
                        self._prev_model = model or provider.model
                        self._last_tier_used = tier_num

                    log.info(
                        "[TIER3] ✓ %s (Tier %d) resolvió la petición",
                        provider.name,
                        tier_num,
                    )
                    return status, headers, resp_body

                # Failed — try next provider in same tier
                last_status = status
                last_headers = headers
                last_body = resp_body
                self._stats[provider.name].total_requests += 1

            # If all providers in this tier failed with 429, try next tier
            tier_429_count = sum(1 for p in providers if self._stats[p.name].consecutive_429 > 0)
            if tier_429_count == len(providers):
                log.warning(
                    "[TIER3] Tier %d agotado (todos en 429), bajando a Tier %d",
                    tier_num,
                    tier_num + 1,
                )

        log.error("[TIER3] Todos los providers fallaron")
        return last_status, last_headers, last_body

    def health(self) -> dict[str, Any]:
        """Estado del proxy y todos los providers."""
        providers_health = []
        for p in self._providers:
            stats = self._stats[p.name]
            breaker = self._breakers[p.name]
            providers_health.append(
                {
                    "name": p.name,
                    "tier": p.tier,
                    "state": breaker.state.value,
                    "total_requests": stats.total_requests,
                    "success": stats.success,
                    "failures_429": stats.failures_429,
                    "failures_other": stats.failures_other,
                    "last_error": stats.last_error,
                    "consecutive_429": stats.consecutive_429,
                }
            )
        return {
            "status": "ok" if any(s["state"] == "healthy" for s in providers_health) else "degraded",
            "last_tier_used": self._last_tier_used,
            "prev_model": self._prev_model,
            "providers": providers_health,
        }

    def reset_all(self) -> None:
        """Resetea todos los circuit breakers."""
        for cb in self._breakers.values():
            cb.reset()
        log.info("[TIER3] Todos los circuit breakers reseteados")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_proxy_instance: Tier3Proxy | None = None
_proxy_lock = threading.Lock()


def get_tier3_proxy(config_path: str | None = None) -> Tier3Proxy:
    global _proxy_instance  # noqa: PLW0603
    with _proxy_lock:
        if _proxy_instance is None:
            _proxy_instance = Tier3Proxy(config_path)
        return _proxy_instance

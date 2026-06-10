import json
import os
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderHealth:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    consecutive_failures: int = 0


def _health_file() -> Path:
    return Path(os.environ.get("MOCHILA_HEALTH_FILE", str(Path.home() / ".nervioso" / "provider_health.json")))


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 2,
        health_file: Path | None = None,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests
        self._health_file = health_file or _health_file()
        self._health: dict[str, ProviderHealth] = {}
        self._caragar()

    def _caragar(self) -> None:
        if self._health_file.exists():
            try:
                with open(self._health_file) as f:
                    raw = json.load(f)
                for provider, data in raw.items():
                    if data.get("state") in ("closed", "open", "half_open"):
                        self._health[provider] = ProviderHealth(
                            state=CircuitState(data["state"]),
                            failure_count=data.get("failure_count", 0),
                            success_count=data.get("success_count", 0),
                            last_failure_time=data.get("last_failure_time", 0.0),
                            last_success_time=data.get("last_success_time", 0.0),
                            consecutive_failures=data.get("consecutive_failures", 0),
                        )
            except (json.JSONDecodeError, KeyError, OSError):
                pass

    def _persistir(self) -> None:
        raw = {p: asdict(h) for p, h in self._health.items()}
        for p, d in raw.items():
            d["state"] = d["state"].value if isinstance(d["state"], CircuitState) else d["state"]
        tmp = self._health_file.with_suffix(".tmp")
        self._health_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(raw, f, indent=2)
        tmp.replace(self._health_file)

    def _health_por_provider(self, provider: str) -> ProviderHealth:
        if provider not in self._health:
            self._health[provider] = ProviderHealth()
        return self._health[provider]

    def puede_pasar(self, provider: str) -> bool:
        h = self._health_por_provider(provider)
        if h.state == CircuitState.CLOSED:
            return True
        if h.state == CircuitState.OPEN:
            if time.time() - h.last_failure_time >= self.recovery_timeout:
                h.state = CircuitState.HALF_OPEN
                self._persistir()
                return True
            return False
        if h.state == CircuitState.HALF_OPEN:
            return h.success_count + h.failure_count < self.half_open_max_requests
        return True

    def registrar_exito(self, provider: str) -> None:
        h = self._health_por_provider(provider)
        h.success_count += 1
        h.last_success_time = time.time()
        h.consecutive_failures = 0
        if h.state == CircuitState.HALF_OPEN:
            h.state = CircuitState.CLOSED
            h.failure_count = 0
        self._persistir()

    def registrar_fallo(self, provider: str, es_timeout: bool = False) -> None:
        h = self._health_por_provider(provider)
        h.failure_count += 1
        h.last_failure_time = time.time()
        h.consecutive_failures += 1
        if h.state == CircuitState.HALF_OPEN:
            h.state = CircuitState.OPEN
            h.last_failure_time = time.time()
        elif h.state == CircuitState.CLOSED and h.consecutive_failures >= self.failure_threshold:
            h.state = CircuitState.OPEN
        self._persistir()

    def estado(self, provider: str) -> dict:
        h = self._health_por_provider(provider)
        return {
            "state": h.state.value,
            "failure_count": h.failure_count,
            "success_count": h.success_count,
            "consecutive_failures": h.consecutive_failures,
            "last_failure_time": h.last_failure_time,
            "last_success_time": h.last_success_time,
        }

    def reset(self, provider: str) -> None:
        if provider in self._health:
            del self._health[provider]
            self._persistir()

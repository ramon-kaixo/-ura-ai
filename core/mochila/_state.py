from dataclasses import dataclass, field

from core.mochila.adapter import _MotorChatAdapter
from core.mochila.circuit_breaker import CircuitBreaker
from core.mochila.cost_tracker import CostTracker
from core.mochila.rate_limiter import RateLimiter
from core.mochila.router import Router
from core.mochila.vram_scheduler import VRAMAwareScheduler


@dataclass
class MochilaState:
    providers: dict[str, _MotorChatAdapter]
    provider_timeouts: dict[str, float]
    cache_models: list = field(default_factory=list)
    cache_models_ts: float = 0.0
    scheduler: VRAMAwareScheduler | None = None
    router: Router | None = None
    circuit_breaker: CircuitBreaker | None = None
    rate_limiter: RateLimiter | None = None
    cost_tracker: CostTracker | None = None


def build_state() -> MochilaState:
    from motor.core.llm.gemini import GeminiProvider as MotorGemini
    from motor.core.llm.ollama import OllamaProvider as MotorOllama
    from motor.core.llm.openrouter import OpenRouterProvider as MotorOpenRouter

    providers = {
        "ollama": _MotorChatAdapter("ollama", MotorOllama()),
        "openrouter": _MotorChatAdapter("openrouter", MotorOpenRouter()),
        "gemini": _MotorChatAdapter("gemini", MotorGemini()),
    }
    provider_timeouts = {
        "ollama": 120.0,
        "openrouter": 60.0,
        "gemini": 30.0,
    }
    scheduler = VRAMAwareScheduler()
    router = Router(providers=providers)
    circuit_breaker = CircuitBreaker()
    rate_limiter = RateLimiter()
    cost_tracker = CostTracker()
    return MochilaState(
        providers=providers,
        provider_timeouts=provider_timeouts,
        scheduler=scheduler,
        router=router,
        circuit_breaker=circuit_breaker,
        rate_limiter=rate_limiter,
        cost_tracker=cost_tracker,
    )

"""Model Router Enhanced — package completo con submódulos."""

from core.model_router.cache import PromptCache, prompt_cache
from core.model_router.cli import main, verificar_politicas_seguridad_preflight
from core.model_router.dashboard import _dashboard_json, _render_dashboard
from core.model_router.handler import RouterHandler
from core.model_router.metrics import MetricsCollector
from core.model_router.metrics import metrics as metrics_singleton
from core.model_router.model_selection import (
    DEFAULT_MODEL_PARAMS,
    MODELO_ROUTES,
    PATRONES_CLASIFICACION,
    _apply_model_params,
    _get_model_params,
    _get_success_rate,
    _record_success,
    clasificar_peticion,
    obtener_modelos_disponibles,
    seleccionar_modelo,
)
from core.model_router.proxy import (
    _CHARS_PER_TOKEN,
    _CONTEXT_SUMMARY_THRESHOLD,
    _CONTEXT_WARN_THRESHOLD,
    _asus_latency_lock,
    _asus_latency_ms,
    _asus_latency_updated,
    _check_context_size,
    _estimate_tokens,
    _fallback_count_last_hour,
    _fallback_lock,
    _fallback_log,
    _get_active_backend_label,
    _is_local_ip,
    _measare_asus_latency,
    _proxy_con_guardia_vram,
    _proxy_con_vram,
    _proxy_request_async,
    _register_fallback,
    _resolve_mode_for_client,
    _resolve_ollama_url,
    _update_asus_latency,
    proxy_request,
)
from core.model_router.router import (
    CACHE_TTL,
    DEFAULT_TIPO,
    FALLBACK_MODEL,
    POWER_MODE,
    ROUTER_PORT,
    auth_validate,
    rate_limiter,
    require_auth,
)
from core.model_router.vram_guard import ConcurrentVRAMGuard
from core.model_router.vram_guard import vram_guard as vram_guard_singleton

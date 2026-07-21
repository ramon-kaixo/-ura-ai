"""Model Router Enhanced — dividido en submódulos con compatibilidad hacia atrás.

Importa desde submódulos (en proceso de extracción) y desde
model_router_main.py (archivo original) para mantener compatibilidad.
"""

from core.model_router.cache import CACHE_TTL, PromptCache, prompt_cache  # noqa: F401
from core.model_router.dashboard import _dashboard_json, _render_dashboard  # noqa: F401
from core.model_router.handler import RouterHandler  # noqa: F401
from core.model_router.metrics import MetricsCollector, metrics  # noqa: F401
from core.model_router.model_selection import (  # noqa: F401
    DEFAULT_MODEL_PARAMS,
    DEFAULT_TIPO,
    FALLBACK_MODEL,
    MODEL_CONFIG,
    MODELO_ROUTES,
    PATRONES_CLASIFICACION,
)
from core.model_router.proxy import (  # noqa: F401
    _check_context_size,
    _fallback_count_last_hour,
    _get_active_backend_label,
    _measare_asus_latency,
    _proxy_con_guardia_vram,
    _proxy_con_vram,
    _proxy_request_async,
    _register_fallback,
    _resolve_mode_for_client,
    _update_asus_latency,
    proxy_request,
)
from core.model_router.vram_guard import ConcurrentVRAMGuard, vram_guard  # noqa: F401
from core.model_router_main import *  # noqa: F403

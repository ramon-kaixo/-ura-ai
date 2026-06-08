# `core/model_router.py`

- **Language:** python
- **Chunks:** 26

## Symbols

### class: `MetricsCollector`
- Line: 226

class MetricsCollector:
Methods: __init__, increment, record_latency, record_error, _make_key, get_prometheus_format

### class: `PromptCache`
- Line: 277

class PromptCache:
Methods: __init__, _hash_content, get, set, clear

### class: `RouterHandler`
- Line: 586

class RouterHandler:
Methods: _get_modelos, do_GET, do_POST, log_message

### function: `_is_local_ip`
- Line: 38

def _is_local_ip(ip):
Detecta si una IP pertenece a la red local.

### function: `_resolve_mode_for_client`
- Line: 50

def _resolve_mode_for_client(client_ip):
Devuelve TURBO o ECO según la IP del cliente y POWER_MODE actual.

POWER_MODE=AUTO  → local=TURBO(ASUS), remoto=ECO(local)
POWER_MODE=TURBO → siempre TURBO (override manual)
POWER_MODE=ECO   → siempre ECO (override manual)

### function: `_resolve_ollama_url`
- Line: 66

def _resolve_ollama_url():
Resuelve URL por defecto (usada en startup y health checks).

### function: `_register_fallback`
- Line: 157

def _register_fallback():

### function: `_fallback_count_last_hour`
- Line: 162

def _fallback_count_last_hour():

### function: `_measare_asus_latency`
- Line: 171

def _measare_asus_latency():

### function: `_update_asus_latency`
- Line: 183

def _update_asus_latency():

### function: `_get_active_backend_label`
- Line: 191

def _get_active_backend_label():

### function: `_estimate_tokens`
- Line: 204

def _estimate_tokens(text):

### function: `_check_context_size`
- Line: 208

def _check_context_size(messages):

### function: `clasificar_peticion`
- Line: 311

def clasificar_peticion(messages):

### function: `obtener_modelos_disponibles`
- Line: 326

def obtener_modelos_disponibles(url):

### function: `_get_model_params`
- Line: 339

def _get_model_params(model_name):

### function: `_apply_model_params`
- Line: 349

def _apply_model_params(data, model_name):

### function: `_record_success`
- Line: 359

def _record_success(modelo, tipo, ok):

### function: `_get_success_rate`
- Line: 367

def _get_success_rate(modelo, tipo):

### function: `seleccionar_modelo`
- Line: 375

def seleccionar_modelo(tipo, disponibles):

### function: `proxy_request`
- Line: 402

def proxy_request(path, body, method, modelo, tipo, client_ip):

### function: `_render_dashboard`
- Line: 529

def _render_dashboard():

### function: `_dashboard_json`
- Line: 562

def _dashboard_json(client_ip):

### function: `main`
- Line: 915

def main():

## Module Overview

Model Router Enhanced - Con prompt caching, fallback system, dashboard y POWER_MODE.

## Imports

```
collections.defaultdict
collections.deque
core.auth_layer.require_auth
core.auth_layer.validate
core.config_manager.get_ollama_urls
core.search_engine.search
hashlib
http.server
http.server.ThreadingHTTPServer
json
logging
os
pathlib.Path
router_rate_limiter.rate_limiter
sys
threading
time
typing.Any
ura_search.indexer.search
urllib.error
urllib.parse
urllib.request
zmq
```

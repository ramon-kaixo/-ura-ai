"""RouterHandler — servidor HTTP para el Model Router."""

from __future__ import annotations

import contextlib
import http.server
import json
import logging
import time

log = logging.getLogger(__name__)


class RouterHandler(http.server.BaseHTTPRequestHandler):
    _modelos_cache: set | None = None
    _cache_ts: float = 0

    @classmethod
    def _get_modelos(cls) -> set:
        if cls._modelos_cache is None:
            cls._modelos_cache = set()
        if time.time() - cls._cache_ts > 300:
            from core.model_router.model_selection import obtener_modelos_disponibles
            cls._modelos_cache = obtener_modelos_disponibles()
            cls._cache_ts = time.time()
        return cls._modelos_cache

    def _send_json(self, data: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_html(self, html: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_text(self, text: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode())

    def _check_rate_limit(self) -> bool:
        from core.model_router.router import rate_limiter
        if not rate_limiter.is_allowed(self.client_address[0]):
            self._send_json({"error": "Rate limit: 100 req/min por IP"}, 429)
            return False
        return True

    def _handle_api_tags(self) -> None:
        from core.model_router.proxy import proxy_request
        status, _headers, body = proxy_request("/api/tags", None, "GET", client_ip=self.client_address[0])
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _handle_api_version(self) -> None:
        from core.model_router import router as _main
        from core.model_router.model_selection import MODELO_ROUTES
        from core.model_router.router import OLLAMA_URL, ROUTER_PORT
        self._send_json(
            {
                "service": "model_router",
                "version": "2.2",
                "ollama": OLLAMA_URL,
                "port": ROUTER_PORT,
                "power_mode": _main.POWER_MODE.upper(),
                "routes": {k: v["descripcion"] for k, v in MODELO_ROUTES.items()},
                "features": [
                    "prompt_caching",
                    "fallback_system",
                    "metrics",
                    "adaptive_routing",
                    "per_model_temperature",
                    "dashboard",
                    "power_mode",
                    "context_checker",
                ],
            },
        )

    def _handle_health(self) -> None:
        from core.model_router import router as _main
        from core.model_router.cache import prompt_cache
        from core.model_router.router import OLLAMA_URL, auth_validate, require_auth
        if require_auth() and not auth_validate(self.headers.get("X-API-KEY")):
            self._send_json({"error": "Forbidden"}, 403)
            return
        disponibles = self._get_modelos()
        ollama_ok = len(disponibles) > 0
        self._send_json(
            {
                "status": "ok" if ollama_ok else "degraded",
                "ollama": "reachable" if ollama_ok else "unreachable",
                "models_available": len(disponibles),
                "ollama_url": OLLAMA_URL,
                "power_mode": _main.POWER_MODE.upper(),
                "cache_size": len(prompt_cache.cache),
                "metrics_enabled": True,
            },
            200 if ollama_ok else 503,
        )

    def _handle_metrics(self) -> None:
        from core.model_router.metrics import metrics
        self._send_text(metrics.get_prometheus_format())

    def _handle_supervisor(self) -> None:
        from core.model_router.router import auth_validate, require_auth
        if require_auth() and not auth_validate(self.headers.get("X-API-KEY")):
            self._send_json({"error": "Forbidden: X-API-KEY inválido o faltante"}, 403)
            return
        supervisor_data = "{}"
        ctx = None
        sock = None
        try:
            import zmq
            ctx = zmq.Context()
            sock = ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, 3000)
            sock.connect("ipc:///tmp/ura-supervisor.ipc")
            sock.send(b"status")
            supervisor_data = sock.recv().decode()
        except Exception as e:
            log.warning(f"Error conectando a supervisor IPC: {e}")
            supervisor_data = json.dumps({"error": "supervisor no accesible"})
        finally:
            if sock:
                with contextlib.suppress(Exception):
                    sock.close()
            if ctx:
                with contextlib.suppress(Exception):
                    ctx.term()
        self._send_json(json.loads(supervisor_data) if isinstance(supervisor_data, str) else supervisor_data)

    def _handle_status(self) -> None:
        html = "<html><head><title>URA System Status</title><meta charset='utf-8'><style>"
        html += "body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}"
        html += "h1{color:#58a6ff}.ok{color:#3fb950}.err{color:#f85149}"
        html += ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}"
        html += ".card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}"
        html += ".card h3{color:#8b949e;margin:0 0 8px 0;font-size:14px;text-transform:uppercase}"
        html += "</style></head><body>"
        html += "<h1>URA System Status</h1><div class='grid'>"
        tasks_data = []
        ctx = None
        sock = None
        try:
            import zmq
            ctx = zmq.Context()
            sock = ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, 3000)
            sock.connect("ipc:///tmp/ura-supervisor.ipc")
            sock.send(b"tasks")
            tasks_data = json.loads(sock.recv())
        except Exception:
            log.exception("Failed to fetch supervisor tasks")
        finally:
            if sock:
                with contextlib.suppress(Exception):
                    sock.close()
            if ctx:
                with contextlib.suppress(Exception):
                    ctx.term()
        healthy = sum(1 for t in tasks_data if not t["done"] and t.get("last_error") is None)
        html += "<div class='card'><h3>Corrutinas</h3>"
        html += f"<div style='font-size:24px;font-weight:bold;color:#58a6ff'>{healthy}/{len(tasks_data)}</div>"
        html += "<div style='margin-top:8px'>"
        for t in sorted(tasks_data, key=lambda x: x["name"]):
            ok = not t["done"] and t.get("last_error") is None
            icon = "●" if ok else "○"
            color = "#3fb950" if ok else "#f85149"
            html += f"<div style='color:{color}'>{icon} {t['name']}</div>"
        html += "</div></div></div>"
        html += f"<div style='margin-top:16px;color:#484f58'>Golden Baseline v3.0 — {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC</div>"
        html += "</body></html>"
        self._send_html(html)

    def _handle_api_search(self, query: str) -> None:
        results = []
        try:
            from core.search_engine import search as fts_search
            results = fts_search(query)
        except Exception as e:
            log.warning("search_engine falló: %s", e)
        self._send_json({"query": query, "results": results, "total": len(results)})

    def _proxy_get(self) -> None:
        from core.model_router.proxy import proxy_request
        status, headers, body = proxy_request(self.path, None, "GET", client_ip=self.client_address[0])
        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._check_rate_limit():
            return
        if self.path in {"/api/tags", "/api/tags/"}:
            self._handle_api_tags()
        elif self.path in {"/api/version", "/"}:
            self._handle_api_version()
        elif self.path == "/health":
            self._handle_health()
        elif self.path == "/metrics":
            self._handle_metrics()
        elif self.path == "/vram/status":
            from core.model_router.vram_guard import vram_guard
            self._send_json(vram_guard.metricas())
        elif self.path == "/supervisor":
            self._handle_supervisor()
        elif self.path == "/status":
            self._handle_status()
        elif self.path.startswith("/dashboard") and not self.path.startswith("/dashboard.json"):
            from core.model_router.dashboard import _render_dashboard
            self._send_html(_render_dashboard())
        elif self.path in ("/dashboard.json", "/dashboard.json/"):
            from core.model_router.dashboard import _dashboard_json
            self._send_json(json.loads(_dashboard_json(client_ip=self.client_address[0])))
        elif self.path.startswith("/api/search"):
            import urllib.parse as _up
            q = _up.parse_qs(self.path.split("?")[1] if "?" in self.path else "").get("q", [None])[0]
            if not q:
                self._send_json({"error": "parametro q requerido"}, 400)
                return
            try:
                self._handle_api_search(q)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        elif self.path.startswith("/v1/"):
            self._proxy_get()
        else:
            self._proxy_get()

    def _handle_power_mode(self) -> bool:
        from core.model_router import router as _main
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        params_str = body.decode() if body else ""
        mode = ""
        for part in params_str.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k == "mode":
                    mode = v
        if "mode=" in self.path:
            mode = self.path.split("mode=")[-1].split("&")[0]
        if mode and mode.upper() in {"AUTO", "TURBO", "ECO"}:
            _main.POWER_MODE = mode.upper()
            log.info("POWER_MODE cambiado a %s por dashboard", _main.POWER_MODE)
            self._send_json({"status": "ok", "power_mode": _main.POWER_MODE})
            return True
        self._send_json({"error": "Modo invalido. Usar AUTO, TURBO o ECO."}, 400)
        return True

    def _do_proxy_inference(self, data: dict, modelo: str, tipo: str) -> None:
        from core.model_router.model_selection import _apply_model_params
        from core.model_router.proxy import _proxy_con_vram
        data = _apply_model_params(data, modelo)
        status, headers, resp_body = _proxy_con_vram(
            self.path,
            json.dumps(data).encode(),
            modelo=modelo,
            tipo=tipo,
            client_ip=self.client_address[0],
        )
        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        for k in ["Transfer-Encoding"]:
            if k in headers:
                self.send_header(k, headers[k])
        self.end_headers()
        self.wfile.write(resp_body)

    def do_POST(self) -> None:  # noqa: PLR0915
        from core.model_router.cache import prompt_cache
        from core.model_router.metrics import metrics
        from core.model_router.model_selection import (
            clasificar_peticion,
            seleccionar_modelo,
        )
        from core.model_router.proxy import _check_context_size, _proxy_con_vram
        from core.model_router.router import rate_limiter

        if not rate_limiter.is_allowed(self.client_address[0]):
            self._send_json({"error": "Rate limit: 100 req/min por IP"}, 429)
            return
        if self.path.startswith("/power_mode"):
            self._handle_power_mode()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        original_model = data.get("model", "")
        messages = data.get("messages", [])
        prompt = data.get("prompt", "")

        ctx = _check_context_size(messages or prompt)
        if ctx["level"] == "critical":
            log.warning("Contexto CRITICO: %s tokens — %s", ctx["tokens"], ctx["message"])
            metrics.increment("context_critical", {"tokens": str(ctx["tokens"])})

        is_chat = "/api/chat" in self.path or "/v1/chat" in self.path
        is_embed = "/api/embed" in self.path or "/v1/embed" in self.path

        if is_embed:
            tipo = "embeddings"
        elif original_model and original_model not in {"auto", "router"}:
            tipo = clasificar_peticion(messages or [{"role": "user", "content": prompt}])
            disponibles = self._get_modelos()
            if original_model in disponibles:
                selected = original_model
                log.info("[DIRECT] modelo=%s (solicitado explicitamente)", selected)
                metrics.increment("model_selection", {"tipo": tipo, "mode": "direct"})
                data["model"] = selected
                self._do_proxy_inference(data, selected, tipo)
                return
            log.warning("[DIRECT] modelo %s no disponible, redirigiendo a router", original_model)
            metrics.increment("model_unavailable", {"modelo": original_model})
        else:
            content_for_classify = messages or [{"role": "user", "content": prompt}]
            tipo = clasificar_peticion(content_for_classify)

        prompt_text = prompt or (json.dumps(messages[-1]) if messages else "")
        cached = prompt_cache.get(prompt_text, tipo) if prompt_text else None
        if cached and is_chat:
            log.info("[CACHE HIT] tipo=%s", tipo)
            metrics.increment("cache_hit", {"tipo": tipo})
            self._send_json(cached)
            return

        disponibles = self._get_modelos()
        selected = seleccionar_modelo(tipo, disponibles)
        log.info("[ROUTE] tipo=%s → modelo=%s (de %s disponibles)", tipo, selected, len(disponibles))
        metrics.increment("model_selection", {"tipo": tipo, "modelo": selected, "mode": "routed"})
        data["model"] = selected
        new_body = json.dumps(data).encode()
        status, headers, resp_body = _proxy_con_vram(
            self.path,
            new_body,
            modelo=selected,
            tipo=tipo,
            client_ip=self.client_address[0],
        )
        if status == 200 and is_chat and prompt_text:
            try:
                response_data = json.loads(resp_body)
                prompt_cache.set(prompt_text, tipo, response_data)
            except Exception:
                log.debug("No se pudo cachear respuesta")
        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        for k in ["Transfer-Encoding"]:
            if k in headers:
                self.send_header(k, headers[k])
        self.end_headers()
        self.wfile.write(resp_body)

    def log_message(self, fmt, *args) -> None:
        log.debug("%s - %s", self.client_address[0], fmt % args)

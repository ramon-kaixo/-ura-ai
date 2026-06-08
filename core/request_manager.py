#!/usr/bin/env python3
"""request_manager.py — Wrapper inteligente de peticiones para URA.

Cada petición pasa por proxy_selector.py para decidir la ruta:
  - pool → Cloudflare Worker (Hetzner, scraping masivo)
  - stealth → Bridge GX10 (Playwright + Anti-Detection + GPU)

Versión async compatible con collector_base.py existente.
"""

import base64
import json
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from core.proxy_selector import get_best_path

log = logging.getLogger(__name__)

GX10_BRIDGE = "http://10.164.1.99:4097"


@dataclass
class SmartResponse:
    data: Any = None
    mode: str = "pool"
    node: str = "hetzner"
    target: str = ""
    timing: float = 0.0
    headers: dict = field(default_factory=dict)
    status_code: int = 0

    @property
    def text(self) -> str:
        if isinstance(self.data, bytes):
            return self.data.decode("utf-8", errors="replace")
        if isinstance(self.data, dict):
            return json.dumps(self.data, indent=2)
        return str(self.data or "")

    def json(self) -> dict:
        if isinstance(self.data, dict):
            return self.data
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def screenshot_base64(self) -> Optional[str]:
        if isinstance(self.data, dict):
            content = self.data.get("result", {}).get("content", [])
            for c in content:
                if c.get("type") == "image":
                    return c.get("data")
        return None

    @property
    def content_bytes(self) -> Optional[bytes]:
        if self.screenshot_base64:
            return base64.b64decode(self.screenshot_base64)
        if isinstance(self.data, bytes):
            return self.data
        if isinstance(self.data, str):
            return self.data.encode()
        return None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "node": self.node,
            "target": self.target,
            "status_code": self.status_code,
            "timing_s": round(self.timing, 2),
            "has_screenshot": self.screenshot_base64 is not None,
            "content_bytes": len(self.content_bytes) if self.content_bytes else 0,
        }


async def smart_request(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    data: Optional[dict] = None,
    context: Optional[dict] = None,
    timeout: int = 60,
) -> SmartResponse:
    """Ejecuta una petición contra `url` usando la ruta óptima.

    Args:
        url: URL completa o dominio a alcanzar.
        method: Método HTTP.
        headers: Cabeceras adicionales.
        data: Body para POST/PUT.
        context: Dict opcional (mode_override, etc).
        timeout: Timeout en segundos.
    """
    start = time.time()
    route = get_best_path(url, context=context)
    log.info("smart_request %s -> mode=%s node=%s", url, route.mode, route.node)

    headers = headers or {}

    if route.mode == "stealth":
        result = await _call_gx10_bridge(url, method, headers, data, timeout)
    else:
        result = await _call_via_pool(url, method, headers, data, timeout)

    elapsed = time.time() - start
    log.info("smart_request %s done in %.2fs", url, elapsed)

    result.timing = elapsed
    result.mode = route.mode
    result.node = route.node
    result.target = url
    return result


async def _call_via_pool(
    url: str, method: str, headers: dict, data: Optional[dict], timeout: int
) -> SmartResponse:
    """Llama al target via Cloudflare Worker (pool residencial)."""
    from core.proxy_selector import CLOUDFLARE_WORKER_URL
    proxy_url = f"{CLOUDFLARE_WORKER_URL}/proxy?url={urllib.parse.quote(url)}"
    log.debug("pool proxy: %s", proxy_url)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            if method == "GET":
                resp = await client.get(proxy_url, headers=headers)
            elif method == "POST":
                resp = await client.post(proxy_url, headers=headers, json=data)
            elif method == "HEAD":
                resp = await client.head(proxy_url, headers=headers)
            else:
                resp = await client.request(method, proxy_url, headers=headers, json=data)
            return SmartResponse(
                data=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
        except httpx.TimeoutException:
            return SmartResponse(
                data=b'{"error": "timeout"}',
                status_code=504,
                headers={},
            )
        except Exception as e:
            return SmartResponse(
                data=f'{{"error": "{e}"}}'.encode(),
                status_code=502,
                headers={},
            )


async def _call_gx10_bridge(
    url: str, method: str, headers: dict, data: Optional[dict], timeout: int
) -> SmartResponse:
    """Llama al Bridge GX10 para ejecutar navegación con Anti-Detection."""
    bridge = f"{GX10_BRIDGE}/api/gui"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            nav_resp = await client.post(f"{bridge}/navigate", json={"url": url})
            if nav_resp.status_code != 200:
                return SmartResponse(
                    data={"error": f"navigate failed: {nav_resp.text}"},
                    status_code=502,
                )

            await client.post(f"{bridge}/wait", json={"ms": 2000})

            if method != "GET" and data:
                for key, value in data.items():
                    await client.post(
                        f"{bridge}/type",
                        json={"selector": f'[name="{key}"]', "text": str(value)},
                    )

            ss_resp = await client.post(f"{bridge}/screenshot", json={})
            if ss_resp.status_code != 200:
                return SmartResponse(
                    data={"error": f"screenshot failed: {ss_resp.text}"},
                    status_code=502,
                )

            return SmartResponse(
                data=ss_resp.json(),
                status_code=200,
            )
        except httpx.TimeoutException:
            return SmartResponse(data={"error": "timeout"}, status_code=504)
        except Exception as e:
            return SmartResponse(data={"error": str(e)}, status_code=502)


def save_screenshot(resp: SmartResponse, path: str) -> bool:
    """Guarda un screenshot de SmartResponse a disco."""
    b64 = resp.screenshot_base64
    if not b64:
        log.warning("No screenshot in response from %s", resp.target)
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        log.info("Screenshot saved: %s (%d bytes)", path, len(b64) * 3 // 4)
        return True
    except Exception as e:
        log.error("Failed to save screenshot: %s", e)
        return False


async def demo():
    logging.basicConfig(level=logging.INFO)
    resp = await smart_request(
        "https://www.behance.net/gallery/228159237/DATASCIENCE"
    )
    print(json.dumps(resp.to_dict(), indent=2))
    if resp.screenshot_base64:
        save_screenshot(resp, "/tmp/behance_demo.jpg")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())

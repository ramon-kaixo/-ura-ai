/**
 * ura-pool — Proxy Residencial URA (Cloudflare Worker).
 * Desplegado en: https://ura-pool.barkaixo.workers.dev
 */
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ status: "ok", worker: "ura-pool" }), {
        headers: { "Content-Type": "application/json" },
      });
    }
    const targetUrl = url.searchParams.get("url");
    if (!targetUrl) {
      return new Response(JSON.stringify({ error: "Missing url" }), {
        status: 400, headers: { "Content-Type": "application/json" },
      });
    }
    try { new URL(targetUrl); } catch {
      return new Response(JSON.stringify({ error: "Invalid URL" }), {
        status: 400, headers: { "Content-Type": "application/json" },
      });
    }
    const headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
      "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    };
    for (const h of ["Cookie", "Authorization", "Referer"]) {
      const v = request.headers.get(h);
      if (v) headers[h] = v;
    }
    const body = (request.method !== "GET" && request.method !== "HEAD")
      ? await request.text() : undefined;
    try {
      const resp = await fetch(targetUrl, {
        method: request.method, headers, body, redirect: "follow",
      });
      const rh = new Headers(resp.headers);
      rh.set("X-URA-Pool", "cloudflare");
      return new Response(resp.body, {
        status: resp.status, statusText: resp.statusText, headers: rh,
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 502, headers: { "Content-Type": "application/json" },
      });
    }
  },
};

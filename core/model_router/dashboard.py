"""Dashboard — HTML template + renderizado JSON y HTML."""

from __future__ import annotations

import json
import time

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>URA Model Router — Dashboard</title>
<style>
*{box-sizing:border-box
margin:0
padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif
background:#0d1117
color:#c9d1d9
padding:20px}
h1{color:#58a6ff
margin-bottom:8px
font-size:1.5rem}
.sub{color:#8b949e
font-size:0.85rem
margin-bottom:20px}
.grid{display:grid
grid-template-columns:repeat(auto-fit,minmax(280px,1fr))
gap:16px}
.card{background:#161b22
border:1px solid #30363d
border-radius:8px
padding:20px}
.card h2{font-size:0.85rem
text-transform:uppercase
letter-spacing:0.5px
color:#8b949e
margin-bottom:12px}
.status{display:inline-block
padding:4px 12px
border-radius:12px
font-weight:600
font-size:0.9rem}
.status-remote{background:#1f6feb22
color:#58a6ff
border:1px solid #1f6feb44}
.status-local{background:#da363322
color:#f0883e
border:1px solid #da363344}
.value{font-size:1.8rem
font-weight:700}
.value-green{color:#3fb950}
.value-yellow{color:#d29922}
.value-red{color:#f85149}
.value-blue{color:#58a6ff}
.meta{font-size:0.75rem
color:#484f58
margin-top:4px}
.power-select{background:#21262d
color:#c9d1d9
border:1px solid #30363d
border-radius:6px
padding:8px 12px
font-size:0.9rem
cursor:pointer}
table{width:100%
border-collapse:collapse
font-size:0.85rem}
th,td{text-align:left
padding:6px 4px
border-bottom:1px solid #21262d}
th{color:#8b949e
font-weight:500}
</style>
</head>
<body>
<h1>URA Model Router</h1>
<div class="sub">Dashboard de inferencia — actualizando cada 5s</div>
<div class="grid">
<div class="card"><h2>Estado de Inferencia</h2>
<div><span class="status {sc}" id="backend-label">{bl}</span></div>
<div class="meta" style="margin-top:8px">{bu}</div></div>
<div class="card"><h2>Latencia ASUS</h2>
<div class="value {lc}" id="asus-latency">{al}</div>
<div class="meta" id="latency-updated">{lu}</div></div>
<div class="card"><h2>Fallbacks (ultima hora)</h2>
<div class="value {fc}" id="fallback-count">{fbc}</div>
<div class="meta">cambios a Local</div></div>
<div class="card"><h2>POWER_MODE</h2>
<select class="power-select" id="power-mode" onchange="setPowerMode(this.value)">
<option value="AUTO" {asel}>&#9889
AUTO — segun IP cliente</option>
<option value="TURBO" {tsel}>&#128293
TURBO — forzar ASUS</option>
<option value="ECO" {esel}>&#128161
ECO — forzar local</option>
</select>
<div class="meta" style="margin-top:8px">{ph}</div></div>
</div>
<div style="margin-top:16px">
<div class="card"><h2>Modelos disponibles</h2>
<table><thead><tr><th>Modelo</th><th>Uso</th></tr></thead>
<tbody id="models-tbody"></tbody></table></div></div>
<script>
async function refresh(){try{
var r=await fetch('/dashboard.json'),d=await r.json()
var l=document.getElementById('backend-label')
l.textContent=d.backend_label
l.className='status '+(d.backend_label==='ASUS Remoto'?'status-remote':'status-local')
document.getElementById('backend-url').textContent=d.backend_url
var le=document.getElementById('asus-latency'),lv=d.asus_latency_ms
if(lv<0){le.textContent='N/A'
le.className='value value-red'}
else if(lv>200){le.textContent=lv+' ms'
le.className='value value-yellow'}
else{le.textContent=lv+' ms'
le.className='value value-green'}
document.getElementById('latency-updated').textContent=d.latency_updated
var fb=document.getElementById('fallback-count'),fv=d.fallback_count_1h
fb.textContent=fv
fb.className='value '+(fv===0?'value-green':fv<5?'value-yellow':'value-red')
document.getElementById('models-tbody').innerHTML=d.models.map(function(m){return '<tr><td>'+m.name+'</td><td>'+m.tasks.join(', ')+'</td></tr>'}).join('')
}catch(e){console.error('Dashboard error:',e)}}
async function setPowerMode(mode){try{
await fetch('/power_mode?mode='+mode,{method:'POST'})
setTimeout(refresh,200)
}catch(e){console.error('Power mode error:',e)}}
refresh()
setInterval(refresh,5000)
</script>
</body>
</html>"""


def _render_dashboard() -> str:
    import core.model_router_main as _main
    from core.model_router.proxy import (
        _asus_latency_lock,
        _asus_latency_ms,
        _asus_latency_updated,
        _fallback_count_last_hour,
        _get_active_backend_label,
        _update_asus_latency,
    )
    from core.model_router_main import OLLAMA_URL

    _update_asus_latency()
    backend_label = _get_active_backend_label()
    fb_count = _fallback_count_last_hour()
    with _asus_latency_lock:
        lat = _asus_latency_ms
        lat_updated = time.strftime("%H:%M:%S", time.localtime(_asus_latency_updated)) if _asus_latency_updated else ""
    pm = _main.POWER_MODE
    status_class = "status-remote" if backend_label == "ASUS Remoto" else "status-local"
    auto_sel = "selected" if pm.upper() == "AUTO" else ""
    turbo_sel = "selected" if pm.upper() == "TURBO" else ""
    eco_sel = "selected" if pm.upper() == "ECO" else ""
    if pm.upper() == "AUTO":
        power_hint = "Clientes locales → ASUS | Remotos → Local"
    elif pm.upper() == "TURBO":
        power_hint = "Toda la inferencia va a ASUS. Fallback local bloqueado."
    else:
        power_hint = "Toda la inferencia va al Mac local."
    if lat < 0:
        latency_class = "value-red"
        asus_latency = "N/A"
        latency_updated = "ASUS no accesible"
    elif lat > 200:
        latency_class = "value-yellow"
        asus_latency = f"{lat} ms"
        latency_updated = f"alta — {lat_updated}"
    else:
        latency_class = "value-green"
        asus_latency = f"{lat} ms"
        latency_updated = lat_updated
    fallback_class = "value-green" if fb_count == 0 else "value-yellow" if fb_count < 5 else "value-red"
    return (
        _DASHBOARD_HTML.replace("{sc}", status_class)
        .replace("{bl}", backend_label)
        .replace("{bu}", OLLAMA_URL)
        .replace("{lc}", latency_class)
        .replace("{al}", asus_latency)
        .replace("{lu}", latency_updated)
        .replace("{fc}", fallback_class)
        .replace("{fbc}", str(fb_count))
        .replace("{asel}", auto_sel)
        .replace("{tsel}", turbo_sel)
        .replace("{esel}", eco_sel)
        .replace("{ph}", power_hint)
    )


def _dashboard_json(client_ip: str = "") -> str:
    import core.model_router_main as _main
    from core.model_router.model_selection import MODELO_ROUTES, obtener_modelos_disponibles
    from core.model_router.proxy import (
        _asus_latency_lock,
        _asus_latency_ms,
        _asus_latency_updated,
        _fallback_count_last_hour,
        _get_active_backend_label,
        _resolve_mode_for_client,
        _update_asus_latency,
    )
    from core.model_router_main import OLLAMA_URL

    _update_asus_latency()
    resolved_mode = _resolve_mode_for_client(client_ip or "127.0.0.1")
    backend_label = (
        "ASUS Remoto"
        if resolved_mode == "TURBO"
        else "Local Mac"
        if resolved_mode == "ECO"
        else _get_active_backend_label()
    )
    fb_count = _fallback_count_last_hour()
    with _asus_latency_lock:
        lat = _asus_latency_ms
        lat_updated = time.strftime("%H:%M:%S", time.localtime(_asus_latency_updated)) if _asus_latency_updated else ""
    disponibles = obtener_modelos_disponibles()
    models_info: list[dict] = []
    for m in sorted(disponibles)[:50]:
        tasks = [k for k, v in MODELO_ROUTES.items() if m in v["modelos"]]
        models_info.append({"name": m, "tasks": tasks or ["disponible"]})
    return json.dumps(
        {
            "backend_label": backend_label,
            "backend_url": OLLAMA_URL,
            "power_mode": _main.POWER_MODE.upper(),
            "asus_latency_ms": lat,
            "latency_updated": lat_updated,
            "fallback_count_1h": fb_count,
            "models": models_info,
        },
    )

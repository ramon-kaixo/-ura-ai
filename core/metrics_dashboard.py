#!/usr/bin/env python3
"""
Metrics Dashboard — FASE 6
───────────────────────────
Página HTML con gráficos de Plotly: CPU, RAM, disco, temperatura.
Servida por ura_web.py.
"""

import time

import psutil

METRICS_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>URA Métricas</title>
<script src="https://cdn.plot.ly/plotly-3.0.1.min.js"></script>
<style>
:root{--bg:#0a0a0f;--card:#131320;--border:#1e1e35;--text:#d4d4e0;--cyan:#6c8cff;--green:#4ade80;--yellow:#fbbf24;--red:#f87171}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,system-ui,sans-serif;padding:20px}
h1{color:var(--cyan);margin-bottom:8px;font-size:24px}
.sub{color:var(--dim);font-size:12px;margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px}
.card h2{font-size:14px;color:var(--cyan);margin-bottom:12px}
.gauge-row{display:flex;gap:16px;flex-wrap:wrap}
.gauge{flex:1;min-width:150px;text-align:center}
.gauge .value{font-size:36px;font-weight:700}
.gauge .label{font-size:11px;color:var(--dim);margin-top:4px}
.gauge .bar{height:6px;border-radius:3px;margin-top:8px;background:var(--border);overflow:hidden}
.gauge .bar div{height:100%;border-radius:3px;transition:width .5s}
</style>
</head>
<body>
<h1>📊 URA Métricas</h1>
<div class="sub" id="sub"></div>
<div class="grid">
  <div class="card" style="grid-column:span 2">
    <h2>CPU + RAM (últimos 5 min)</h2>
    <div id="cpu-ram-chart" style="height:300px"></div>
  </div>
  <div class="card">
    <h2>💾 Disco</h2>
    <div id="disk-gauge"></div>
  </div>
  <div class="card">
    <h2>🧵 Procesos URA</h2>
    <div id="proc-list"></div>
  </div>
</div>
<script>
const history=[];
function fmt(n){return n.toFixed(1)}
async function update(){
  let r=await fetch('/metrics/data');
  let d=await r.json();
  document.getElementById('sub').textContent='Actualizado: '+new Date().toLocaleTimeString();

  // CPU + RAM history
  history.push({t:new Date(),cpu:d.cpu_percent,ram:d.ram_percent});
  if(history.length>60)history.shift();
  let ts=history.map(h=>h.t),cpu=history.map(h=>h.cpu),ram=history.map(h=>h.ram);
  Plotly.newPlot('cpu-ram-chart',[
    {x:ts,y:cpu,name:'CPU %',type:'scatter',mode:'lines',line:{color:'#6c8cff',width:2},fill:'tozeroy',fillcolor:'rgba(108,140,255,0.1)'},
    {x:ts,y:ram,name:'RAM %',type:'scatter',mode:'lines',line:{color:'#4ade80',width:2},fill:'tozeroy',fillcolor:'rgba(74,222,128,0.1)'}
  ],{margin:{t:10,r:10,b:30,l:40},paper_bgcolor:'#131320',plot_bgcolor:'#0a0a0f',font:{color:'#d4d4e0',size:12},xaxis:{showgrid:false},yaxis:{range:[0,100],gridcolor:'#1e1e35'},showlegend:true,legend:{font:{color:'#d4d4e0'}}},{displayModeBar:false});

  // Disk gauge
  let diskPct=d.disk_percent,diskColor=diskPct>90?'#f87171':diskPct>70?'#fbbf24':'#4ade80';
  document.getElementById('disk-gauge').innerHTML=`
    <div class="gauge"><div class="value" style="color:${diskColor}">${fmt(diskPct)}%</div><div class="label">Usado (${d.disk_used} de ${d.disk_total})</div><div class="bar"><div style="width:${diskPct}%;background:${diskColor}"></div></div></div>`;

  // Processes
  document.getElementById('proc-list').innerHTML=d.processes.map(p=>`<div style="padding:4px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between"><span>${p.name}</span><span style="color:var(--dim)">${p.pid} | ${p.cpu}% CPU | ${p.mem}MB</span></div>`).join('');
}
update();setInterval(update,5000);
</script>
</body>
</html>"""


def get_metrics_data() -> dict:
    """Recolecta métricas del sistema en tiempo real."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            name = (proc.info["name"] or "").lower()
            if any(kw in name for kw in ["python", "ollama", "ura", "node", "docker", "grafana"]):
                mem_info = proc.info["memory_info"]
                mem_mb = (mem_info.rss / 1024 / 1024) if mem_info else 0
                processes.append(
                    {
                        "pid": proc.info["pid"],
                        "name": proc.info["name"],
                        "cpu": round(proc.info["cpu_percent"] or 0, 1),
                        "mem": round(mem_mb, 1),
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    processes.sort(key=lambda p: -p["mem"])

    return {
        "timestamp": time.time(),
        "cpu_percent": round(cpu, 1),
        "ram_percent": round(ram.percent, 1),
        "ram_used": f"{ram.used / 1024**3:.1f} GB",
        "ram_total": f"{ram.total / 1024**3:.1f} GB",
        "disk_percent": round(disk.percent, 1),
        "disk_used": f"{disk.used / 1024**3:.1f} GB",
        "disk_total": f"{disk.total / 1024**3:.1f} GB",
        "processes": processes[:8],
    }

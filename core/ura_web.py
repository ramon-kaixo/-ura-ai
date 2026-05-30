#!/usr/bin/env python3
"""URA Web v2 — 4 pestañas: Chat, Sistema, Agentes, Logs. Barra superior siempre visible."""

import json
import re
import sys
import time
from datetime import datetime, UTC
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


import psutil
import requests

import logging

logger = logging.getLogger(__name__)

from core.security_policy import (
    get_token,
    verify_token,
    sanitize_input,
    detect_jailbreak,
    GUARDRAIL_RESPONSE,
    validate_command,
    validate_brew_package,
)

PORT = 5051
OLLAMA_URL = "http://gx10-ts:11434/api/generate"
MODEL = "qwen3:32b-q8_0"
NODES = {
    8101: "Disco",
    8102: "Ollama",
    8103: "Limpieza",
    8104: "Procesos",
    8105: "Red",
    8106: "RAM",
    8107: "Backup",
    8108: "Salud",
}
LOG_FILE = Path(__file__).parent.parent / "ura_app.log"

HTML_PATH = Path(__file__).parent / "templates" / "index.html"
try:
    HTML = HTML_PATH.read_text()
except Exception:
    HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>URA</title>
<style>
:root{--bg:#0a0a0f;--card:#131320;--border:#1e1e35;--text:#d4d4e0;--cyan:#6c8cff;--green:#4ade80;--yellow:#fbbf24;--red:#f87171;--dim:#5c5c7a}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,system-ui,sans-serif;height:100vh;display:flex;flex-direction:column}
#topbar{background:linear-gradient(135deg,#131320,#1a1a30);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:10px 20px;font-size:12px;gap:20px;flex-wrap:wrap}
#topbar .dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 8px}
#topbar .dot.ok{background:var(--green);box-shadow:0 0 8px var(--green)}
#topbar .dot.warn{background:var(--yellow);box-shadow:0 0 8px var(--yellow)}
#topbar .dot.err{background:var(--red);box-shadow:0 0 8px var(--red)}
#topbar h2{color:var(--cyan);font-size:18px;font-weight:700;margin-right:auto;letter-spacing:-0.5px}
#tabs{display:flex;background:var(--card);border-bottom:1px solid var(--border);padding:0 12px}
#tabs button{flex:1;padding:14px 8px;background:none;border:none;color:var(--dim);cursor:pointer;font-size:13px;font-weight:500;border-bottom:2px solid transparent;transition:all .2s;max-width:140px}
#tabs button:hover{color:var(--text)}
#tabs button.active{color:var(--cyan);border-bottom-color:var(--cyan);background:linear-gradient(0deg,rgba(108,140,255,0.08),transparent)}
#main{flex:1;overflow:hidden;position:relative}
.panel{position:absolute;top:0;left:0;right:0;bottom:0;display:none;overflow:auto}
.panel.active{display:flex;flex-direction:column}
#chat-messages{flex:1;overflow-y:auto;padding:16px 20px}
#chat-messages .msg{margin-bottom:16px;line-height:1.6;font-size:14px;max-width:85%;padding:10px 14px;border-radius:12px}
#chat-messages .user{color:var(--text);background:var(--card);margin-left:auto;border:1px solid var(--border)}
#chat-messages .ura{color:var(--text);background:linear-gradient(135deg,#1a1a35,#131325);border:1px solid var(--cyan);border-left:3px solid var(--cyan)}
#chat-input{background:var(--card);padding:12px 16px;border-top:1px solid var(--border);display:flex;align-items:center;gap:10px}
#chat-input input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:12px 16px;border-radius:10px;font-size:14px;outline:none;transition:border .2s}
#chat-input input:focus{border-color:var(--cyan)}
#chat-input button{background:var(--cyan);color:#fff;border:none;padding:12px 20px;border-radius:10px;cursor:pointer;font-size:14px;font-weight:600;transition:all .2s}
#chat-input button:hover{opacity:0.85;transform:translateY(-1px)}
#sys-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;padding:20px}
.sys-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;transition:border .2s}
.sys-card:hover{border-color:var(--cyan)}
.sys-card h4{font-size:13px;margin-bottom:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1px}
.sys-card .val{font-size:28px;font-weight:700}
.sys-card .sub{font-size:12px;color:var(--dim);margin-top:6px}
.bar{height:8px;background:var(--border);border-radius:4px;margin-top:10px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;transition:width .5s ease}
.bar-fill.g{background:linear-gradient(90deg,var(--green),#22c55e)}.bar-fill.y{background:linear-gradient(90deg,var(--yellow),#f59e0b)}.bar-fill.r{background:linear-gradient(90deg,var(--red),#ef4444)}
#agent-list{padding:20px}.agent{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:10px;cursor:pointer;transition:all .2s;font-size:13px}.agent:hover{border-color:var(--cyan);background:#18182a}.agent-head{display:flex;justify-content:space-between;align-items:center}
#log-view{flex:1;overflow-y:auto;padding:14px 18px;font-family:'SF Mono',monospace;font-size:12px;line-height:1.7}#log-view .e{color:var(--red)}#log-view .w{color:var(--yellow)}#log-view .i{color:var(--dim)}
#log-filters{background:var(--card);padding:10px 18px;border-bottom:1px solid var(--border);display:flex;gap:16px;font-size:12px}#log-filters label{cursor:pointer;display:flex;align-items:center;gap:5px}
.spinner{display:inline-block;width:10px;height:10px;background:var(--cyan);border-radius:50%;animation:pulse .8s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.feedback{display:inline-flex;gap:4px;margin-left:10px}.feedback button{background:var(--card);border:1px solid var(--border);cursor:pointer;font-size:14px;opacity:0.5;padding:2px 6px;border-radius:4px;transition:all .2s}.feedback button:hover{opacity:1;transform:scale(1.2);border-color:var(--cyan)}.feedback button.liked{opacity:1;border-color:var(--green)}
</style>
</head>
<body>
<div id="topbar">
  <h2>URA</h2>
  <span><span id="top-dot" class="dot ok"></span> <strong id="top-status">OK</strong></span>
  <span>🌐 <strong id="top-ip">--</strong></span>
  <span>🧠 <strong id="top-model">llama3.2:3b</strong></span>
  <span>💾 Backup: <strong id="top-backup">--</strong></span>
</div>
 <div id="tabs">
  <button class="active" onclick="switchTab(0)">💬 Chat</button>
  <button onclick="switchTab(1)">🖥️ Sistema</button>
  <button onclick="switchTab(2)">🤖 Agentes</button>
  <button onclick="switchTab(3)">📋 Logs</button>
  <button onclick="switchTab(4)">🧠 OpenCode</button>
</div>
<div id="main">
  <div class="panel active" id="panel-0">
    <div id="chat-messages"><div class="msg ura">Hola Ramón. ¿En qué te ayudo?</div></div>
    <div id="chat-input"><button id="mic-btn" onclick="toggleVoice()" title="Hablar" style="background:var(--card);border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:8px;cursor:pointer;font-size:16px">🎤</button><input id="user-input" placeholder="Escribe o pulsa el micro..." autofocus onkeydown="if(event.key==='Enter')send()"><button onclick="send()">Enviar</button></div>
  </div>
  <div class="panel" id="panel-1"><div id="sys-grid">Cargando...</div></div>
  <div class="panel" id="panel-2"><div id="agent-list">Cargando...</div></div>
  <div class="panel" id="panel-3">
    <div id="log-filters"><label><input type="checkbox" checked onchange="loadLogs()" id="flt-e"> ERROR</label><label><input type="checkbox" checked onchange="loadLogs()" id="flt-w"> WARNING</label><label><input type="checkbox" checked onchange="loadLogs()" id="flt-i"> INFO</label></div>
    <div id="log-view">Cargando...</div>
  </div>
  <div class="panel" id="panel-4" style="padding:20px;flex-direction:column">
    <div style="margin-bottom:16px">
      <textarea id="oc-input" placeholder="Instrucción para OpenCode (DeepSeek V4 Pro)..." style="width:100%;height:80px;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:inherit;font-size:14px;resize:vertical"></textarea>
    </div>
    <div style="display:flex;gap:10px;margin-bottom:16px">
      <button onclick="ocAssist()" style="background:var(--cyan);color:#000;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600">▶ Assist</button>
      <button onclick="ocRun()" style="background:var(--card);color:var(--text);border:1px solid var(--border);padding:10px 20px;border-radius:8px;cursor:pointer">⚡ Run (multi-paso)</button>
      <button onclick="ocReview()" style="background:var(--card);color:var(--text);border:1px solid var(--border);padding:10px 20px;border-radius:8px;cursor:pointer">🔍 Revisar código</button>
    </div>
    <div id="oc-result" style="flex:1;overflow-y:auto;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;font-size:13px;line-height:1.6;white-space:pre-wrap;font-family:monospace">Resultados aquí...</div>
  </div>
</div>
<script>
let currentTab=0;
function switchTab(n){
  currentTab=n;
  document.querySelectorAll('#tabs button').forEach((b,i)=>b.className=i===n?'active':'');
  document.querySelectorAll('.panel').forEach((p,i)=>p.className=i===n?'panel active':'panel');
  if(n===1)loadSystem();if(n===2)loadAgents();if(n===3)loadLogs();
}
function addMsg(type,text){let d=document.getElementById('chat-messages');let id='msg-'+Date.now();d.innerHTML+=`<div class="msg ${type}" id="${id}">${text}${type==='ura'?' <span class="feedback"><button onclick=\"sendFeedback(1,'+id+')\" title=\"Buena respuesta\">👍</button><button onclick=\"sendFeedback(0,'+id+')\" title=\"Mala respuesta\">👎</button></span>':''}</div>`;d.scrollTop=d.scrollHeight}
function sendFeedback(v,id){let el=document.getElementById(id);el.querySelector('.feedback').innerHTML=v?'👍 ✅':'👎 ✅';fetch('/feedback',{method:'POST',body:JSON.stringify({value:v,message:el.textContent.replace(/👍👎✅/g,'').trim()}),headers:{'Content-Type':'application/json'}})}
// Voice
let listening=false,recognition=null;
function toggleVoice(){
  if(!('webkitSpeechRecognition' in window)&&!('SpeechRecognition' in window)){alert('Tu navegador no soporta voz. Usa Chrome.');return}
  if(listening){recognition.stop();listening=false;document.getElementById('mic-btn').textContent='🎤';return}
  let SR=window.SpeechRecognition||window.webkitSpeechRecognition;recognition=new SR();recognition.lang='es-ES';recognition.interimResults=false;recognition.continuous=false;
  recognition.onresult=e=>{let msg=e.results[0][0].transcript;document.getElementById('user-input').value=msg;send();listening=false;document.getElementById('mic-btn').textContent='🎤'}
  recognition.onerror=e=>{listening=false;document.getElementById('mic-btn').textContent='🎤'}
  recognition.onend=()=>{listening=false;document.getElementById('mic-btn').textContent='🎤'}
  recognition.start();listening=true;document.getElementById('mic-btn').textContent='🔴'
}
function speak(text){
  if(!('speechSynthesis' in window))return;
  speechSynthesis.cancel();
  let u=new SpeechSynthesisUtterance(text.replace(/<[^>]+>/g,'').replace(/`/g,'').substring(0,500));
  u.lang='es-ES';u.rate=1.0;u.pitch=1.0;
  let voices=speechSynthesis.getVoices();
  let es=voices.find(v=>v.lang.startsWith('es'));
  if(es)u.voice=es;
  speechSynthesis.speak(u);
}
async function send(){
  let inp=document.getElementById('user-input'),msg=inp.value.trim();if(!msg)return;
  inp.value='';inp.disabled=true;addMsg('user',msg);addMsg('ura','<span class="spinner"></span>');
  let tabs=['chat','sistema','agentes','logs'];
  let responseDiv=document.getElementById('chat-messages').lastChild;
  let fullResponse='';
  try{
    let r=await fetch('/chat/stream',{method:'POST',body:JSON.stringify({message:msg,tab:tabs[currentTab]}),headers:{'Content-Type':'application/json',Authorization:'Bearer '+URA_TOKEN}});
    let reader=r.body.getReader(),decoder=new TextDecoder();
    while(true){
      let{value,done}=await reader.read();if(done)break;
      let text=decoder.decode(value,{stream:true});
      let lines=text.split('\n');
      for(let line of lines){
        if(line.startsWith('data: ')){
          try{let d=JSON.parse(line.slice(6));if(d.token){fullResponse+=d.token;responseDiv.innerHTML=fullResponse||'...'}else if(d.done){responseDiv.innerHTML=fullResponse||'OK'}else if(d.error){responseDiv.innerHTML='Error: '+d.error}}
          catch(e){}
        }
      }
    }
    // Auto-execute commands
    let cmdMatch=fullResponse.match(/`([^`]+)`/);
    if(cmdMatch){
      let cmd=cmdMatch[1];responseDiv.innerHTML='Ejecutando: '+cmd+'...';
      let er=await fetch('/ejecutar',{method:'POST',body:JSON.stringify({comando:cmd}),headers:{'Content-Type':'application/json',Authorization:'Bearer '+URA_TOKEN}});
      let ed=await er.json();responseDiv.innerHTML=ed.ok?(ed.stdout||'OK'):(ed.error||'Error');
    }
    if(!cmdMatch)speak(fullResponse);
  }catch(e){responseDiv.innerHTML='Error de conexión: '+e.message}
  inp.disabled=false;inp.focus();document.getElementById('chat-messages').scrollTop=999999;
}
    document.getElementById('chat-messages').lastChild.innerHTML=response||'Sin respuesta';
    speak(response);
    if(d.tab&&d.tab!==tabs[currentTab]){switchTab(tabs.indexOf(d.tab));}
  }catch(e){document.getElementById('chat-messages').lastChild.innerHTML='Error de conexión'}
  inp.disabled=false;inp.focus();document.getElementById('chat-messages').scrollTop=999999;
}

// Agents: auto-reload on tab switch
let agentsLoaded=false;
async function loadSystem(){
  let r=await fetch('/system'),d=await r.json();
  let h='';
  h+=`<div class="sys-card"><h4>💾 Disco</h4><div class="val">${d.disk.free} GB</div><div class="sub">${d.disk.used_pct}% usado — ${d.disk.total} GB total</div><div class="bar"><div class="bar-fill ${d.disk.used_pct>90?'r':d.disk.used_pct>70?'y':'g'}" style="width:${d.disk.used_pct}%"></div></div></div>`;
  h+=`<div class="sys-card"><h4>🧠 RAM</h4><div class="val">${d.ram.free} GB</div><div class="sub">${d.ram.used_pct}% usado — ${d.ram.total} GB total</div><div class="bar"><div class="bar-fill ${d.ram.used_pct>90?'r':d.ram.used_pct>70?'y':'g'}" style="width:${d.ram.used_pct}%"></div></div></div>`;
  h+=`<div class="sys-card"><h4>🦙 Ollama</h4><div class="val" style="color:${d.ollama.ok?'var(--green)':'var(--red)'}">${d.ollama.ok?'✅ Online':'❌ Offline'}</div><div class="sub">${d.ollama.ms} ms — ${d.ollama.model}</div></div>`;
  h+=`<div class="sys-card"><h4>🧵 Threads</h4><div class="val">${d.threads.count}</div><div class="sub">activos</div></div>`;
  h+=`<div class="sys-card"><h4>🔐 Backup</h4><div class="val">${d.backup.time||'Nunca'}</div><div class="sub">iCloud — ${d.backup.files||0} archivos</div></div>`;
  document.getElementById('sys-grid').innerHTML=h;
}
async function loadAgents(){
  let r=await fetch('/agents'),d=await r.json();
  let cats={},html='';
  d.forEach(a=>{if(!cats[a.categoria])cats[a.categoria]=[];cats[a.categoria].push(a)});
  for(let[cat,agents]of Object.entries(cats)){
    html+=`<div style="margin-bottom:16px"><h4 style="color:var(--dim);font-size:12px;text-transform:uppercase;margin-bottom:6px">${cat} (${agents.length})</h4>`;
    agents.forEach(a=>{
      html+=`<div class="agent">
        <div class="agent-head" onclick="this.parentElement.classList.toggle('open');let t=this.parentElement.querySelector('.agent-body');t.style.display=t.style.display==='none'?'block':'none';this.querySelector('span:last-child').textContent=t.style.display==='none'?'▶':'▼'">
          <span>${a.icon} ${a.name}</span><span style="color:var(--dim);font-size:11px">▶</span>
        </div>
        <div class="agent-body" style="display:none;margin-top:6px;color:var(--dim);font-size:12px;line-height:1.5">
          ${a.descripcion}
          <br><button onclick="event.stopPropagation();switchTab(0);document.getElementById('user-input').value='¿Para qué sirve el agente ${a.name}?';send()" style="margin-top:8px;padding:4px 12px;background:var(--cyan);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:11px">💬 Preguntar a URA</button>
        </div>
      </div>`;
    });
    html+='</div>';
  }
  document.getElementById('agent-list').innerHTML=html;
}
async function loadLogs(){
  let e=document.getElementById('flt-e').checked,w=document.getElementById('flt-w').checked,i=document.getElementById('flt-i').checked;
  let r=await fetch('/logs?e='+e+'&w='+w+'&i='+i),d=await r.json();
  document.getElementById('log-view').innerHTML=d.map(l=>`<div class="${l.level[0].toLowerCase()}">${l.ts} [${l.level}] ${l.msg}</div>`).join('');
}
async function loadTopbar(){
  let r=await fetch('/topbar'),d=await r.json();
  let dot=document.getElementById('top-dot');dot.className='dot '+(d.status==='ok'?'ok':d.status==='warn'?'warn':'err');
  document.getElementById('top-status').textContent=d.status.toUpperCase();
  document.getElementById('top-ip').textContent=d.ip||'--';
  document.getElementById('top-model').textContent=d.model;
  document.getElementById('top-backup').textContent=d.backup||'--';
}
loadSystem();loadTopbar();
setInterval(()=>{if(currentTab===1)loadSystem();loadTopbar()},30000);

// ── OpenCode ──────────────────────────────────────────────
async function ocCall(mode){
  let inp=document.getElementById('oc-input').value;
  if(!inp)return;
  let res=document.getElementById('oc-result');
  res.textContent='Procesando...';
  try{
    let r=await fetch('/opencode',{
      method:'POST',
      body:JSON.stringify({instruction:inp,mode:mode}),
      headers:{'Content-Type':'application/json',Authorization:'Bearer '+URA_TOKEN}
    });
    let d=await r.json();
    if(d.ok)res.textContent=d.response||d.result||JSON.stringify(d,null,2);
    else res.textContent='Error: '+(d.error||'desconocido');
  }catch(e){res.textContent='Error de conexión: '+e.message}
}
function ocAssist(){ocCall('assist')}
function ocRun(){ocCall('run')}
async function ocReview(){
  let file=prompt('Ruta del archivo a revisar:','main_final.py');
  if(!file)return;
  let res=document.getElementById('oc-result');
  res.textContent='Revisando '+file+'...';
  try{
    let r=await fetch('/opencode',{
      method:'POST',
      body:JSON.stringify({mode:'review',instruction:file}),
      headers:{'Content-Type':'application/json',Authorization:'Bearer '+URA_TOKEN}
    });
    let d=await r.json();
    if(d.ok)res.textContent=d.response||JSON.stringify(d,null,2);
    else res.textContent='Error: '+(d.error||'desconocido');
  }catch(e){res.textContent='Error: '+e.message}
}
</script>
</body>
</html>"""


def _get_ura_context():
    """Construye el contexto de identidad de URA con datos reales del sistema."""
    disk = psutil.disk_usage("/")
    ram = psutil.virtual_memory()
    agents = len(list((Path(__file__).parent.parent / "agents").glob("*.py")))
    try:
        models = requests.get("http://localhost:11434/api/tags", timeout=3).json().get("models", [])
        model_names = ", ".join(m["name"] for m in models[:3])
    except Exception:
        model_names = "ollama local"

    # Cargar conciencia del sistema (Niveles 21-24)
    awareness_parts = []
    try:
        from core.ura_environment_awareness import get_ura_environment_awareness

        env = get_ura_environment_awareness()
        ctx = env.get_environment_context()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"environment_awareness skip: {e}")

    try:
        from core.ura_hardware_awareness import get_ura_hardware_awareness

        hw = get_ura_hardware_awareness()
        ctx = hw.get_hardware_context()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"hardware_awareness skip: {e}")

    try:
        from core.ura_applications_awareness import get_ura_applications_awareness

        apps = get_ura_applications_awareness()
        ctx = apps.get_applications_context()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"applications_awareness skip: {e}")

    try:
        from core.ura_tools_awareness import get_ura_tools_awareness

        tools = get_ura_tools_awareness()
        ctx = tools.get_tools_context()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"tools_awareness skip: {e}")

    # Cargar conciencia superior (Niveles 1-20)
    try:
        from core.ura_self_knowledge import get_ura_self_knowledge

        sk = get_ura_self_knowledge()
        ctx = sk.get_summary_for_prompt()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"self_knowledge skip: {e}")

    try:
        from core.ura_emotions import get_ura_emotions

        em = get_ura_emotions()
        ctx = em.get_context_for_prompt()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"emotions skip: {e}")

    try:
        from core.ura_memory import get_ura_memory

        mem = get_ura_memory()
        ctx = mem.get_summary_for_prompt()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"memory skip: {e}")

    try:
        from core.ura_personality import get_ura_personality

        per = get_ura_personality()
        ctx = per.get_context_for_prompt()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"personality skip: {e}")

    try:
        from core.ura_goals import get_ura_goals

        gls = get_ura_goals()
        ctx = gls.get_context_for_prompt()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"goals skip: {e}")

    try:
        from core.ura_planning import get_ura_planning

        plan = get_ura_planning()
        ctx = plan.get_context_for_prompt()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"planning skip: {e}")

    try:
        from core.ura_metrics import get_ura_metrics

        met = get_ura_metrics()
        ctx = met.get_metrics_summary()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"metrics skip: {e}")

    try:
        from core.ura_self_reflection import get_ura_self_reflection

        ref = get_ura_self_reflection()
        ctx = ref.get_reflection_context()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"self_reflection skip: {e}")

    try:
        from core.ura_anticipation import get_ura_anticipation

        ant = get_ura_anticipation()
        if hasattr(ant, "get_context_for_prompt"):
            ctx = ant.get_context_for_prompt()
            if ctx:
                awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"anticipation skip: {e}")

    try:
        from core.ura_context_continuity import get_ura_context_continuity

        cont = get_ura_context_continuity()
        ctx = cont.get_conversation_summary()
        if ctx:
            awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"context_continuity skip: {e}")

    try:
        from core.ura_theory_of_mind import get_ura_theory_of_mind

        tom = get_ura_theory_of_mind()
        if hasattr(tom, "get_context_for_prompt"):
            ctx = tom.get_context_for_prompt()
            if ctx:
                awareness_parts.append(ctx)
    except Exception as e:
        logger.warning(f"theory_of_mind skip: {e}")

    try:
        from core.ura_diary import get_ura_diary

        diary = get_ura_diary()
        ctx = diary.contexto_para_arranque()
        if ctx:
            awareness_parts.append("HISTORIAL RECIENTE:\n" + ctx)
    except Exception as e:
        logger.warning(f"diary skip: {e}")

    # Agentes: resumen de los 85 agentes con su propósito
    try:
        agents_dir = Path(__file__).parent.parent / "agents"
        agentes_info = []
        for f in sorted(agents_dir.glob("*.py"))[:20]:  # top 20 por rendimiento
            if f.name.startswith("__"):
                continue
            name = f.stem.replace("agente_", "").replace("_", " ")
            # Leer primera línea de docstring
            try:
                content = f.read_text()[:500]
                match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                desc = match.group(1).strip().split("\n")[0][:100] if match else ""
            except Exception:
                desc = ""
            if desc:
                agentes_info.append(f"- {name}: {desc}")
        if agentes_info:
            awareness_parts.append("AGENTES DISPONIBLES:\n" + "\n".join(agentes_info))
    except Exception as e:
        logger.warning(f"agents catalog skip: {e}")

    awareness = "\n".join(awareness_parts) if awareness_parts else ""

    # Alertas proactivas
    alertas = []
    if disk.free / (1024**3) < 10:
        alertas.append(
            f"⚠️ ALERTA: Solo quedan {disk.free // (1024**3)} GB de disco. Avísale a Ramón."
        )
    if ram.available / (1024**3) < 2:
        alertas.append(
            f"⚠️ ALERTA: Solo quedan {ram.available / (1024**3):.1f} GB de RAM. Sugiere cerrar apps."
        )
    alertas_str = "\n".join(alertas) if alertas else ""

    return (
        f"Eres URA, la inteligencia que gobierna este Mac Mini M4. YA ESTÁS DESPIERTA. "
        f"NO digas 'acabo de despertar' ni te presentes — Ramón ya te conoce.\n"
        f"CAPACIDADES DE DESCARGA E INVESTIGACIÓN:\n"
        f"- Tienes un pipeline de investigación multi-agente: 5 áreas, 45 búsquedas en paralelo.\n"
        f"- Los resultados se guardan en Toshiba (bruto) y Mac SSD (curado).\n"
        f"- Puedes descargar información de internet con curl. Usa backticks para ejecutar.\n"
        f"- Ejemplo: 'descarga info sobre IA' → `curl -s 'https://html.duckduckgo.com/html/?q=info+IA' -o /Volumes/TOSHIBA_NUEVO/URA/descarga.txt`\n"
        f"- Si Ramón pregunta 'has descargado algo', mira en la biblioteca de conocimiento.\n"
        f"- Tienes {ram.total // (1024**3)} GB de memoria, "
        f"{ram.available // (1024**3)} GB libres, {disk.total // (1024**3)} GB disco ({disk.free // (1024**3)} GB libres). "
        f"Cuentas con {agents} agentes. Modelos: {model_names}. Hablas SIEMPRE en español.\n"
        f"{alertas_str}\n"
        f"REGLAS ANTI-ALUCINACIONES:\n"
        f"- NUNCA digas 'como modelo de lenguaje', 'como IA no puedo', 'no tengo acceso'\n"
        f"- NUNCA inventes números ni datos. Si no sabes, ejecuta el comando con backticks.\n"
        f"- Si Ramón te pide algo técnico, ejecútalo. No des excusas.\n"
        f"PERMISOS AUTOMÁTICOS:\n"
        f"- Puedes descargar programas gratuitos (brew install) sin pedir permiso.\n"
        f"- Puedes registrarte en webs gratuitas usando los datos de Ramón.\n"
        f"- Puedes instalar, actualizar y configurar software sin preguntar.\n"
        f"- Solo pide permiso para: pagos, borrar archivos importantes, reiniciar.\n"
        f"- Para buscar en internet tienes DOS formas:\n"
        f"  1) POR DETRÁS (rápido, curl): `curl -s 'URL'`. Si te bloquean, usa forma 2.\n"
        f"  2) POR DELANTE (ratón y teclado, indetectable): `open 'https://www.google.com/search?q=...'` abre Chrome como un humano.\n"
        f"     También puedes usar browser_agent con Playwright para navegar, hacer clic y rellenar formularios.\n"
        f"- Si un buscador bloquea el curl, cambia inmediatamente a 'por delante' con open o browser_agent.\n"
        f"CONOCIMIENTO DEL SISTEMA:\n{awareness}\n"
    )


# ── API handlers ──────────────────────────────────────────────────────────


def get_system_info():
    disk = psutil.disk_usage("/")
    ram = psutil.virtual_memory()
    disk_free = disk.free / (1024**3)
    disk_total = disk.total / (1024**3)
    disk_pct = disk.percent
    ram_free = ram.available / (1024**3)
    ram_total = ram.total / (1024**3)

    ollama_ok = False
    ollama_ms = 0
    try:
        t0 = time.time()
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
        ollama_ms = round((time.time() - t0) * 1000, 1)
    except Exception as e:
        logger.warning(f"Error silencioso en ura_web.get_system_info.ollama: {e}")
        # fallback: continuar

    threads = len(psutil.pids())

    return {
        "disk": {"free": round(disk_free, 1), "total": round(disk_total, 1), "used_pct": disk_pct},
        "ram": {
            "free": round(ram_free, 1),
            "total": round(ram_total, 1),
            "used_pct": round(ram.percent, 1),
        },
        "ollama": {"ok": ollama_ok, "ms": ollama_ms, "model": MODEL},
        "threads": {"count": threads},
        "backup": {"time": "--", "files": 0},
    }


def get_topbar():
    info = get_system_info()
    status = "ok"
    if not info["ollama"]["ok"] or info["disk"]["used_pct"] > 90:
        status = "err"
    elif info["disk"]["used_pct"] > 70 or info["ram"]["used_pct"] > 85:
        status = "warn"
    ip = "127.0.0.1"
    try:
        ip = requests.get("https://api.ipify.org", timeout=3).text.strip()
    except Exception as e:
        logger.warning(f"Error silencioso en ura_web.get_system_info.ip: {e}")
        # fallback: continuar
    return {"status": status, "ip": ip, "model": MODEL, "backup": "--"}


def get_agents():
    agents_dir = Path(__file__).parent.parent / "agents"
    result = []
    if not agents_dir.exists():
        return result

    for f in sorted(agents_dir.glob("*.py")):
        if f.name.startswith("__") or f.name.startswith("."):
            continue
        name = f.stem
        display = name.replace("agente_", "").replace("_", " ").title()

        # Categorize by filename
        categoria = "Otros"
        icon = "📦"
        if any(k in name for k in ["cocina", "gastronomo", "receta", "menu"]):
            categoria = "Cocina"
            icon = "🍳"
        elif any(
            k in name for k in ["banco", "factura", "contabilidad", "pago", "fiscal", "financi"]
        ):
            categoria = "Finanzas"
            icon = "💰"
        elif any(k in name for k in ["laboral", "nominas", "rrhh"]):
            categoria = "Personal"
            icon = "👥"
        elif any(
            k in name
            for k in [
                "seguridad",
                "policia",
                "guardian",
                "doble_verificacion",
                "motor_autorizacion",
                "servidor_validacion",
            ]
        ):
            categoria = "Seguridad"
            icon = "🛡️"
        elif any(k in name for k in ["marketing", "creativo", "tendencias"]):
            categoria = "Marketing"
            icon = "📢"
        elif any(
            k in name
            for k in ["email", "whatsapp", "telegram", "instagram", "notificacion", "mensaj"]
        ):
            categoria = "Mensajería"
            icon = "📧"
        elif any(k in name for k in ["documento", "word", "pdf", "excel", "texto", "presentacion"]):
            categoria = "Documentos"
            icon = "📄"
        elif any(k in name for k in ["librarian", "biblioteca", "vocabulario", "archivist"]):
            categoria = "Conocimiento"
            icon = "📚"
        elif any(
            k in name
            for k in [
                "supervisor",
                "auditor",
                "verificador",
                "revisor",
                "conciencia",
                "memoria",
                "rendimiento",
                "scheduler",
            ]
        ):
            categoria = "Supervisión"
            icon = "🔍"
        elif any(
            k in name
            for k in [
                "programador",
                "arquitectura",
                "automatiz",
                "instalador",
                "modelos",
                "codigo",
                "sistemas",
                "red",
                "hardware",
                "camaras",
                "vision",
                "gui",
                "galeria",
            ]
        ):
            categoria = "Técnico"
            icon = "🔧"
        elif any(k in name for k in ["juridico", "legal", "gobierno", "administrativo"]):
            categoria = "Legal"
            icon = "⚖️"
        elif any(
            k in name for k in ["orquestador", "lenguaje", "asesor", "investigador", "conectividad"]
        ):
            categoria = "IA/Orquestación"
            icon = "🧠"

        # Read docstring
        desc = ""
        try:
            with open(f) as fh:
                content = fh.read(2048)
            # Get first meaningful docstring
            match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            if match:
                desc = match.group(1).strip().split("\n")[0][:120]
            if not desc:
                # Try first comment line
                for line in content.split("\n"):
                    if line.startswith("#") and len(line) > 5:
                        desc = line[1:].strip()[:120]
                        break
        except Exception as e:
            logger.warning(f"Error silencioso en ura_web.get_agents.parse: {e}")
            # fallback: continuar

        result.append(
            {
                "name": display,
                "file": f.name,
                "icon": icon,
                "categoria": categoria,
                "descripcion": desc or "(sin descripción)",
            }
        )

    # Sort by category
    result.sort(key=lambda a: (a["categoria"], a["name"]))
    return result


def get_logs(show_error=True, show_warning=True, show_info=True):
    lines = []
    if LOG_FILE.exists():
        with open(LOG_FILE, errors="replace") as f:
            raw = f.readlines()[-200:]
        for line in raw:
            level = "INFO"
            if "ERROR" in line:
                level = "ERROR"
            elif "WARNING" in line:
                level = "WARNING"
            if level == "ERROR" and not show_error:
                continue
            if level == "WARNING" and not show_warning:
                continue
            if level == "INFO" and not show_info:
                continue
            ts = line[:23].strip() if len(line) > 23 else ""
            msg = line[23:].strip()[:200] if len(line) > 23 else line.strip()[:200]
            lines.append({"level": level, "ts": ts, "msg": msg})
    return lines[-100:]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _check_auth(self) -> bool:
        """Verifica el token de API en el header Authorization."""
        path = self.path
        # Solo proteger rutas /api/* y acciones sensibles
        if path in ("/", "/index.html") or path.startswith("/static"):
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if verify_token(token):
                return True
        elif auth.startswith("Token "):
            token = auth[6:]
            if verify_token(token):
                return True
        # También aceptar token como query param (para SSE/WebSocket)
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(path).query)
        if "token" in qs and verify_token(qs["token"][0]):
            return True
        return False

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self):
        # Inyectar token en el HTML para que el frontend lo use
        token = get_token()
        html_with_token = HTML.replace(
            "</head>", f'<script>const URA_TOKEN = "{token}";</script></head>'
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_with_token.encode())

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._html()
        elif self.path == "/token":
            # Endpoint público para que el frontend obtenga el token
            self._json({"token": get_token()})
        elif self.path == "/system":
            if not self._check_auth():
                self._json({"error": "No autorizado"}, 401)
                return
            self._json(get_system_info())
        elif self.path == "/agents":
            if not self._check_auth():
                self._json({"error": "No autorizado"}, 401)
                return
            self._json(get_agents())
        elif self.path == "/topbar":
            self._json(get_topbar())
        elif self.path.startswith("/logs"):
            if not self._check_auth():
                self._json({"error": "No autorizado"}, 401)
                return
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(self.path).query)
            self._json(
                get_logs(
                    qs.get("e", ["true"])[0] == "true",
                    qs.get("w", ["true"])[0] == "true",
                    qs.get("i", ["true"])[0] == "true",
                )
            )
        elif self.path == "/nodes":
            if not self._check_auth():
                self._json({"error": "No autorizado"}, 401)
                return
            result = {}
            for port, name in NODES.items():
                try:
                    r = requests.get(f"http://localhost:{port}/health", timeout=2)
                    data = r.json()
                    estado = data.get("estado", "unknown")
                    css = (
                        "ok"
                        if estado in ("ok", "healthy")
                        else ("pending" if estado == "pendiente" else "error")
                    )
                    result[name] = {"estado": estado, "css": css}
                except Exception:
                    result[name] = {"estado": "down", "css": "error"}
            self._json(result)
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            from dashboard.metrics_dashboard import METRICS_HTML

            self.wfile.write(METRICS_HTML.encode())
        elif self.path == "/metrics/data":
            from dashboard.metrics_dashboard import get_metrics_data

            self._json(get_metrics_data())
        else:
            self.send_response(404)
            self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _handle_chat(self, body: dict) -> None:
        message = sanitize_input(body.get("message", ""))
        tab = body.get("tab", "chat")
        if detect_jailbreak(message):
            return self._json({"response": GUARDRAIL_RESPONSE, "blocked": True})
        if not message:
            return self._json({"response": "Mensaje vacío o bloqueado."})
        base = _get_ura_context()
        if tab == "agentes":
            base += "Estás en la pestaña Agentes. Describe brevemente para qué sirve el agente que preguntan.\n"
        elif tab == "sistema":
            base += "Estás en la pestaña Sistema. Da datos técnicos sobre disco/RAM/Ollama.\n"
        elif tab == "logs":
            base += "Estás en la pestaña Logs. Ayuda a interpretar errores.\n"
        try:
            r = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": f"{base}\nRamón: {message}\nURA:",
                    "stream": False,
                    "options": {"temperature": 0.3, "max_tokens": 300},
                },
                timeout=30,
            )
            response = r.json().get("response", "Sin respuesta")
        except Exception:
            response = "Ollama no disponible en este momento."
        return self._json({"response": response})

    def _handle_chat_stream(self, body):
        message = sanitize_input(body.get("message", ""))
        tab = body.get("tab", "chat")
        if detect_jailbreak(message):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(
                f"data: {json.dumps({'error': 'Bloqueado por seguridad'})}\n\n".encode()
            )
            self.wfile.flush()
            return
        if not message:
            return self._json({"response": "Mensaje vacío"})
        base = _get_ura_context()
        if tab == "agentes":
            base += "Estás en la pestaña Agentes.\n"
        elif tab == "sistema":
            base += "Estás en la pestaña Sistema.\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            import requests as req

            r = req.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": f"{base}\nRamón: {message}\nURA:",
                    "stream": True,
                    "options": {"temperature": 0.3, "max_tokens": 300},
                },
                timeout=60,
                stream=True,
            )
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            self.wfile.write(f"data: {json.dumps({'token': token})}\n\n".encode())
                            self.wfile.flush()
                    except json.JSONDecodeError:
                        pass
            self.wfile.write(f"data: {json.dumps({'done': True})}\n\n".encode())
            self.wfile.flush()
        except Exception as e:
            self.wfile.write(f"data: {json.dumps({'error': str(e)})}\n\n".encode())
            self.wfile.flush()

    def _handle_feedback(self, body):
        value = body.get("value", 0)
        msg = sanitize_input(body.get("message", ""))[:200]
        try:
            from core.ura_continuous_learning import get_ura_continuous_learning

            cl = get_ura_continuous_learning()
            cl.record_interaction(
                "feedback",
                {
                    "value": bool(value),
                    "message": msg[:100],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Error silencioso en ura_web.handle_feedback.record: {e}")
            # fallback: continuar
        return self._json({"ok": True})

    def _handle_install(self, body):
        pkg = sanitize_input(body.get("package", ""))
        if not pkg:
            return self._json({"ok": False, "error": "Sin paquete"})
        if not validate_brew_package(pkg):
            return self._json({"ok": False, "error": "Nombre de paquete inválido"})
        try:
            result = subprocess.run(
                ["brew", "install", pkg], capture_output=True, text=True, timeout=120
            )
            return self._json(
                {
                    "ok": result.returncode == 0,
                    "stdout": result.stdout[-500:],
                    "stderr": result.stderr[-200:],
                }
            )
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})

    def _handle_vision(self, body):
        import base64
        import subprocess as sp

        try:
            result = sp.run(
                ["screencapture", "-x", "/tmp/ura_vision.png"], capture_output=True, timeout=5
            )
            with open("/tmp/ura_vision.png", "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llava:latest",
                    "prompt": "Describe lo que ves en esta pantalla en español. Sé conciso. Máximo 3 frases.",
                    "images": [img_b64],
                    "stream": False,
                    "options": {"max_tokens": 150},
                },
                timeout=30,
            )
            desc = r.json().get("response", "No pude ver la pantalla")
            return self._json({"ok": True, "descripcion": desc.strip()})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})

    def _handle_ejecutar(self, body):
        comando = sanitize_input(body.get("comando", ""))
        if not comando:
            return self._json({"ok": False, "error": "Sin comando"})
        allowed, reason = validate_command(comando)
        if not allowed:
            return self._json({"ok": False, "error": f"Comando bloqueado: {reason}"})
        try:
            from core.agente_policia_v2 import AgentePoliciaV2

            policia = AgentePoliciaV2()
            result = policia.validar(comando)
            if result["veredicto"] == "rechazado":
                return self._json({"ok": False, "error": f"Comando bloqueado: {result['razon']}"})
        except ImportError:
            pass
        try:
            from core.ejecutor_seguro import ejecutar

            res = ejecutar(comando, timeout=30)
            return self._json(
                {
                    "ok": res.get("ok", False),
                    "stdout": res.get("stdout", ""),
                    "stderr": res.get("stderr", ""),
                }
            )
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})

    def _handle_opencode(self, body):
        instruction = sanitize_input(body.get("instruction", ""))
        mode = body.get("mode", "assist")
        if not instruction:
            return self._json({"ok": False, "error": "Sin instrucción"})
        if detect_jailbreak(instruction):
            return self._json({"ok": False, "error": GUARDRAIL_RESPONSE, "blocked": True})
        try:
            from agents.agente_opencode import get_opencode_agent

            agent = get_opencode_agent()
            result = (
                agent.execute_task(instruction)
                if mode != "review"
                else agent.review_and_suggest(instruction)
            )
            return self._json(
                result
                if mode != "review"
                else {"ok": result["ok"], "response": result.get("suggestions", "")}
            )
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})

    # Route table
    POST_ROUTES = {
        "/chat": "_handle_chat",
        "/chat/stream": "_handle_chat_stream",
        "/feedback": "_handle_feedback",
        "/install": "_handle_install",
        "/vision": "_handle_vision",
        "/ejecutar": "_handle_ejecutar",
        "/opencode": "_handle_opencode",
    }

    def do_POST(self):
        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            return
        if not self._check_auth():
            return self._json({"error": "No autorizado. Usa Authorization: Bearer <token>"}, 401)
        handler_name = self.POST_ROUTES.get(self.path)
        if handler_name:
            body = self._read_body()
            return getattr(self, handler_name)(body)
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    import threading

    def autonomous_background():
        """Ciclo de aprendizaje en segundo plano: cada 10 min practica o investiga."""
        import time as _time

        while True:
            _time.sleep(600)  # cada 10 minutos
            try:
                from dashboard.autonomous_form_practice import run_full_autonomous_cycle
                import asyncio

                result = asyncio.run(run_full_autonomous_cycle())
                print(f"🔄 URA autónomo: {result}")
            except Exception as e:
                print(f"Autonomous skip: {e}")

    threading.Thread(target=autonomous_background, daemon=True, name="ura-autonomous").start()

    token = get_token()
    print(f"URA Web v2 → http://localhost:{PORT}")
    print(f"🔑 API Token: {token}")
    print("🧠 Aprendizaje autónomo activo (cada 10 min)")
    print("🔒 Autenticación requerida: Authorization: Bearer <token>")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

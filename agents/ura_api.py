#!/usr/bin/env python3
"""URA API — Endpoint universal, cuarentena, evolucion, recursos GX10."""

import json
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

URA_TOKEN = os.environ.get("URA_TOKEN", "ura_blackwell_2026")
HOME = os.path.expanduser("~")


def check_token(h):
    return h.get("Authorization", "").replace("Bearer ", "") == URA_TOKEN


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path
        if p == "/api/evolucion":
            if not check_token(self.headers):
                self.js(403, {"error": "No autorizado"})
                return
            sf = Path("/opt/ura/data/sugerencias.json")
            sugs = json.loads(sf.read_text()) if sf.exists() else []
            ac = Path(f"{HOME}/URA/ura_ia_1972/logs/auto_conciencia.log")
            tm = []
            if ac.exists():
                for line in ac.read_text().splitlines()[-30:]:
                    if "ms" in line and "[" in line:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            tm.append(
                                {
                                    "timestamp": parts[0],
                                    "nombre": parts[3].strip(":"),
                                    "duracion_ms": parts[2]
                                    .replace("[", "")
                                    .replace("]", "")
                                    .replace("ms", ""),
                                }
                            )
            self.js(200, {"sugerencias": len(sugs), "tests_mcp": tm})
        elif p == "/api/cuarentena":
            if not check_token(self.headers):
                self.js(403, {"error": "No autorizado"})
                return
            items = [f for f in os.listdir("/opt/ura/cuarentena") if not f.endswith(".meta")]
            self.js(200, items)
        elif p == "/api/gx10/recursos":
            if not check_token(self.headers):
                self.js(403, {"error": "No autorizado"})
                return
            try:
                r = subprocess.run(
                    ["ssh", "ramon@10.164.1.99", "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                cpu = r.stdout.strip()[:10] or "0"
                r = subprocess.run(
                    ["ssh", "ramon@10.164.1.99", "free -m | awk '/Mem/ {print $3}'"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                ram = r.stdout.strip() or "0"
                r = subprocess.run(
                    ["ssh", "ramon@10.164.1.99", "df -h / | tail -1 | awk '{print $5}'"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                dsk = r.stdout.strip() or "0"
                r = subprocess.run(
                    [
                        "ssh",
                        "ramon@10.164.1.99",
                        "nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader 2>/dev/null || echo '0,0'",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                g = r.stdout.strip().split(",")
                self.js(
                    200,
                    {
                        "cpu": cpu + "%",
                        "ram_mb": ram + " MB",
                        "disco": dsk,
                        "gpu_temp": (g[0] + "C") if len(g) > 0 else "0C",
                        "gpu_util": (g[1].strip() + "%") if len(g) > 1 else "0%",
                    },
                )
            except Exception:
                self.js(
                    200,
                    {
                        "cpu": "N/A",
                        "ram_mb": "N/A",
                        "disco": "N/A",
                        "gpu_temp": "N/A",
                        "gpu_util": "N/A",
                    },
                )
        else:
            self.js(
                200,
                {
                    "status": "ok",
                    "endpoints": [
                        "/api/evolucion",
                        "/api/cuarentena",
                        "/api/gx10/recursos",
                        "/api/openclaw/ejecutar",
                    ],
                },
            )

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        p, a = self.path, body.get("accion", "")
        args, comando = body.get("args", []), body.get("comando", "")
        if p == "/api/cuarentena/eliminar":
            if not check_token(self.headers):
                self.js(403, {"error": "No autorizado"})
                return
            ruta = os.path.join("/opt/ura/cuarentena", body.get("item", ""))
            if os.path.exists(ruta) and not body.get("item", "").endswith(".meta"):
                os.remove(ruta)
                self.js(200, {"status": "eliminado"})
            else:
                self.js(404, {"error": "No encontrado"})
            return
        r = {"ok": False, "resultado": "", "error": ""}
        try:
            if p == "/api/openclaw/ejecutar" or comando:
                cmd = comando or args[0] if args else ""
                if cmd:
                    x = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    r = {
                        "output": x.stdout[:2000],
                        "error": x.stderr[:500],
                        "success": x.returncode == 0,
                    }
                else:
                    r = {"error": "Falta comando"}
            elif a == "volumen":
                if args:
                    subprocess.run(
                        ["osascript", "-e", f"set volume output volume {args[0]}"], timeout=5
                    )
                    r = {"ok": True, "resultado": f"Volumen: {args[0]}"}
                else:
                    x = subprocess.run(
                        ["osascript", "-e", "get volume settings"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    r = {"ok": True, "resultado": x.stdout.strip()}
            elif a == "abrir":
                subprocess.run(
                    ["osascript", "-e", f'tell application "{args[0]}" to activate'], timeout=10
                )
                r = {"ok": True, "resultado": f"{args[0]} abierto"}
            elif a == "cerrar":
                subprocess.run(
                    ["osascript", "-e", f'tell application "{args[0]}" to quit'], timeout=10
                )
                r = {"ok": True, "resultado": f"{args[0]} cerrado"}
            elif a in ("camaras",):
                x = subprocess.run(
                    ["curl", "-s", "http://10.164.1.99:1984/api/streams"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                r = {"ok": True, "resultado": x.stdout[:2000]}
            elif a == "sistema":
                x = subprocess.run(
                    ["ssh", "ramon@10.164.1.99", "uptime && free -h | head -2"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                r = {"ok": True, "resultado": x.stdout or x.stderr}
            else:
                r = {"error": "Accion desconocida"}
        except Exception as e:
            r = {"error": str(e)}
        self.js(200, r)

    def js(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass


HTTPServer(("0.0.0.0", 9090), Handler).serve_forever()

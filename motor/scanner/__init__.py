import logging, time, json
from pathlib import Path
from datetime import datetime
from core.state import ScanResult
from core.config import UraConfig
from scanner.sliding_window import SlidingWindow
from scanner.diff_detector import compute_diff
from scanner.calibration import Calibration
from scanner.collector_red import escanear_red
from scanner.collector_hw_vm import escanear_hw_vm
from scanner.collector_hw_asus import escanear_hw_asus
from scanner.collector_asus import escanear_asus

log = logging.getLogger("ura.scanner")

class Scanner:
    def __init__(self, config: UraConfig):
        self.config = config
        self.sliding = SlidingWindow()
        self.cal = Calibration(config)
        self._ventana_previa = {}

    def run(self) -> ScanResult:
        t0 = time.time()
        r = ScanResult(timestamp=datetime.utcnow().isoformat()+"Z")
        r.hostname = self._get_hostname()
        r.servicios = self._check_servicios()
        r.recursos = self._check_recursos()
        r.contenedores = self._check_contenedores()
        r.red = escanear_red(self.config)
        if self.config.is_vm:
            r.hw_health = escanear_hw_vm()
        else:
            asus_info = escanear_asus(self.config)
            r.hw_health = escanear_hw_asus(asus_info.get("temp_gpu"))
        r.health_score = self._calcular_health_score(r)
        r.diff_total, r.anomalias = self._detectar_cambios(r)
        r.flapping = self.sliding.add_and_check(r)
        if self.cal.hay_baseline:
            r.anomalias += self.cal.detectar_anomalias(r)
        r.calibration_status = "learning" if not self.cal.hay_baseline else "active"
        r.duplicados = self._detectar_duplicados()
        r.snapshot_hash = self._tomar_snapshot_hash()
        log.info("scan %.2fs score=%.1f diff=%d", time.time()-t0, r.health_score, r.diff_total)
        return r

    def _get_hostname(self):
        try: import socket; return socket.gethostname()
        except: return "unknown"

    def _check_servicios(self) -> dict:
        s = {}
        for svc in ["sshd", "docker", "qdrant", "n8n", "searxng", "vane"]:
            try:
                import subprocess
                r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
                s[svc] = r.stdout.strip()
            except: s[svc] = "unknown"
        s["opencode"] = self._check_opencode()
        return s

    def _check_opencode(self) -> str:
        try:
            import subprocess
            r = subprocess.run(["systemctl", "is-active", "opencode"], capture_output=True, text=True, timeout=3)
            return r.stdout.strip()
        except: return "unknown"

    def _check_recursos(self) -> dict:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "ram_pct": round(mem.percent, 1),
            "ram_gb": round(mem.total / 1e9, 1),
            "ram_available_gb": round(mem.available / 1e9, 1),
            "disk_pct": round(disk.percent, 1),
            "disk_gb": round(disk.total / 1e9, 1),
            "disk_free_gb": round(disk.free / 1e9, 1),
            "load_1m": round(psutil.getloadavg()[0], 2),
            "zombies": sum(1 for p in psutil.process_iter() if p.status() == "zombie"),
        }

    def _check_contenedores(self) -> dict:
        c = {"total": 0, "running": 0, "exited": 0}
        try:
            import subprocess, json
            r = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"],
                               capture_output=True, text=True, timeout=10)
            for line in r.stdout.strip().split("\n"):
                if not line: continue
                parts = line.split("\t")
                if len(parts) == 2:
                    c["total"] += 1
                    if parts[1] == "running": c["running"] += 1
                    else: c["exited"] += 1
        except: pass
        return c

    def _detectar_cambios(self, actual: ScanResult) -> tuple:
        if not self._ventana_previa:
            self._ventana_previa = {"servicios": dict(actual.servicios),
                                     "recursos": dict(actual.recursos),
                                     "contenedores": dict(actual.contenedores),
                                     "hw_health": dict(actual.hw_health)}
            return 0, []
        diff_count, anomalias = compute_diff(
            actual={"servicios": dict(actual.servicios), "recursos": dict(actual.recursos),
                    "contenedores": dict(actual.contenedores), "hw_health": dict(actual.hw_health)},
            prev=self._ventana_previa
        )
        self._ventana_previa = {"servicios": dict(actual.servicios),
                                 "recursos": dict(actual.recursos),
                                 "contenedores": dict(actual.contenedores),
                                 "hw_health": dict(actual.hw_health)}
        return diff_count, anomalias

    def _calcular_health_score(self, r: ScanResult) -> float:
        score = 100.0
        fallados = sum(1 for s in r.servicios.values() if s not in ("active", "ok"))
        score -= fallados * 10
        if r.recursos.get("ram_pct", 0) > 90: score -= 15
        elif r.recursos.get("ram_pct", 0) > 80: score -= 10
        if r.recursos.get("disk_pct", 0) > 90: score -= 15
        elif r.recursos.get("disk_pct", 0) > 80: score -= 10
        score -= r.recursos.get("zombies", 0) * 5
        score -= r.red.get("latencia_ms", 0) / 20
        score -= len(r.flapping) * 5
        if not r.hw_health.get("ok", True): score -= 15
        score -= r.diff_total * 2
        return max(0, round(score, 1))

    def _detectar_duplicados(self) -> dict:
        d = {}
        try:
            import subprocess
            r = subprocess.run(["ps", "-eo", "comm="], capture_output=True, text=True, timeout=5)
            vistos = {}
            for line in r.stdout.strip().split("\n"):
                c = line.strip()
                if not c: continue
                vistos[c] = vistos.get(c, 0) + 1
            dups = {k: v for k, v in vistos.items() if v > 1 and k in ("opencode", "python3", "node", "docker")}
            if dups: d["procesos"] = dups
        except: pass
        return d

    def _tomar_snapshot_hash(self) -> str:
        import hashlib, os
        h = hashlib.sha256()
        for archivo in ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"]:
            if os.path.isfile(archivo):
                h.update(open(archivo, "rb").read())
        return h.hexdigest()[:16]

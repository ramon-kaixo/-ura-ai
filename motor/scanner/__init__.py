import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor
from motor.core.state import ScanResult
from motor.scanner.calibration import Calibration
from motor.scanner.collector_asus import escanear_asus
from motor.scanner.collector_hw_asus import escanear_hw_asus
from motor.scanner.collector_hw_vm import escanear_hw_vm
from motor.scanner.collector_red import escanear_red
from motor.scanner.diff_detector import compute_diff
from motor.scanner.sliding_window import SlidingWindow

log = logging.getLogger("ura.scanner")
_executor = SubprocessExecutor()

SERVICIOS_SYSTEMD = ["sshd", "docker", "opencode"]
SERVICIOS_DOCKER = ["qdrant", "n8n", "searxng", "vane", "agent-search"]
DOCKER_ALIASES = {"vane": "perplexica-vane-1", "agent-search": "agent-search-agent-search-1"}
RUTAS_CONFIG_OPENCODE = ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"]


class Scanner:
    """Escáner principal del sistema: servicios, recursos, red y hardware."""

    def __init__(self, config: UraConfig) -> None:
        self.config = config
        self.sliding = SlidingWindow()
        self.cal = Calibration(config)
        self._ventana_previa = {}

    @staticmethod
    def _es_fisico() -> bool:
        """Determina si el hardware es físico (no VM)."""
        try:
            r = _executor.run(["systemd-detect-virt"], timeout=5)
            return "none" in r.stdout.strip()
        except Exception as e:
            log.debug("systemd-detect-virt falló: %s", e)
            try:
                with open("/proc/cpuinfo") as f:  # noqa: PTH123
                    return "hypervisor" not in f.read()
            except Exception as e2:
                log.debug("lectura cpuinfo falló: %s", e2)
                return True

    def run(self) -> ScanResult:
        """Ejecuta el escaneo completo y devuelve un ScanResult."""
        t0 = time.time()
        r = ScanResult(timestamp=datetime.now(UTC).isoformat() + "Z")
        r.hostname = self._get_hostname()
        r.servicios = self._check_servicios()
        r.recursos = self._check_recursos()
        r.contenedores = self._check_contenedores()
        dc = self._list_docker_containers()
        r.contenedores_ko = [name for name, st in dc.items() if st != "running"]
        r.red = escanear_red(self.config)
        is_vm = self.config.is_vm and not self._es_fisico()
        if is_vm:
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
        r.orphans = self._detectar_orphans()
        r.systemd_failed = self._detectar_systemd_failed()
        r.snapshot_hash = self._tomar_snapshot_hash()
        r.ok = True
        log.info(
            "scan %.2fs score=%.1f diff=%d orphans=%d failed=%d",
            time.time() - t0,
            r.health_score,
            r.diff_total,
            len(r.orphans),
            len(r.systemd_failed),
        )
        return r

    def _get_hostname(self):
        """Obtiene el hostname del sistema."""
        try:
            import socket

            return socket.gethostname()
        except Exception as e:
            log.warning("no se pudo obtener hostname: %s", e)
            return "unknown"

    def _check_servicios(self) -> dict:
        """Comprueba estado de servicios systemd y docker."""
        s = {}
        for svc in SERVICIOS_SYSTEMD:
            try:
                r = _executor.run(["systemctl", "is-active", svc], timeout=5)
                out = r.stdout.strip()
                s[svc] = "not_found" if out in ("unknown", "inactive") and not self._unit_exists(svc) else out
            except FileNotFoundError:
                s[svc] = "not_found"
            except Exception as e:
                log.debug("systemctl is-active %s fallo: %s", svc, e)
                s[svc] = "unknown"
        docker_containers = self._list_docker_containers()
        for svc in SERVICIOS_DOCKER:
            name = DOCKER_ALIASES.get(svc, svc)
            state = docker_containers.get(name, "not_found")
            s[svc] = "active" if state == "running" else state
        return s

    def _unit_exists(self, name: str) -> bool:
        """Verifica si existe una unit systemd."""
        try:
            r = _executor.run(
                ["systemctl", "list-units", "--all", "--type=service", f"{name}.service", "--no-legend"],
                timeout=5,
            )
            return bool(r.stdout.strip())
        except Exception as e:
            log.debug("systemctl list-units %s falló: %s", name, e)
            return False

    def _list_docker_containers(self) -> dict:
        """Lista contenedores docker y su estado."""
        try:
            r = _executor.run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"], timeout=10)
            return dict(line.split("\t") for line in r.stdout.strip().split("\n") if "\t" in line)
        except Exception as e:
            log.debug("docker ps falló: %s", e)
            return {}

    def _check_recursos(self) -> dict:  # noqa: C901
        """Recolecta métricas de RAM, disco, CPU y zombies."""
        try:
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
                "ncpu": psutil.cpu_count(),
                "zombies": sum(1 for p in psutil.process_iter() if p.status() == "zombie"),
            }
        except ImportError:
            log.debug("psutil no disponible, fallback a /proc")
        except Exception as e:
            log.warning("psutil falló: %s", e)

        meminfo = {}
        try:
            with open("/proc/meminfo") as f:  # noqa: PTH123
                meminfo = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in f if ":" in l)}
        except Exception as e:
            log.warning("fallo lectura /proc/meminfo: %s", e)
        mem_total = meminfo.get("MemTotal", 1) * 1024
        mem_avail = meminfo.get("MemAvailable", 0) * 1024

        load = 0.0
        try:
            with open("/proc/loadavg") as f:  # noqa: PTH123
                load = float(f.read().split()[0])
        except Exception as e:
            log.debug("fallo lectura /proc/loadavg: %s", e)
        ncpu = os.cpu_count() or 1

        try:
            s = os.statvfs("/")
            disk_total = s.f_frsize * s.f_blocks
            disk_free = s.f_frsize * s.f_bfree
            disk_pct = round((1 - disk_free / disk_total) * 100, 1) if disk_total else 0
        except Exception as e:
            log.warning("fallo statvfs: %s", e)
            disk_total = disk_free = disk_pct = 0

        zombies = 0
        try:
            for p in Path("/proc").iterdir():
                if p.name.isdigit():
                    try:
                        texto = (p / "status").read_text()
                        if any(line.startswith("State:") and "Z" in line for line in texto.split("\n")):
                            zombies += 1
                    except Exception as e:
                        log.debug("fallo lectura proc status: %s", e)
        except Exception as e:
            log.debug("fallo iteracion /proc: %s", e)

        return {
            "ram_pct": round((1 - mem_avail / mem_total) * 100, 1),
            "ram_gb": round(mem_total / 1e9, 1),
            "ram_available_gb": round(mem_avail / 1e9, 1),
            "disk_pct": disk_pct,
            "disk_gb": round(disk_total / 1e9, 1),
            "disk_free_gb": round(disk_free / 1e9, 1),
            "load_1m": load,
            "ncpu": ncpu,
            "zombies": zombies,
        }

    def _check_contenedores(self) -> dict:
        """Cuenta contenedores docker por estado."""
        c = {"total": 0, "running": 0, "exited": 0}
        try:
            r = _executor.run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"], timeout=10)
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) == 2:
                    c["total"] += 1
                    if parts[1] == "running":
                        c["running"] += 1
                    else:
                        c["exited"] += 1
        except Exception as e:
            log.debug("docker ps (contenedores) falló: %s", e)
        return c

    def _detectar_cambios(self, actual: ScanResult) -> tuple:
        """Compara estado actual vs ventana previa y devuelve (diff_count, anomalias)."""
        snap = {
            "servicios": dict(actual.servicios),
            "recursos": dict(actual.recursos),
            "contenedores": dict(actual.contenedores),
            "hw_health": dict(actual.hw_health),
        }
        if not self._ventana_previa:
            self._ventana_previa = snap
            return 0, []
        diff_count, anomalias = compute_diff(actual=snap, prev=self._ventana_previa)
        self._ventana_previa = snap
        return diff_count, anomalias

    def _calcular_health_score(self, r: ScanResult) -> float:
        """Calcula health score en base a servicios, recursos y anomalías."""
        score = 100.0
        fallados = sum(1 for s in r.servicios.values() if s not in ("active", "ok", "not_found"))
        score -= fallados * 10
        ram = r.recursos.get("ram_pct", 0)
        if ram > 90:
            score -= 15
        elif ram > 80:
            score -= 10
        disk = r.recursos.get("disk_pct", 0)
        if disk > 90:
            score -= 15
        elif disk > 80:
            score -= 10
        score -= r.recursos.get("zombies", 0) * 5
        score -= r.red.get("latencia_ms", 0) / 20
        score -= len(r.flapping) * 5
        if not r.hw_health.get("ok", True):
            score -= 15
        score -= r.diff_total * 2
        return max(0, round(score, 1))

    def _detectar_duplicados(self) -> dict:
        """Detecta procesos duplicados (opencode, node, docker)."""
        d = {}
        try:
            r = _executor.run(["ps", "-eo", "args="], timeout=5)
            vistos = {}
            for line in r.stdout.strip().split("\n"):
                args = line.strip()
                if not args:
                    continue
                clave = args.split()[0] if args.split() else args
                if clave in ("opencode", "node", "docker"):
                    vistos[args] = vistos.get(args, 0) + 1
            dups = {k: v for k, v in vistos.items() if v > 1}
            if dups:
                d["procesos"] = dups
        except Exception as e:
            log.debug("deteccion duplicados falló: %s", e)
        return d

    def _tomar_snapshot_hash(self) -> str:
        """Calcula hash SHA256 de los archivos de configuración de opencode."""
        import hashlib

        h = hashlib.sha256()
        for archivo in RUTAS_CONFIG_OPENCODE:
            try:
                with open(archivo, "rb") as f:  # noqa: PTH123
                    h.update(f.read())
            except OSError:
                pass
        return h.hexdigest()[:16]

    def _detectar_orphans(self) -> list:  # noqa: C901
        """Detecta PIDs huérfanos, hijos de padres muertos, docker dangling y systemd falladas."""
        orphans = []
        try:
            for p in Path("/var/run").glob("*.pid"):
                try:
                    pid = int(p.read_text().strip())
                    if not Path(f"/proc/{pid}").exists():
                        orphans.append({"pid_file": str(p), "pid": pid, "tipo": "stale_pid"})
                except (ValueError, OSError) as e:
                    log.debug("fallo procesar pid file %s: %s", p, e)
        except Exception as e:
            log.debug("fallo glob /var/run/*.pid: %s", e)

        try:
            import psutil

            current_pids = {p.info["pid"] for p in psutil.process_iter(["pid", "ppid", "name"])}
            for proc in psutil.process_iter(["pid", "ppid", "name"]):
                ppid = proc.info["ppid"]
                if ppid != 1 and ppid not in current_pids:
                    name = proc.info["name"] or "?"
                    orphans.append(
                        {
                            "tipo": "hijo_huertano",
                            "pid": proc.info["pid"],
                            "ppid": ppid,
                            "name": name,
                        },
                    )
        except (ImportError, Exception) as e:
            log.debug("deteccion hijos huerfanos fallo: %s", e)

        try:
            r = _executor.run(["docker", "images", "-f", "dangling=true", "-q"], timeout=10)
            dangling = [i for i in r.stdout.strip().split("\n") if i]
            if dangling:
                orphans.append({"tipo": "docker_dangling", "cantidad": len(dangling)})
        except Exception as e:
            log.debug("deteccion docker dangling falló: %s", e)

        try:
            r = _executor.run(["systemctl", "list-units", "--state=failed", "--no-legend"], timeout=10)
            failed = [
                l.split()[0].lstrip("●").strip() or l.split()[1] for l in r.stdout.strip().split("\n") if l.strip()
            ]
            if failed:
                orphans.append({"tipo": "systemd_failed", "unidades": failed[:10]})
        except Exception as e:
            log.debug("deteccion systemd failed falló: %s", e)

        return orphans

    def _detectar_systemd_failed(self) -> list:
        """Devuelve lista de unidades systemd en estado failed."""
        try:
            r = _executor.run(["systemctl", "list-units", "--state=failed", "--no-legend"], timeout=10)
            return [l.split()[0].lstrip("●").strip() or l.split()[1] for l in r.stdout.strip().split("\n") if l.strip()]
        except Exception as e:
            log.debug("systemctl list-failed falló: %s", e)
            return []

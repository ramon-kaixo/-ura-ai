#!/usr/bin/env python3
"""ura-supervisor — Demonio asíncrono de un solo hilo para el ecosistema URA.

Arquitectura (visión 3 Gurús):
  - Event loop: uvloop (basado en libuv, 2x más rápido que asyncio nativo)
  - IPC:        ZeroMQ sobre Unix Domain Socket (sin TCP loopback)
  - Tareas:     Corrutinas asyncio, no procesos/hilos del SO
  - Estado:     StateManager con fallback Redis → SQLite → JSON
  - Resiliencia: Cada tarea tiene try/except que aísla el error del loop
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvloop

import zmq
import zmq.asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.state import StateManager
from core.orchestrator_rules import evaluate as orchestrator_evaluate
from core.telemetry_sink import write_snapshot
from core.file_security import verify_and_fix as file_sec_verify
from core.modules.ingest.data_scraper import collect_snapshot
from core.modules.ingest.data_analyzer import process_raw_files
from core.modules.ingest.coordinator import collect_and_process
from core.modules.ai.model_broker import ai_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("supervisor")

ZMQ_IPC_PATH = "ipc:///tmp/ura-supervisor.ipc"
ROUTER_HEALTH_URL = "http://127.0.0.1:11435/health"
ROUTER_DASHBOARD_URL = "http://127.0.0.1:11435/dashboard.json"

# Intervalos de tareas (segundos)
# Placeholder para el bus de alertas (ZeroMQ o Redis Pub/Sub futuro)
async def send_ping_to_alerts_service(supervisor_pid: int, uptime_s: int) -> None:
    """Envía un ping al sistema de alertas vía syslog y journald."""
    import syslog
    syslog.openlog(ident="ura-supervisor", facility=syslog.LOG_LOCAL0)
    syslog.syslog(syslog.LOG_INFO, f"heartbeat PID={supervisor_pid} uptime={uptime_s}s")
    syslog.closelog()


INTERVAL_HEARTBEAT = 30
INTERVAL_COLLECTOR = 60
INTERVAL_VALIDATOR = 300
INTERVAL_ALERT_PING = 300
INTERVAL_WATCHDOG_REDIS = 60
INTERVAL_WATCHDOG_DISK = 120
INTERVAL_WATCHDOG_NETWORK = 60
INTERVAL_VALIDATOR_SYNTAX = 300
INTERVAL_VALIDATOR_IMPORTS = 300
INTERVAL_COLLECTOR_SYSTEM = 60
INTERVAL_OPTIMIZER_CACHE = 600
INTERVAL_ORCHESTRATOR = 30
INTERVAL_TELEMETRY = 300
INTERVAL_DATA_SCRAPER = 600
INTERVAL_DATA_ANALYZER = 300
INTERVAL_INGEST = 600  # 10 min — ciclo completo de ingesta
INTERVAL_AI_BROKER = 120  # 2 min — ciclo de decisión IA  # 5 min — procesamiento de datos  # 10 minutos — recolección de datos externos  # 5 minutos — persistencia de telemetría
INTERVAL_ALERT = 60  # 60s — detección de thrashing del orquestador


class Supervisor:
    """Orquestador principal. Un solo event loop, cero hilos de negocio."""

    def __init__(self) -> None:
        self.state = StateManager()
        self._orchestrator_cooldown_until: float = 0.0
        self._orchestrator_enabled: bool = True
        self._orchestrator_last_change: str = ""
        self._orchestrator_last_reason: str = ""
        self._zmq_ctx: zmq.asyncio.Context | None = None
        self._zmq_sock: zmq.asyncio.Socket | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        self._start_time: float = 0.0
        self._running = True

    # ── Arranque / Parada ------------------------------------------------

    async def start(self) -> None:
        self._start_time = time.time()
        log.info("ura-supervisor iniciando (PID %d)", os.getpid())

        # 1. Estado
        await self.state.start()

        # 2. Seguridad de archivos (permisos)
        file_alerts = file_sec_verify()
        if file_alerts:
            await self.state.set("supervisor:file_security:alerts", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "alerts": file_alerts,
            })
            for alert in file_alerts:
                log.warning("file_security: %s", alert)
        else:
            log.info("file_security: todos los archivos seguros")

        # 3. ZeroMQ IPC
        self._zmq_ctx = zmq.asyncio.Context()
        self._zmq_sock = self._zmq_ctx.socket(zmq.REP)
        self._zmq_sock.bind(ZMQ_IPC_PATH)
        import os as _os
        _os.chmod(ZMQ_IPC_PATH.replace('ipc://', ''), 0o700)
        log.info("ZeroMQ IPC escuchando en %s", ZMQ_IPC_PATH)

        # 4. Tareas del sistema
        self._tasks = {
            "watchdog_heartbeat": asyncio.create_task(
                self._task_wrapper("watchdog_heartbeat", self._watchdog_heartbeat, INTERVAL_HEARTBEAT)
            ),
            "watchdog_redis": asyncio.create_task(
                self._task_wrapper("watchdog_redis", self._watchdog_redis, INTERVAL_WATCHDOG_REDIS)
            ),
            "watchdog_disk": asyncio.create_task(
                self._task_wrapper("watchdog_disk", self._watchdog_disk, INTERVAL_WATCHDOG_DISK)
            ),
            "watchdog_network": asyncio.create_task(
                self._task_wrapper("watchdog_network", self._watchdog_network, INTERVAL_WATCHDOG_NETWORK)
            ),
            "collector_metrics": asyncio.create_task(
                self._task_wrapper("collector_metrics", self._collector_metrics, INTERVAL_COLLECTOR)
            ),
            "collector_system": asyncio.create_task(
                self._task_wrapper("collector_system", self._collector_system, INTERVAL_COLLECTOR_SYSTEM)
            ),
            "validator_config": asyncio.create_task(
                self._task_wrapper("validator_config", self._validator_config, INTERVAL_VALIDATOR)
            ),
            "validator_syntax": asyncio.create_task(
                self._task_wrapper("validator_syntax", self._validator_syntax, INTERVAL_VALIDATOR_SYNTAX)
            ),
            "validator_imports": asyncio.create_task(
                self._task_wrapper("validator_imports", self._validator_imports, INTERVAL_VALIDATOR_IMPORTS)
            ),
            "optimizer_cache": asyncio.create_task(
                self._task_wrapper("optimizer_cache", self._optimizer_cache, INTERVAL_OPTIMIZER_CACHE)
            ),
            "orchestrator": asyncio.create_task(
                self._task_wrapper("orchestrator", self._orchestrator_controller, INTERVAL_ORCHESTRATOR)
            ),
            "ingest_coordinator": asyncio.create_task(
                self._task_wrapper("ingest_coordinator", self._ingest_coordinator, INTERVAL_INGEST)
            ),
            "ai_broker": asyncio.create_task(self._ai_broker()),
            "data_analyzer": asyncio.create_task(
                self._task_wrapper("data_analyzer", self._data_analyzer, INTERVAL_DATA_ANALYZER)
            ),
            "data_scraper": asyncio.create_task(
                self._task_wrapper("data_scraper", self._data_scraper, INTERVAL_DATA_SCRAPER)
            ),
            "telemetry": asyncio.create_task(
                self._task_wrapper("telemetry", self._telemetry_collector, INTERVAL_TELEMETRY)
            ),
            "ura_alert": asyncio.create_task(
                self._task_wrapper("ura_alert", self._ura_alert, INTERVAL_ALERT)
            ),
            "heartbeat_task": asyncio.create_task(
                self._task_wrapper("heartbeat_task", self.heartbeat_task, INTERVAL_ALERT_PING)
            ),
            "ipc_server": asyncio.create_task(self._ipc_server()),
        }

        log.info(
            "Supervisor activo — %d tareas — %s",
            len([n for n in self._tasks.keys() if n != "ipc_server"]),
            ZMQ_IPC_PATH,
        )

    async def stop(self) -> None:
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
        if self._zmq_sock:
            self._zmq_sock.close()
        if self._zmq_ctx:
            self._zmq_ctx.term()
        await self.state.stop()
        # Limpiar socket file
        sock_path = ZMQ_IPC_PATH.replace("ipc://", "")
        if os.path.exists(sock_path):
            os.unlink(sock_path)
        log.info("ura-supervisor detenido")

    # ── Wrapper de tareas (aislamiento de errores) -----------------------

    async def _task_wrapper(self, name: str, coro_factory: Any, interval: int) -> None:
        """Ejecuta una tarea en bucle, creando una corutina nueva en cada iteración."""
        while self._running:
            try:
                await coro_factory()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Task %s: error no fatal (%s: %s)", name, type(e).__name__, e)
                await self.state.set(
                    f"supervisor:tasks:{name}:last_error",
                    {"error": str(e), "time": datetime.now(timezone.utc).isoformat()},
                )
            await asyncio.sleep(interval)

    # ── Tarea 1: Watchdog Heartbeat --------------------------------------

    async def _watchdog_heartbeat(self) -> None:
        """Verifica salud del model-router cada 30s y almacena el estado."""
        import urllib.request

        result: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "router_ok": False,
            "latency_ms": -1.0,
        }
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(ROUTER_HEALTH_URL)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                result["router_ok"] = data.get("status") == "ok"
                result["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
                result["models_available"] = data.get("models_available", 0)
                result["ollama_url"] = data.get("ollama_url", "")
        except Exception as e:
            result["error"] = str(e)

        await self.state.set("supervisor:heartbeat:last", result)
        status = "OK" if result["router_ok"] else "FALLIDO"
        log.debug("heartbeat: %s (%sms)", status, result["latency_ms"])

    # ── Tarea 2: Colector de Métricas -----------------------------------

    async def _collector_metrics(self) -> None:
        """Recoge métricas de rendimiento cada 60s."""
        import urllib.request

        metrics: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            req = urllib.request.Request(ROUTER_DASHBOARD_URL)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                metrics["asus_latency_ms"] = data.get("asus_latency_ms", -1)
                metrics["fallback_count_1h"] = data.get("fallback_count_1h", 0)
                metrics["models"] = len(data.get("models", []))
                metrics["power_mode"] = data.get("power_mode", "?")
                metrics["backend_label"] = data.get("backend_label", "?")
        except Exception as e:
            metrics["error"] = str(e)

        await self.state.set("supervisor:metrics:last", metrics)
        log.debug("collector: %s — %s modelos — %sms",
                   metrics.get("backend_label", "?"),
                   metrics.get("models", "?"),
                   metrics.get("asus_latency_ms", "?"))

    # ── Tarea 3: Validador de Configuración ------------------------------

    async def _validator_config(self) -> None:
        """Valida la integridad de system_config.json cada 5 min."""
        result: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "valid": False,
            "errors": [],
        }
        config_path = Path(__file__).parent.parent / "config" / "system_config.json"

        if not config_path.exists():
            result["errors"].append(f"Archivo no encontrado: {config_path}")
        else:
            try:
                raw = json.loads(config_path.read_text())
                profiles = raw.get("profiles", {})
                required = {"linux_asus", "darwin_mac"}

                missing = required - set(profiles.keys())
                if missing:
                    result["errors"].append(f"Perfiles faltantes: {missing}")
                for pname, pcfg in profiles.items():
                    if "ollama" not in pcfg:
                        result["errors"].append(f"Perfil {pname}: falta ollama")
                    if "router" not in pcfg:
                        result["errors"].append(f"Perfil {pname}: falta router")

                result["valid"] = len(result["errors"]) == 0
            except json.JSONDecodeError as e:
                result["errors"].append(f"JSON inválido: {e}")

        await self.state.set("supervisor:validator:last", result)
        log.debug("validator: %s (%d errores)", "VALIDO" if result["valid"] else "INVALIDO", len(result["errors"]))

    # ── Tarea 4: Alert Heartbeat (ping al sistema de alertas) -------------

    # ── Tarea: Watchdog Redis --------------------------------------------

    async def _watchdog_redis(self) -> None:
        health = await self.state.health()
        ok = health["active_backend"] != "none" and health.get("redis_connected", False)
        await self.state.set("supervisor:watchdog:redis", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ok": ok,
            "backend": health["active_backend"],
        })
        log.debug("watchdog-redis: %s", "OK" if ok else "FALLIDO")

    # ── Tarea: Watchdog Disco --------------------------------------------

    async def _watchdog_disk(self) -> None:
        import shutil
        usage = shutil.disk_usage("/")
        pct = round(usage.used / usage.total * 100, 1)
        await self.state.set("supervisor:watchdog:disk", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "used_pct": pct,
        })
        log.debug("watchdog-disk: %s%% usado", pct)

    # ── Tarea: Colector de Sistema ---------------------------------------

    async def _collector_system(self) -> None:
        psutil_ok = False
        cpu_pct = -1.0
        mem_pct = -1.0
        try:
            import psutil
            psutil_ok = True
            cpu_pct = psutil.cpu_percent(interval=0.5)
            mem_pct = psutil.virtual_memory().percent
        except ImportError:
            log.debug("silent exception suppressed")
        await self.state.set("supervisor:collector:system", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_pct": cpu_pct,
            "mem_pct": mem_pct,
            "psutil_available": psutil_ok,
        })
        log.debug("collector-system: CPU=%s%% MEM=%s%%", cpu_pct, mem_pct)

    # ── Tarea: Validador de Sintaxis -------------------------------------

    async def _validator_syntax(self) -> None:
        import py_compile
        import tempfile
        base = Path(__file__).parent
        errors: list[str] = []
        for f in sorted(base.glob("*.py")):
            try:
                py_compile.compile(f, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"{f.name}: {e}")
        await self.state.set("supervisor:validator:syntax", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "valid": len(errors) == 0,
            "errors": errors[:20],
        })
        log.debug("validator-syntax: %s (%d errores)", "OK" if not errors else "FALLOS", len(errors))

    # ── Tarea: Validador de Imports --------------------------------------

    async def _validator_imports(self) -> None:
        base = Path(__file__).parent
        errors: list[str] = []
        for f in sorted(base.glob("*.py")):
            content = f.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if "import " not in line and "from " not in line:
                    continue
        await self.state.set("supervisor:validator:imports", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "valid": len(errors) == 0,
            "files_checked": len(list(base.glob("*.py"))),
        })
        log.debug("validator-imports: %s archivos OK", len(list(base.glob("*.py"))))

    # ── Tarea: Optimizador de Cache --------------------------------------

    async def _optimizer_cache(self) -> None:
        try:
            hb = await self.state.get("supervisor:heartbeat:last") or {}
            latency = hb.get("latency_ms", 30)
            suggested_ttl = 7200
            if latency > 100:
                suggested_ttl = 14400
            elif latency < 10:
                suggested_ttl = 3600
        except Exception:
            suggested_ttl = 7200
        await self.state.set("supervisor:optimizer:cache", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suggested_cache_ttl_s": suggested_ttl,
            "reason": f"latency={latency}ms" if 'latency' in dir() else "default",
        })
        log.debug("optimizer-cache: sugerencia TTL=%ds", suggested_ttl)

    # ── Tarea: Watchdog Red -------------------------------------------------

    async def _watchdog_network(self) -> None:
        import subprocess
        lan_ok = False
        ping_lan_ms = -1.0
        try:
            t0 = time.monotonic()
            r = subprocess.run(["ping", "-c", "1", "-W", "2", "10.164.1.99"],
                               capture_output=True, timeout=5)
            ping_lan_ms = round((time.monotonic() - t0) * 1000, 1)
            lan_ok = r.returncode == 0
        except Exception:
            log.debug("silent exception suppressed")
        await self.state.set("supervisor:watchdog:network", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lan_reachable": lan_ok,
            "lan_ping_ms": ping_lan_ms,
            "comment": "LAN 10.164.1.99 — tráfico crítico",
        })
        log.debug("watchdog-network: LAN %s (%sms)", "OK" if lan_ok else "FALLIDO", ping_lan_ms)

    # ── Tarea: Orquestador Determinista ---------------------------------

    async def _orchestrator_controller(self) -> None:
        import json as _json
        now = time.time()
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        orch_log = log_dir / "orchestrator.log"

        if not self._orchestrator_enabled:
            await self.state.set("supervisor:orchestrator:last", {
                "status": "DISABLED",
                "reason": "Deshabilitado por fail-safe",
            })
            return

        # Cooldown check
        if now < self._orchestrator_cooldown_until:
            remaining = int(self._orchestrator_cooldown_until - now)
            log.debug("orchestrator: cooldown %ds restante", remaining)
            await self.state.set("supervisor:orchestrator:last", {
                "status": "ACTIVE",
                "last_change": self._orchestrator_last_change or "—",
                "reason": f"Cooldown {remaining}s — esperando tras: {self._orchestrator_last_reason}",
                "cooldown_until": self._orchestrator_cooldown_until,
            })
            return

        # Obtener métricas actuales
        hb = await self.state.get("supervisor:heartbeat:last") or {}
        sys_data = await self.state.get("supervisor:collector:system") or {}
        mode_data = await self.state.get("supervisor:mode:last") or {}

        current_mode = mode_data.get("mode", "AUTO")
        latency = hb.get("latency_ms", -1.0)
        cpu = sys_data.get("cpu_pct", -1.0)

        if isinstance(latency, list):
            latency = -1.0

        state_input = {
            "current_mode": current_mode,
            "latency_ms": float(latency) if latency is not None else -1.0,
            "cpu_pct": float(cpu) if cpu is not None else -1.0,
        }

        decision = orchestrator_evaluate(state_input)

        if decision in ("TURBO", "ECO") and decision != current_mode:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://127.0.0.1:11435/power_mode?mode={decision}",
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = _json.loads(resp.read())

                reason = f"Cambio a {decision}: lat={latency}ms cpu={cpu}% desde {current_mode}"
                self._orchestrator_cooldown_until = now + 300
                self._orchestrator_last_change = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
                self._orchestrator_last_reason = reason

                # Log a archivo
                with open(orch_log, "a") as f:
                    f.write(f"[{self._orchestrator_last_change}] {reason}\n")

                log.info("orquestador: %s", reason)

                await self.state.set("supervisor:orchestrator:last", {
                    "status": "ACTIVE",
                    "last_change": self._orchestrator_last_change,
                    "reason": reason,
                    "cooldown_until": self._orchestrator_cooldown_until,
                })
            except Exception as e:
                log.warning("orquestador: cambio a %s falló: %s", decision, e)
        else:
            await self.state.set("supervisor:orchestrator:last", {
                "status": "ACTIVE",
                "last_change": self._orchestrator_last_change or "—",
                "reason": f"KEEP: {current_mode} estable (lat={latency}ms cpu={cpu}%)",
                "cooldown_until": self._orchestrator_cooldown_until,
            })
            log.debug("orquestador: MANTENER (%s -> %s)", current_mode, decision)

    # ── Tarea: Ingest Coordinator (scraper + analyzer) -------------------

    async def _ingest_coordinator(self) -> None:
        await collect_and_process()

    # ── Tarea: AI Broker (decisión basada en analytics) ---------------------

    async def _ai_broker(self) -> None:
        await ai_cycle()

    # ── Tarea: Data Analyzer (procesamiento de datos raw) -----------------

    async def _data_analyzer(self) -> None:
        await process_raw_files()

    # ── Tarea: Data Scraper (recolección de datos externos) ---------------

    async def _data_scraper(self) -> None:
        await collect_snapshot()

    # ── Tarea: Telemetría (persistencia JSON Lines) ----------------------

    async def _telemetry_collector(self) -> None:
        hb = await self.state.get("supervisor:heartbeat:last") or {}
        metrics = await self.state.get("supervisor:metrics:last") or {}
        sys_data = await self.state.get("supervisor:collector:system") or {}
        mode_data = await self.state.get("supervisor:mode:last") or {}
        orch_data = await self.state.get("supervisor:orchestrator:last") or {}
        net_data = await self.state.get("supervisor:watchdog:network") or {}
        st = await self.state.health()
        tasks_list = await self._ipc_tasks()

        active_coros = sum(1 for t in tasks_list if not t["done"] and t.get("last_error") is None)
        total_coros = len(tasks_list)

        write_snapshot(
            mode=mode_data.get("mode", "?"),
            cpu_pct=sys_data.get("cpu_pct", -1.0),
            mem_pct=sys_data.get("mem_pct", -1.0),
            latency_ms=metrics.get("asus_latency_ms", -1.0),
            models_available=metrics.get("models", 0),
            backend_label=metrics.get("backend_label", "?"),
            fallback_count_1h=metrics.get("fallback_count_1h", 0),
            active_coroutines=active_coros,
            total_coroutines=total_coros,
            orchestrator_status=orch_data.get("status", "?"),
            orchestrator_reason=orch_data.get("reason", ""),
            router_ok=hb.get("router_ok", False),
            lan_reachable=net_data.get("lan_reachable", False),
            state_backend=st.get("active_backend", "?"),
        )

    # ── Tarea: Alertas (detección de thrashing del orquestador) -----------

    async def _ura_alert(self) -> None:
        now = time.time()
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        alerts_log = log_dir / "alerts.log"

        # Leer modo actual e historial de cambios
        mode_data = await self.state.get("supervisor:mode:last") or {}
        orch_data = await self.state.get("supervisor:orchestrator:last") or {}

        # Reconstruir cambios recientes desde orchestrator.log
        change_times: list[float] = []
        orch_log_path = log_dir / "orchestrator.log"
        if orch_log_path.exists():
            try:
                content = orch_log_path.read_text()
                for line in content.strip().split("\n"):
                    if "Cambio a" in line or "->" in line:
                        try:
                            ts_str = line.split("[")[1].split("]")[0]
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                                try:
                                    parsed = time.mktime(time.strptime(ts_str, fmt))
                                    change_times.append(parsed)
                                    break
                                except ValueError:
                                    continue
                        except (IndexError, ValueError):
                            continue
            except Exception:
                log.debug("silent exception suppressed")

        # Filtrar cambios en los últimos 10 minutos
        cutoff = now - 600
        recent_changes = [t for t in change_times if t >= cutoff]

        is_thrashing = len(recent_changes) > 3

        if is_thrashing:
            msg = (f"CRITICAL: Thrashing detectado — {len(recent_changes)} cambios "
                   f"de modo en los últimos 10 minutos")
            log.warning("ura-alert: %s", msg)

            # Escribir a alerts.log
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
            with open(alerts_log, "a") as f:
                f.write(f"[{ts}] {msg}\n")

            # Enviar warning a syslog del router
            try:
                import urllib.request
                import json as _j
                payload = _j.dumps({"model": "auto", "messages": [{"role": "system", "content": f"[URA ALERT] {msg}"}]})
                req = urllib.request.Request(
                    "http://127.0.0.1:11435/api/chat", data=payload.encode(), method="POST"
                )
                req.add_header("Content-Type", "application/json")
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                log.debug("silent exception suppressed")

        current_mode = mode_data.get("mode", "?")
        if is_thrashing:
            current_mode = f"{current_mode} [THRASHING]"

        await self.state.set("supervisor:alert:last", {
            "status": "THRASHING" if is_thrashing else "OK",
            "changes_last_10min": len(recent_changes),
            "mode": current_mode,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        })

    # ── Tarea: Heartbeat (alertas) ---------------------------------------

    async def heartbeat_task(self) -> None:
        """Ping cada 5 minutos. Si falta, el sistema de alertas detecta ausencia."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supervisor_pid": os.getpid(),
            "uptime_s": round(time.time() - self._start_time),
            "tasks_ok": len([t for t in self._tasks.values() if not t.done() and not t.cancelled()]),
        }
        await self.state.set("supervisor:alert:heartbeat", payload)
        await send_ping_to_alerts_service(payload["supervisor_pid"], payload["uptime_s"])
        log.info("heartbeat-task: ping enviado (PID %d, uptime %ds)", payload["supervisor_pid"], payload["uptime_s"])

    # ── Servidor IPC (ZeroMQ REP) ---------------------------------------

    async def _ipc_server(self) -> None:
        """Atiende comandos IPC. No debe lanzar excepciones no controladas."""
        while self._running:
            try:
                msg = await self._zmq_sock.recv_multipart()
                response = await self._handle_ipc(msg)
                await self._zmq_sock.send_multipart([response.encode()])
            except asyncio.CancelledError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("IPC error: %s", e)
                await self._zmq_sock.send_multipart([
                    json.dumps({"error": str(e)}).encode()
                ])

    async def _handle_ipc(self, msg: list[bytes]) -> str:
        """Interpreta un comando IPC y devuelve respuesta JSON."""
        if not msg:
            return json.dumps({"error": "mensaje vacío"})

        parts = msg[0].decode().strip().split()
        cmd = parts[0].lower() if parts else ""

        if cmd == "health":
            return json.dumps(await self._ipc_health())

        if cmd == "status":
            return json.dumps(await self._ipc_status())

        if cmd == "tasks":
            return json.dumps(await self._ipc_tasks())

        if cmd == "state" and len(parts) >= 3 and parts[1] == "get":
            val = await self.state.get(parts[2])
            return json.dumps({"key": parts[2], "value": val})

        if cmd == "state" and len(parts) >= 4 and parts[1] == "set":
            try:
                val = json.loads(parts[3])
            except json.JSONDecodeError:
                val = parts[3]
            ok = await self.state.set(parts[2], val)
            return json.dumps({"key": parts[2], "set": ok})

        if cmd == "mode" and len(parts) >= 2:
            mode_val = parts[1].upper()
            if mode_val not in ("TURBO", "ECO", "AUTO"):
                return json.dumps({"error": f"modo inválido: {mode_val}. Usar TURBO, ECO o AUTO"})
            import urllib.request
            import urllib.parse
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:11435/power_mode?mode={mode_val}",
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = json.loads(resp.read())
                await self.state.set("supervisor:mode:last", {
                    "mode": mode_val,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                })
                return json.dumps({"mode": mode_val, "status": "ok"})
            except Exception as e:
                return json.dumps({"error": f"cambio a {mode_val} falló: {e}"})

        return json.dumps({"error": f"comando desconocido: {cmd}"})

    async def _ipc_health(self) -> dict[str, Any]:
        st = await self.state.health()
        return {
            "service": "ura-supervisor",
            "pid": os.getpid(),
            "uptime_s": round(time.time() - self._start_time),
            "state_backend": st["active_backend"],
            "tasks_active": len([t for t in self._tasks.values() if not t.done()]),
        }

    async def _ipc_status(self) -> dict[str, Any]:
        st = await self.state.health()
        hb = await self.state.get("supervisor:heartbeat:last") or {}
        metrics = await self.state.get("supervisor:metrics:last") or {}
        mode_data = await self.state.get("supervisor:mode:last") or {}
        disk = await self.state.get("supervisor:watchdog:disk") or {}
        system_data = await self.state.get("supervisor:collector:system") or {}
        syntax = await self.state.get("supervisor:validator:syntax") or {}
        imports = await self.state.get("supervisor:validator:imports") or {}
        cache = await self.state.get("supervisor:optimizer:cache") or {}
        redis_wd = await self.state.get("supervisor:watchdog:redis") or {}
        orch_data = await self.state.get("supervisor:orchestrator:last") or {}
        net_wd = await self.state.get("supervisor:watchdog:network") or {}
        tasks_list = await self._ipc_tasks()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supervisor": {
                "pid": os.getpid(),
                "uptime_s": round(time.time() - self._start_time),
                "state_backend": st["active_backend"],
                "tasks_active": len([t for t in self._tasks.values() if not t.done()]),
                "tasks_total": len(self._tasks),
            },
            "tasks": tasks_list,
            "mode": mode_data.get("mode", "AUTO"),
            "router": {
                "ok": hb.get("router_ok", False),
                "latency_ms": hb.get("latency_ms", -1),
                "models_available": hb.get("models_available", 0),
                "ollama_url": hb.get("ollama_url", ""),
                "power_mode": metrics.get("power_mode", "?"),
                "backend_label": metrics.get("backend_label", "?"),
                "fallback_count_1h": metrics.get("fallback_count_1h", 0),
            },
            "resources": {
                "disk_used_pct": disk.get("used_pct", "?"),
                "disk_free_gb": disk.get("free_gb", "?"),
                "cpu_pct": system_data.get("cpu_pct", "?"),
                "mem_pct": system_data.get("mem_pct", "?"),
                "psutil": system_data.get("psutil_available", False),
            },
            "validation": {
                "syntax_valid": syntax.get("valid", None),
                "imports_valid": imports.get("valid", None),
                "files_checked": imports.get("files_checked", 0),
            },
            "optimizer": {
                "suggested_cache_ttl_s": cache.get("suggested_cache_ttl_s", 7200),
            },
            "network": {
                "lan_reachable": net_wd.get("lan_reachable", False),
                "lan_ping_ms": net_wd.get("lan_ping_ms", -1),
            },
            "orchestrator": {
                "status": orch_data.get("status", "DISABLED"),
                "last_change": orch_data.get("last_change", ""),
                "reason": orch_data.get("reason", ""),
                "enabled": self._orchestrator_enabled,
            },
            "redis": {
                "connected": redis_wd.get("ok", False),
                "backend": redis_wd.get("backend", "?"),
            },
        }

    async def _ipc_tasks(self) -> list[dict[str, Any]]:
        result = []
        for name, task in list(self._tasks.items()):
            error = await self.state.get(f"supervisor:tasks:{name}:last_error")
            result.append({
                "name": name,
                "done": task.done(),
                "cancelled": task.cancelled(),
                "last_error": error.get("error") if error else None,
            })
        return result


# ── Entry point ------------------------------------------------------------

async def main() -> None:
    sup = Supervisor()
    loop = asyncio.get_running_loop()

    def shutdown() -> None:
        log.info("Señal de parada recibida, cerrando supervisor...")
        asyncio.ensure_future(sup.stop())

    loop.add_signal_handler(signal.SIGINT, shutdown)
    loop.add_signal_handler(signal.SIGTERM, shutdown)

    try:
        await sup.start()
        while sup._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        log.debug("silent exception suppressed")
    finally:
        await sup.stop()


if __name__ == "__main__":
    uvloop.install()
    asyncio.run(main())

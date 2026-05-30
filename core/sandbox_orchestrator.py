#!/usr/bin/env python3
"""
Módulo: core/sandbox_orchestrator.py
Propósito: Orquesta ejecuciones en sandbox: gestiona cola de tareas, log de ejecuciones y rotación de entornos.
Dependencias principales: json, datetime, pathlib, Sandbox
Reglas especiales: Máximo de ejecuciones concurrentes. Rotar logs cada 1000 entradas.
"""

import json
import logging
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

URA_HOME = Path.home() / ".ura"
SANDBOX_LOG_PATH = URA_HOME / "sandbox_log.json"
SANDBOX_STATE_PATH = URA_HOME / "sandbox_state.json"
SANDBOXES_DIR = Path(__file__).parent.parent / "sandbox"
URA_HOME.mkdir(parents=True, exist_ok=True)

CYCLE_NORMAL = 21600  # 6 horas
CYCLE_ACCELERATED = 3600  # 1 hora
ACCELERATED_DURATION = 86400  # 24 horas

SANDBOX_DEFINITIONS = {
    "mantenimiento": {
        "id": "mantenimiento",
        "nombre": "Mantenimiento",
        "ubicacion": "mac_local",
        "funcion": "limpieza y optimizacion",
        "herramientas": [
            "limpieza_caches",
            "optimizacion_db",
            "rotacion_logs",
            "compresion_datos",
            "limpieza_temp",
        ],
        "horario": ["06:00", "18:00"],
        "dir": SANDBOXES_DIR / "Mantenimiento",
    },
    "seguridad": {
        "id": "seguridad",
        "nombre": "Seguridad",
        "ubicacion": "gx10_docker",
        "funcion": "validacion y auditoria",
        "herramientas": [
            "bandit",
            "pip_audit",
            "verificacion_permisos",
            "validacion_firmas",
            "analisis_logs",
        ],
        "horario": ["06:00", "00:00"],
        "dir": SANDBOXES_DIR / "Seguridad",
    },
    "aprendizaje": {
        "id": "aprendizaje",
        "nombre": "Aprendizaje",
        "ubicacion": "gx10_docker",
        "funcion": "memoria y embeddings",
        "herramientas": [
            "generacion_embeddings",
            "indexacion_memoria",
            "procesamiento_docs",
            "actualizacion_vectores",
            "entrenamiento_ligero",
        ],
        "horario": ["12:00", "18:00"],
        "dir": SANDBOXES_DIR / "Aprendizaje",
    },
    "documentacion": {
        "id": "documentacion",
        "nombre": "Documentacion",
        "ubicacion": "mac_local",
        "funcion": "manuales e informes",
        "herramientas": [
            "generacion_manuales",
            "informes_estado",
            "documentacion_cambios",
            "actualizacion_readme",
            "generacion_metricas",
        ],
        "horario": ["12:00", "00:00"],
        "dir": SANDBOXES_DIR / "Documentacion",
    },
}

ROTACION = {
    6: ["mantenimiento", "seguridad"],
    12: ["aprendizaje", "documentacion"],
    18: ["mantenimiento", "aprendizaje"],
    0: ["seguridad", "documentacion"],
}


class SandboxOrchestrator:
    """Orquestador de los 4 sandboxes — ciclo cada 6h."""

    def __init__(self):
        self.sandboxes = {sid: dict(meta) for sid, meta in SANDBOX_DEFINITIONS.items()}
        for sb in self.sandboxes.values():
            sb["status"] = "idle"
            sb["last_run"] = None
            sb["last_result"] = None
            sb["locked"] = False
        self.cycle_normal = CYCLE_NORMAL
        self.cycle_accelerated = CYCLE_ACCELERATED
        self.accelerated_until: float | None = None
        self.accelerated_active = False
        self.last_normal_run: float | None = None
        self.last_accelerated_run: float | None = None
        self.pending_critical_changes: list[dict] = []
        self.log: list[dict] = self._load_log()
        self._lock = threading.Lock()
        self._load_state()
        self._ensure_dirs()

    def _ensure_dirs(self):
        for sb in self.sandboxes.values():
            d = sb.get("dir")
            if d:
                d.mkdir(parents=True, exist_ok=True)

    # ─── Persistencia ───
    def _load_log(self) -> list[dict]:
        if SANDBOX_LOG_PATH.exists():
            try:
                with open(SANDBOX_LOG_PATH) as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception as e:
                logger.warning(f"Error cargando sandbox_log: {e}")
        return []

    def _save_log(self):
        with open(SANDBOX_LOG_PATH, "w") as f:
            json.dump(self.log[-500:], f, indent=2)

    def _load_state(self):
        if SANDBOX_STATE_PATH.exists():
            try:
                with open(SANDBOX_STATE_PATH) as f:
                    state = json.load(f)
                self.accelerated_until = state.get("accelerated_until")
                self.accelerated_active = state.get("accelerated_active", False)
                self.last_normal_run = state.get("last_normal_run")
                self.last_accelerated_run = state.get("last_accelerated_run")
            except Exception as e:
                logger.warning(f"Error cargando sandbox_state: {e}")

    def _save_state(self):
        state = {
            "accelerated_until": self.accelerated_until,
            "accelerated_active": self.accelerated_active,
            "last_normal_run": self.last_normal_run,
            "last_accelerated_run": self.last_accelerated_run,
        }
        with open(SANDBOX_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)

    # ─── Coordinación ───
    def lock_sandbox(self, sandbox_id: str) -> bool:
        with self._lock:
            sb = self.sandboxes.get(sandbox_id)
            if not sb or sb["locked"]:
                return False
            sb["locked"] = True
            sb["status"] = "ejecutando"
            return True

    def release_sandbox(self, sandbox_id: str):
        with self._lock:
            sb = self.sandboxes.get(sandbox_id)
            if sb:
                sb["locked"] = False
                if sb["status"] == "ejecutando":
                    sb["status"] = "idle"

    def get_sandbox_status(self, sandbox_id: str) -> dict:
        return dict(self.sandboxes.get(sandbox_id, {}))

    def get_all_status(self) -> dict:
        return {
            "sandboxes": {sid: dict(sb) for sid, sb in self.sandboxes.items()},
            "cycle_normal_seconds": self.cycle_normal,
            "cycle_accelerated_seconds": self.cycle_accelerated,
            "accelerated_active": self.accelerated_active,
            "accelerated_until": self.accelerated_until,
            "pending_critical_changes": len(self.pending_critical_changes),
            "last_normal_run": self.last_normal_run,
            "last_accelerated_run": self.last_accelerated_run,
        }

    # ─── Ejecución por sandbox ───
    def _run_sandbox(self, sandbox_id: str) -> dict:
        sb = self.sandboxes.get(sandbox_id)
        if not sb:
            return {"success": False, "error": f"sandbox {sandbox_id} no existe"}
        if not self.lock_sandbox(sandbox_id):
            return {"success": False, "error": "sandbox bloqueado"}

        result = {"success": True, "sandbox": sandbox_id, "herramientas": {}}
        sandbox_dir = sb.get("dir")

        try:
            if sandbox_id == "mantenimiento":
                result["herramientas"]["limpieza_temp"] = self._tarea_generica(
                    "limpieza temp", sandbox_dir
                )
                result["herramientas"]["rotacion_logs"] = self._tarea_generica(
                    "rotacion logs", sandbox_dir
                )
                result["herramientas"]["optimizacion_db"] = self._tarea_generica(
                    "optimizacion db", sandbox_dir
                )

            elif sandbox_id == "seguridad":
                result["herramientas"]["bandit"] = self._check_tool("bandit", "--version")
                result["herramientas"]["pip_audit"] = self._check_tool("pip-audit", "--version")
                result["herramientas"]["verificacion_permisos"] = self._tarea_generica(
                    "verificacion permisos", sandbox_dir
                )

            elif sandbox_id == "aprendizaje":
                result["herramientas"]["embeddings"] = self._tarea_generica(
                    "generacion embeddings", sandbox_dir
                )
                result["herramientas"]["indexacion"] = self._tarea_generica(
                    "indexacion memoria", sandbox_dir
                )

            elif sandbox_id == "documentacion":
                result["herramientas"]["metricas"] = self._tarea_generica("metricas", sandbox_dir)
                result["herramientas"]["informes"] = self._tarea_generica("informes", sandbox_dir)

            sb["last_run"] = datetime.now().isoformat()
            sb["last_result"] = result["success"]
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            sb["status"] = "error"
        finally:
            self.release_sandbox(sandbox_id)

        return result

    def _tarea_generica(self, nombre: str, sandbox_dir: Path) -> bool:
        """Tarea placeholder hasta implementar la logica real."""
        if sandbox_dir and sandbox_dir.exists():
            log_file = sandbox_dir / f"{nombre.replace(' ', '_')}.log"
            log_file.write_text(f"{datetime.now().isoformat()} — {nombre} ejecutado\n")
        return True

    def _check_tool(self, tool: str, arg: str = "--version") -> bool:
        """Verifica si una herramienta esta disponible."""
        try:
            r = subprocess.run([tool, arg], capture_output=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    # ─── Rotación ───
    def _get_current_rotation(self) -> list[str]:
        """Devuelve los sandboxes que tocan en la hora actual."""
        hora = datetime.now().hour
        for h in sorted(ROTACION.keys(), reverse=True):
            if hora >= h:
                return ROTACION[h]
        return ROTACION[0]

    def _run_full_pipeline(self, accelerated: bool = False) -> dict:
        """Ejecuta la rotacion actual de sandboxes (2 a la vez)."""
        cycle_type = "accelerated" if accelerated else "normal"
        run_log = {
            "cycle_type": cycle_type,
            "started": datetime.now().isoformat(),
            "results": {},
            "failures": [],
        }

        sandboxes_a_ejecutar = self._get_current_rotation()
        threads = []

        def _ejecutar(sid):
            res = self._run_sandbox(sid)
            with self._lock:
                run_log["results"][sid] = res
                if not res.get("success"):
                    run_log["failures"].append(sid)

        for sid in sandboxes_a_ejecutar:
            t = threading.Thread(target=_ejecutar, args=(sid,), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=300)

        run_log["finished"] = datetime.now().isoformat()
        run_log["sandboxes_ejecutados"] = sandboxes_a_ejecutar
        self.log.append(run_log)
        self._save_log()
        return run_log

    def run_normal_cycle(self) -> dict:
        """Ciclo normal cada 6h."""
        result = self._run_full_pipeline(accelerated=False)
        self.last_normal_run = time.time()
        self._save_state()
        return result

    def run_accelerated_cycle(self) -> dict:
        """Ciclo acelerado cada 1h."""
        result = self._run_full_pipeline(accelerated=True)
        self.last_accelerated_run = time.time()
        self._save_state()
        return result

    def trigger_accelerated_cycle(self, reason: str = "") -> dict:
        """Activa el ciclo acelerado durante 24h."""
        self.accelerated_active = True
        self.accelerated_until = time.time() + ACCELERATED_DURATION
        self._save_state()
        notification = "Ciclo acelerado activado 24h" + (f": {reason}" if reason else "")
        logger.warning(notification)
        self.log.append(
            {
                "event": "accelerated_triggered",
                "reason": reason,
                "until": datetime.fromtimestamp(self.accelerated_until).isoformat(),
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save_log()
        return {"ok": True, "message": notification, "until": self.accelerated_until}

    def check_and_update_cycle(self):
        """Desactiva acelerado si expiro."""
        now = time.time()
        if self.accelerated_active and self.accelerated_until and now > self.accelerated_until:
            if self.pending_critical_changes:
                last_change = self.pending_critical_changes[-1]
                self.trigger_accelerated_cycle(reason=last_change.get("reason", ""))
                self.pending_critical_changes.clear()
            else:
                self.accelerated_active = False
                self.accelerated_until = None
                self._save_state()
                logger.info("Ciclo acelerado finalizado")

    CRITICAL_CHANGE_TYPES = {
        "package_install",
        "systemic_repair",
        "core_modification",
        "ollama_model_update",
        "network_config_change",
        "external_merge",
    }

    def register_critical_change(
        self, change_type: str, reason: str = "", metadata: dict = None
    ) -> bool:
        if change_type not in self.CRITICAL_CHANGE_TYPES:
            logger.warning(f"Tipo de cambio desconocido: {change_type}")
            return False
        change = {
            "type": change_type,
            "reason": reason,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.pending_critical_changes.append(change)
        if not self.accelerated_active:
            self.trigger_accelerated_cycle(reason=f"{change_type}: {reason}")
        return True

    def get_failing_sandboxes(self) -> list[dict]:
        return [
            {"id": sid, **sb}
            for sid, sb in self.sandboxes.items()
            if sb.get("status") == "error" or sb.get("last_result") is False
        ]


_sandbox_orchestrator: SandboxOrchestrator | None = None


def get_sandbox_orchestrator() -> SandboxOrchestrator:
    global _sandbox_orchestrator
    if _sandbox_orchestrator is None:
        _sandbox_orchestrator = SandboxOrchestrator()
    return _sandbox_orchestrator

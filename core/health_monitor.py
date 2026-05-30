#!/usr/bin/env python3
"""
Módulo: core/health_monitor.py
Propósito: Monitor de salud del sistema URA: verifica estado de Ollama y recursos cada 5 minutos.
Dependencias principales: subprocess, threading, datetime, logging, requests
Reglas especiales: Intervalo mínimo de 300 segundos entre alertas. Detectar caídas de Ollama.
"""

import time
import logging
import threading
from datetime import datetime
from pathlib import Path

import psutil

from core.logging_config import get_logger

logger = get_logger("health_monitor", log_dir="./logs")

ALERT_LOG_PATH = Path.home() / ".ura" / "health_alerts.log"
ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class HealthMonitor:
    """Monitor de salud para URA."""

    def __init__(self, check_interval: int = 300):  # 5 minutos por defecto
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._ollama_down_since = None
        self._last_alert = {}
        from core.sandbox_orchestrator import get_sandbox_orchestrator

        self.sandbox_orchestrator = get_sandbox_orchestrator()

    def check_ollama(self) -> bool:
        """Verifica si Ollama está funcionando."""
        try:
            import requests

            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            return r.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama check failed: {e}")
            return False

    def check_disk_space(self) -> float:
        """Verifica el espacio en disco (porcentaje usado)."""
        try:
            disk = psutil.disk_usage("/")
            return disk.percent
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return 0.0

    def write_alert(self, service: str, message: str):
        """Escribe una alerta en el log de alertas."""
        timestamp = datetime.now().isoformat()
        alert_line = f"{timestamp} - {service}: {message}\n"

        with open(ALERT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(alert_line)

        logger.warning(f"ALERT: {service} - {message}")

    def check(self):
        """Verifica el estado de Ollama y disco."""
        # Verificar Ollama
        ollama_ok = self.check_ollama()

        if not ollama_ok:
            if self._ollama_down_since is None:
                self._ollama_down_since = datetime.now()
                logger.warning("Ollama está caído")
            else:
                downtime = (datetime.now() - self._ollama_down_since).total_seconds()
                if downtime > 300:  # 5 minutos
                    alert_key = "ollama_down"
                    if (
                        alert_key not in self._last_alert
                        or time.time() - self._last_alert[alert_key] > 300
                    ):
                        self.write_alert("Ollama", f"Caído por más de {int(downtime / 60)} minutos")
                        self._last_alert[alert_key] = time.time()
        else:
            if self._ollama_down_since is not None:
                downtime = (datetime.now() - self._ollama_down_since).total_seconds()
                logger.info(f"Ollama recuperado después de {int(downtime / 60)} minutos")
                self._ollama_down_since = None

        # Verificar disco
        disk_percent = self.check_disk_space()
        if disk_percent > 80:
            alert_key = "disk_low"
            if alert_key not in self._last_alert or time.time() - self._last_alert[alert_key] > 300:
                self.write_alert("Disco", f"Espacio bajo: {disk_percent:.1f}% usado")
                self._last_alert[alert_key] = time.time()

        logger.info(
            f"Health check: Ollama={'OK' if ollama_ok else 'DOWN'}, Disco={disk_percent:.1f}%"
        )

        # Ejecutar auto-reparación de errores típicos
        self._run_error_repair_cycle()

        # Ejecutar análisis forense
        self._run_forensic_cycle()

        # Cruce de correlaciones de errores
        self._run_cross_reference_cycle()

        # Post-mortem de instalaciones
        self._run_install_post_mortem()

        # Cristal: revisar timeouts
        self._check_crystal_timeouts()

        # Vocabularios: actualizar cada 24h
        self._update_vocabularies()

        # Sandboxes: actualizar ciclo y ejecutar si toca
        self._run_sandbox_cycle()
        self._check_critical_changes()

    def _run_sandbox_cycle(self):
        """Ejecuta el ciclo de sandboxes (normal o acelerado) si toca."""
        try:
            orch = self.sandbox_orchestrator
            orch.check_and_update_cycle()
            now = time.time()
            if orch.accelerated_active:
                if (
                    not orch.last_accelerated_run
                    or (now - orch.last_accelerated_run) >= orch.cycle_accelerated
                ):
                    logger.info("Ejecutando ciclo acelerado de sandboxes")
                    orch.run_accelerated_cycle()
            else:
                if not orch.last_normal_run or (now - orch.last_normal_run) >= orch.cycle_normal:
                    logger.info("Ejecutando ciclo normal de sandboxes")
                    orch.run_normal_cycle()
        except Exception as e:
            logger.debug(f"Error en sandbox cycle: {e}")

    def _check_critical_changes(self):
        """Si hay cambios importantes pendientes y no hay ciclo acelerado, lo activa."""
        try:
            orch = self.sandbox_orchestrator
            if orch.pending_critical_changes and not orch.accelerated_active:
                last = orch.pending_critical_changes[-1]
                orch.trigger_accelerated_cycle(reason=last.get("reason", ""))
        except Exception as e:
            logger.debug(f"Error en _check_critical_changes: {e}")

    def _check_crystal_timeouts(self):
        """Revisa si algún departamento ha excedido su tiempo más de 3 veces en 1h."""
        try:
            from core.vocabulary_department import get_crystal_limiter

            limiter = get_crystal_limiter()
            for dept in limiter.time_limits:
                count = limiter.recent_timeouts(dept, hours=1)
                if count >= 3:
                    self.write_alert(
                        "CrystalLimiter",
                        f"{dept}: {count} timeouts en última hora (límite: {limiter.get_limit(dept)}s)",
                    )
        except Exception as e:
            logger.debug(f"Error en _check_crystal_timeouts: {e}")

    def _update_vocabularies(self):
        """Actualiza vocabularios desde la biblioteca local cada 24h."""
        now = time.time()
        last = getattr(self, "_last_vocab_update", 0)
        if now - last < 24 * 3600:
            return
        try:
            from core.vocabulary_department import get_vocabulary_manager

            vm = get_vocabulary_manager()
            stats = vm.update_from_knowledge_base()
            self._last_vocab_update = now
            if stats:
                total = sum(stats.values())
                logger.info(
                    f"Vocabularios actualizados: {total} fuentes nuevas en {len(stats)} departamentos"
                )
        except Exception as e:
            logger.debug(f"Error actualizando vocabularios: {e}")

    def _run_cross_reference_cycle(self):
        """Cruzar correlaciones de errores."""
        try:
            from core.error_cross_reference import get_error_cross_reference

            xref = get_error_cross_reference()
            correlations = xref.find_correlations()
            if correlations.get("cascade_errors"):
                logger.warning(f"Cascadas detectadas: {len(correlations['cascade_errors'])}")
        except Exception as e:
            logger.debug(f"Error en cross_reference: {e}")

    def _run_install_post_mortem(self):
        """Revisar instalaciones recientes en busca de conflictos."""
        try:
            from core.conflict_detector import get_conflict_detector

            cd = get_conflict_detector()
            issues = cd.post_mortem_check()
            if issues:
                logger.warning(f"Post-mortem: {len(issues)} instalaciones con conflictos")
        except Exception as e:
            logger.debug(f"Error en post-mortem: {e}")

    def _run_error_repair_cycle(self):
        """Ejecutar ciclo de auto-reparación de errores típicos."""
        try:
            from core.error_auto_repair import ErrorAutoRepair

            repair = ErrorAutoRepair()
            results = repair.auto_repair_typical_errors()
            if results:
                repaired = [r for r in results if r.get("repaired")]
                failed = [r for r in results if not r.get("repaired")]
                if repaired:
                    logger.info(f"Auto-reparados {len(repaired)} errores típicos")
                if failed:
                    logger.warning(f"Fallaron {len(failed)} reparaciones")
        except Exception as e:
            logger.debug(f"Error en ciclo de reparación: {e}")

    def _run_forensic_cycle(self):
        """Ejecutar ciclo de análisis forense."""
        try:
            from core.forensic_scribe import get_forensic_scribe

            scribe = get_forensic_scribe()
            scribe.log_event(
                "health_check",
                "health_monitor",
                "cycle_completed",
                {"ollama": self.check_ollama(), "disk": self.check_disk_space()},
                ["health_monitor", "error_auto_repair"],
            )
            predictions = scribe.predict_issues()
            if predictions:
                for p in predictions[:3]:
                    logger.warning(
                        f"PREDICCIÓN: {p.get('predicted_issue', '')} en {p.get('module', '?')} (similitud: {p.get('similarity', 0)})"
                    )
                    self.write_alert(
                        "ForensicScribe",
                        f"Predicción: {p.get('predicted_issue', '')} en {p.get('module', '?')}",
                    )
        except Exception as e:
            logger.debug(f"Error en ciclo forense: {e}")

    def _monitor_loop(self):
        """Bucle de monitoreo en segundo plano."""
        while self._running:
            try:
                self.check()
            except Exception as e:
                logger.error(f"Error en health check: {e}")

            time.sleep(self.check_interval)

    def start(self):
        """Inicia el monitor en segundo plano."""
        if self._running:
            logger.warning("Health monitor ya está corriendo")
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"Health monitor iniciado (intervalo: {self.check_interval}s)")

    def stop(self):
        """Detiene el monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Health monitor detenido")


# Singleton
_health_monitor: HealthMonitor | None = None


def get_health_monitor(check_interval: int = 300) -> HealthMonitor:
    """Obtener el singleton del health monitor."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor(check_interval=check_interval)
    return _health_monitor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = get_health_monitor(check_interval=10)  # 10 segundos para prueba

    print("Health monitor iniciado (presiona Ctrl+C para detener)")
    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("Health monitor detenido")

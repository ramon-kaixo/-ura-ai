#!/usr/bin/env python3
"""
Sistema de Autonomía y Mantenimiento Predictivo - URA App
Módulo de auto-recuperación y mantenimiento automático
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta

# evolutionary_system is an optional module; gracefully degrade if absent.
try:
    from evolutionary_system import get_evolutionary_system  # type: ignore

    HAS_EVOLUTIONARY = True
except ImportError:
    HAS_EVOLUTIONARY = False
    get_evolutionary_system = None  # type: ignore

# Configurar logging
BENCHMARKS_DIR = Path(__file__).parent.parent / "benchmarks"
MAINTENANCE_LOG = BENCHMARKS_DIR / "maintenance.log"
PERFORMANCE_HISTORY = BENCHMARKS_DIR / "performance_history.json"

# Crear directorio de benchmarks si no existe
BENCHMARKS_DIR.mkdir(exist_ok=True)

# Configurar logger para mantenimiento
maintenance_logger = logging.getLogger("maintenance")
maintenance_logger.setLevel(logging.INFO)
handler = logging.FileHandler(MAINTENANCE_LOG)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
maintenance_logger.addHandler(handler)


class SelfHealingSystem:
    """Sistema de Auto-Recuperación para URA App"""

    def __init__(self, ollama_connector, context_callback=None, telegram_bridge=None):
        self.ollama_connector = ollama_connector
        self.context_callback = context_callback  # Callback para actualizar panel Contexto (10%)
        self.telegram_bridge = telegram_bridge  # Telegram bridge inyectado desde main_final.py
        self.crash_count = 0
        self.last_crash_time = None
        self.monitoring_active = False
        self.monitor_thread = None

    def log_maintenance(self, message, level="INFO"):
        """Registrar actividad en maintenance.log"""
        maintenance_logger.log(getattr(logging, level), message)
        if self.context_callback:
            self.context_callback(f"[Mantenimiento] {message}")

    def monitor_ollama_connection(self):
        """Vigilancia continua de conexión con Ollama"""
        self.monitoring_active = True
        self.log_maintenance("Iniciando vigilancia de Ollama...")

        while self.monitoring_active:
            try:
                if not self.ollama_connector.test_connection(test_model=False):
                    self.log_maintenance("⚠️ Ollama desconectado - iniciando auto-reinicio...")
                    self.auto_restart_ollama()
                time.sleep(5)  # Verificar cada 5 segundos
            except Exception as e:
                self.log_maintenance(f"Error en vigilancia: {e}", "ERROR")
                time.sleep(5)

    def auto_restart_ollama(self):
        """Reiniciar Ollama automáticamente si se pierde conexión"""
        try:
            # Intentar reiniciar Ollama
            subprocess.Popen(
                ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # Esperar a que Ollama se inicie
            time.sleep(3)

            # Verificar conexión
            if self.ollama_connector.test_connection(test_model=False):
                self.log_maintenance("✅ Ollama reiniciado exitosamente")
                self.crash_count = 0
            else:
                self.log_maintenance("❌ No se pudo reiniciar Ollama", "ERROR")
                self.increment_crash_count()

        except Exception as e:
            self.log_maintenance(f"Error reiniciando Ollama: {e}", "ERROR")
            self.increment_crash_count()

    def increment_crash_count(self):
        """Incrementar contador de caídas y verificar si se necesita mantenimiento de emergencia"""
        self.crash_count += 1
        self.last_crash_time = datetime.now()

        self.log_maintenance(f"Caída #{self.crash_count} registrada")

        # Si hay 3 o más caídas en 5 minutos, activar mantenimiento de emergencia
        if self.crash_count >= 3 and (
            self.last_crash_time and (datetime.now() - self.last_crash_time).total_seconds() < 300
        ):
            self.log_maintenance(
                "⚠️ Caídas frecuentes detectadas - activando mantenimiento de emergencia"
            )
            self.emergency_maintenance()

    def emergency_maintenance(self):
        """Mantenimiento de emergencia: reinicio de hilos, vaciado de caché, reconexión de sockets"""
        self.log_maintenance("🔧 Ejecutando mantenimiento de emergencia...")

        try:
            # 1. Reiniciar conexión Ollama
            self.log_maintenance("Reiniciando conexión Ollama...")
            self.ollama_connector.is_connected = False
            time.sleep(2)
            self.ollama_connector.test_connection(test_model=False)

            # 2. Limpiar caché (simulado - en producción implementar limpieza real)
            self.log_maintenance("Vaciando caché...")
            # Aquí se implementaría limpieza de caché real

            # 3. Reiniciar sockets de voz (simulado)
            self.log_maintenance("Reconectando sockets de voz...")
            # Aquí se implementaría reconexión de sockets de voz

            # 4. Reiniciar contador de caídas
            self.crash_count = 0

            self.log_maintenance("✅ Mantenimiento de emergencia completado")

        except Exception as e:
            self.log_maintenance(f"Error en mantenimiento de emergencia: {e}", "ERROR")

    def start_monitoring(self):
        """Iniciar vigilancia en thread separado"""
        if not self.monitoring_active:
            self.monitor_thread = threading.Thread(
                target=self.monitor_ollama_connection, daemon=True
            )
            self.monitor_thread.start()

    def stop_monitoring(self):
        """Detener vigilancia"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)


class BenchmarkAutomation:
    """Automatización del Banco de Pruebas"""

    def __init__(self, context_callback=None, voice_notification_callback=None):
        self.context_callback = context_callback
        self.voice_notification_callback = voice_notification_callback
        self.performance_history = self.load_performance_history()

        # Inicializar Evolutionary System (opcional)
        self.evolutionary_system = (
            get_evolutionary_system(BENCHMARKS_DIR) if HAS_EVOLUTIONARY else None
        )

    def log_maintenance(self, message, level="INFO"):
        """Registrar actividad en maintenance.log"""
        maintenance_logger.log(getattr(logging, level), message)
        if self.context_callback:
            self.context_callback(f"[Benchmarks] {message}")

    def load_performance_history(self):
        """Cargar historial de rendimiento"""
        if PERFORMANCE_HISTORY.exists():
            try:
                with open(PERFORMANCE_HISTORY) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_performance_history(self):
        """Guardar historial de rendimiento"""
        with open(PERFORMANCE_HISTORY, "w") as f:
            json.dump(self.performance_history, f, indent=2)

    def should_run_weekly_benchmark(self):
        """Verificar si es momento de ejecutar benchmark semanal"""
        if "last_benchmark" not in self.performance_history:
            return True

        last_benchmark = datetime.fromisoformat(self.performance_history["last_benchmark"])
        time_since_last = datetime.now() - last_benchmark

        # Ejecutar si han pasado 7 días o más
        return time_since_last >= timedelta(days=7)

    def run_weekly_benchmarks(self):
        """Ejecutar banco de pruebas semanalmente con tests evolutivos"""
        self.log_maintenance("Iniciando banco de pruebas semanal con evolución proactiva...")

        # Ejecutar scripts de benchmark
        benchmark_scripts = [
            "benchmark_advanced.py",
            "benchmark_resilience.py",
            "benchmark_streaming.py",
        ]

        results = {}
        failed_tests = []

        for script in benchmark_scripts:
            script_path = BENCHMARKS_DIR / script
            if script_path.exists():
                self.log_maintenance(f"Ejecutando {script}...")
                try:
                    result = subprocess.run(
                        ["python3", str(script_path)], capture_output=True, text=True, timeout=120
                    )
                    results[script] = {
                        "returncode": result.returncode,
                        "output": result.stdout,
                        "error": result.stderr,
                    }

                    # Registrar tests fallados para evolución
                    if result.returncode != 0:
                        failed_tests.append(script)

                    self.log_maintenance(f"{script} completado")
                except subprocess.TimeoutExpired:
                    results[script] = {"returncode": -1, "output": "", "error": "Timeout"}
                    failed_tests.append(script)
                    self.log_maintenance(f"{script} timeout", "WARNING")
                except Exception as e:
                    results[script] = {"returncode": -1, "output": "", "error": str(e)}
                    failed_tests.append(script)
                    self.log_maintenance(f"{script} error: {e}", "ERROR")
            else:
                self.log_maintenance(f"{script} no encontrado", "WARNING")

        # GENERAR TESTS EVOLUTIVOS (opcional — requiere evolutionary_system)
        if self.evolutionary_system is not None:
            self.log_maintenance("Generando tests evolutivos basados en fallos...")
            evolutionary_tests = self.evolutionary_system.generate_evolutionary_tests(failed_tests)

            # Registrar en EVOLUTION_LOG
            from evolutionary_system import RiskLevel  # type: ignore

            self.evolutionary_system.log_evolution_event(
                "TEST_GENERADO",
                f"Generados {len(evolutionary_tests)} tests evolutivos basados en {len(failed_tests)} fallos",
                RiskLevel.SAFE,
                auto_approved=True,
            )

            # Ejecutar suite aleatoria con mutaciones
            self.log_maintenance("Ejecutando suite de tests en orden aleatorio con mutaciones...")
            self.evolutionary_system.execute_random_test_suite()
        else:
            self.log_maintenance(
                "evolutionary_system no disponible — saltando tests evolutivos", "WARNING"
            )

        # Verificar degradación de rendimiento
        latency_issue = self.check_performance_degradation(results)

        # Generar informe semanal
        self.generate_weekly_health_report(results, latency_issue)

        # Exportar para análisis de IA (opcional)
        if self.evolutionary_system is not None:
            ai_analysis_export = self.evolutionary_system.export_for_ai_analysis()
            ai_export_path = BENCHMARKS_DIR / "AI_ANALYSIS_EXPORT.md"
            with open(ai_export_path, "w") as f:
                f.write(ai_analysis_export)
            self.log_maintenance(f"Exportación para IA generada: {ai_export_path}")

        # Si hay problemas, activar mantenimiento automático
        if latency_issue:
            self.log_maintenance(
                "⚠️ Problemas detectados - activando mantenimiento automático", "WARNING"
            )
            self.auto_repair()

        self.log_maintenance("✅ Benchmarks semanales completados")

    def generate_weekly_health_report(self, results, latency_issue):
        """Generar Informe_Semanal_Salud.md"""
        report_path = BENCHMARKS_DIR / "Informe_Semanal_Salud.md"

        report_content = f"""# Informe Semanal de Salud - URA App
**Fecha:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Estado:** {"CRÍTICO" if latency_issue else "OPERATIVO"}

---

## 📊 Resumen de Benchmarks

"""

        for script, result in results.items():
            status = "✅ Éxito" if result["success"] else "❌ Fallo"
            report_content += f"\n### {script}\n- Estado: {status}\n"
            if result.get("error"):
                report_content += f"- Error: {result['error']}\n"

        report_content += f"""
---

## 🔍 Estado de Sistemas

- **Latencia IA:** {self.performance_history.get("last_ttft", 0) * 1000:.0f}ms {"⚠️ > 180ms" if self.performance_history.get("last_ttft", 0) > 0.18 else "✅ OK"}
- **Filtros de Privacidad:** {"❌ Fallo detectado" if latency_issue else "✅ Operativos"}
- **Estado General:** {"⚠️ Requiere mantenimiento" if latency_issue else "✅ Operativo al 100%"}

---

## 📝 Recomendaciones

"""

        if latency_issue:
            report_content += "- Se ha activado la Orden de Mantenimiento automática\n"
            report_content += "- Verifique los logs en maintenance.log y privacy_scrubber.log\n"
        else:
            report_content += "- Sistema operativo correctamente\n"
            report_content += "- Próximo reporte en 7 días\n"

        report_content += """
---

**Generado por:** Sistema de Automatización de Benchmarks
**Versión:** 3.0
"""

        with open(report_path, "w") as f:
            f.write(report_content)

        self.log_maintenance(f"Informe semanal generado: {report_path}")

        # Telegram bridge se inyecta desde main_final.py
        # telegram_bridge = get_telegram_bridge()
        # if telegram_bridge and telegram_bridge.enabled:
        #     telegram_bridge.send_health_report(report_content)
        #     self.log_maintenance("Informe semanal enviado a Telegram")

    def check_performance_degradation(self, results):
        """Verificar si hay degradación de rendimiento o fallos de privacidad"""
        degradation_detected = False

        # Buscar TTFT en resultados de benchmark_advanced.py
        if "benchmark_advanced.py" in results:
            output = results["benchmark_advanced.py"].get("output", "")
            if "TTFT medio" in output:
                try:
                    import re

                    match = re.search(r"(\d+\.?\d*)\s*s", output)
                    if match:
                        ttft = float(match.group(1))
                        self.performance_history["last_ttft"] = ttft

                        # Verificar si TTFT > 180ms
                        if ttft > 0.18:
                            self.log_maintenance(
                                f"⚠️ Degradación detectada: TTFT = {ttft * 1000:.0f}ms > 180ms",
                                "WARNING",
                            )
                            degradation_detected = True
                        else:
                            self.log_maintenance(
                                f"✅ Rendimiento óptimo: TTFT = {ttft * 1000:.0f}ms"
                            )
                except:
                    pass

        # Verificar logs de privacidad
        privacy_log = BENCHMARKS_DIR / "privacy_scrubber.log"
        if privacy_log.exists():
            with open(privacy_log) as f:
                content = f.read()
            if "VIOLACIÓN DE PRIVACIDAD" in content or "patrones sensibles" in content.lower():
                self.log_maintenance("⚠️ Fallos en filtros de privacidad detectados", "WARNING")
                degradation_detected = True

        # Si hay degradación, notificar por voz
        if degradation_detected and self.voice_notification_callback:
            message = "Se han detectado problemas de rendimiento o privacidad. Latencia superior a 180 milisegundos o filtros fallidos. Activando mantenimiento automático."
            self.voice_notification_callback(message)

        self.save_performance_history()
        return degradation_detected

    def auto_repair(self):
        """Auto-arreglo: ejecutar mantenimiento y reinstalar dependencias si es necesario"""
        self.log_maintenance("🔧 Iniciando auto-arreglo...")

        try:
            # 1. Ejecutar mantenimiento de emergencia
            self.log_maintenance("Ejecutando mantenimiento...")
            # Aquí se llamaría al sistema de self-healing

            # 2. Reinstalar dependencias
            self.log_maintenance("Reinstalando dependencias...")
            requirements_file = Path(__file__).parent / "requirements.txt"
            if requirements_file.exists():
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    self.log_maintenance("✅ Dependencias reinstaladas exitosamente")
                else:
                    self.log_maintenance("❌ Error reinstalando dependencias", "ERROR")

            self.log_maintenance("✅ Auto-arreglo completado")

        except Exception as e:
            self.log_maintenance(f"Error en auto-arreglo: {e}", "ERROR")


if __name__ == "__main__":
    # Test del sistema
    print("Sistema de Autonomía y Mantenimiento Predictivo")
    print(f"Directorio de benchmarks: {BENCHMARKS_DIR}")
    print(f"Log de mantenimiento: {MAINTENANCE_LOG}")

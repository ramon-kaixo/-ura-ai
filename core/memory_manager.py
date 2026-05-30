#!/usr/bin/env python3
"""
Gestor de Memoria RAM URA
Optimiza automáticamente el uso de RAM congelando procesos inactivos
"""

import json
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

import psutil

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "memory_manager_config.json"
LOG_FILE = PROJECT_ROOT / "logs" / "memory_manager.log"
STATE_FILE = PROJECT_ROOT / "logs" / "memory_manager_state.json"
HISTORY_FILE = PROJECT_ROOT / "logs" / "memory_history.json"

# Crear directorios necesarios
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ProcessConfig:
    """Configuración de un proceso"""

    name: str
    pattern: str  # Patrón para identificar el proceso
    max_inactive_minutes: int  # Tiempo de inactividad antes de congelar
    min_memory_mb: int  # Memoria mínima a mantener
    priority: int  # Prioridad (1 = alta, 10 = baja)
    auto_restart: bool = True  # Si se reinicia automáticamente
    alert_on_freeze: bool = False  # Alertar cuando se congela
    alert_on_thaw: bool = False  # Alertar cuando se reactiva


@dataclass
class ProcessState:
    """Estado de un proceso"""

    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    last_active: str
    status: str  # running, frozen, stopped
    frozen_at: str | None = None


class MemoryManager:
    """Gestor de memoria RAM URA"""

    def __init__(self):
        self.configs = self.cargar_config()
        self.state: dict[str, ProcessState] = {}
        self.historial_memoria: list[dict] = []
        self.cargar_estado()
        self.cargar_historial()

    def log(self, message: str):
        """Escribe mensaje en log"""
        timestamp = datetime.now().isoformat()
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
        print(message)

    def cargar_config(self) -> list[ProcessConfig]:
        """Carga configuración de procesos"""
        default_configs = [
            ProcessConfig(
                name="Docker",
                pattern="docker",
                max_inactive_minutes=10,
                min_memory_mb=100,
                priority=5,
                auto_restart=True,
            ),
            ProcessConfig(
                name="Redis",
                pattern="redis-server",
                max_inactive_minutes=15,
                min_memory_mb=50,
                priority=2,
                auto_restart=True,
            ),
            ProcessConfig(
                name="Ollama",
                pattern="ollama",
                max_inactive_minutes=20,
                min_memory_mb=500,
                priority=3,
                auto_restart=True,
            ),
            ProcessConfig(
                name="PostgreSQL",
                pattern="postgres",
                max_inactive_minutes=30,
                min_memory_mb=100,
                priority=4,
                auto_restart=True,
            ),
            ProcessConfig(
                name="MongoDB",
                pattern="mongod",
                max_inactive_minutes=30,
                min_memory_mb=200,
                priority=5,
                auto_restart=True,
            ),
            ProcessConfig(
                name="MySQL",
                pattern="mysqld",
                max_inactive_minutes=30,
                min_memory_mb=100,
                priority=4,
                auto_restart=True,
            ),
        ]

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    config_data = json.load(f)
                    return [ProcessConfig(**cfg) for cfg in config_data]
            except Exception as e:
                logger.warning(f"Error silencioso en memory_manager.cargar_config: {e}")
                # fallback: continuar

        # Guardar configuración por defecto
        with open(CONFIG_FILE, "w") as f:
            json.dump([asdict(cfg) for cfg in default_configs], f, indent=2)

        return default_configs

    def cargar_estado(self):
        """Carga estado de procesos"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    state_data = json.load(f)
                    for pid_str, state_dict in state_data.items():
                        self.state[pid_str] = ProcessState(**state_dict)
            except Exception as e:
                logger.warning(f"Error silencioso en memory_manager.cargar_estado: {e}")
                # fallback: continuar

    def guardar_estado(self):
        """Guarda estado de procesos"""
        state_data = {}
        for pid_str, state in self.state.items():
            state_data[pid_str] = asdict(state)

        with open(STATE_FILE, "w") as f:
            json.dump(state_data, f, indent=2, default=str)

    def cargar_historial(self):
        """Carga historial de memoria"""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    self.historial_memoria = json.load(f)
            except:
                self.historial_memoria = []

    def guardar_historial(self):
        """Guarda historial de memoria"""
        # Mantener solo últimos 1000 registros
        if len(self.historial_memoria) > 1000:
            self.historial_memoria = self.historial_memoria[-1000:]

        with open(HISTORY_FILE, "w") as f:
            json.dump(self.historial_memoria, f, indent=2, default=str)

    def registrar_historial(self, mem_stats: dict):
        """Registra estadísticas de memoria en historial"""
        registro = {
            "timestamp": datetime.now().isoformat(),
            "total_gb": mem_stats["total_gb"],
            "used_gb": mem_stats["used_gb"],
            "available_gb": mem_stats["available_gb"],
            "percent": mem_stats["percent"],
        }
        self.historial_memoria.append(registro)
        self.guardar_historial()

    def obtener_procesos(self) -> list[psutil.Process]:
        """Obtiene todos los procesos del sistema"""
        return list(psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]))

    def obtener_memoria_total(self) -> dict:
        """Obtiene estadísticas de memoria del sistema"""
        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "used_gb": mem.used / (1024**3),
            "percent": mem.percent,
        }

    def obtener_proceso_por_patron(self, pattern: str) -> psutil.Process | None:
        """Obtiene un proceso por patrón de nombre"""
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if pattern.lower() in proc.info["name"].lower():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def obtener_memoria_proceso(self, proc: psutil.Process) -> float:
        """Obtiene memoria de un proceso en MB"""
        try:
            return proc.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def obtener_cpu_proceso(self, proc: psutil.Process) -> float:
        """Obtiene CPU de un proceso"""
        try:
            return proc.cpu_percent(interval=0.1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def congelar_proceso(self, proc: psutil.Process, config: ProcessConfig) -> bool:
        """Congela un proceso (SIGSTOP)"""
        try:
            proc.send_signal(signal.SIGSTOP)
            self.log(f"✅ Proceso congelado: {proc.name()} (PID: {proc.pid})")

            # Alertar si está configurado
            if config.alert_on_freeze:
                self.log(f"🔔 ALERTA: {proc.name()} congelado (configurado)")

            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.log(f"❌ Error al congelar {proc.name()}: {e}")
            return False

    def reanudar_proceso(self, proc: psutil.Process, config: ProcessConfig) -> bool:
        """Reanuda un proceso (SIGCONT)"""
        try:
            proc.send_signal(signal.SIGCONT)
            self.log(f"✅ Proceso reanudado: {proc.name()} (PID: {proc.pid})")

            # Alertar si está configurado
            if config.alert_on_thaw:
                self.log(f"🔔 ALERTA: {proc.name()} reanudado (configurado)")

            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.log(f"❌ Error al reanudar {proc.name()}: {e}")
            return False

    def detener_proceso(self, proc: psutil.Process) -> bool:
        """Detiene un proceso (SIGTERM)"""
        try:
            proc.terminate()
            self.log(f"✅ Proceso detenido: {proc.name()} (PID: {proc.pid})")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.log(f"❌ Error al detener {proc.name()}: {e}")
            return False

    def iniciar_proceso(self, name: str) -> bool:
        """Inicia un proceso por nombre"""
        # Comandos para iniciar servicios comunes
        comandos = {
            "docker": "brew services start docker",
            "redis": "brew services start redis",
            "postgres": "brew services start postgresql",
            "mongodb": "brew services start mongodb-community",
            "mysql": "brew services start mysql",
        }

        if name in comandos:
            try:
                # Use shlex.split to avoid shell=True (commands are hardcoded, but safer pattern)
                import shlex

                subprocess.run(
                    shlex.split(comandos[name]),
                    shell=False,
                    check=True,
                    capture_output=True,
                )
                self.log(f"✅ Proceso iniciado: {name}")
                return True
            except subprocess.CalledProcessError as e:
                self.log(f"❌ Error al iniciar {name}: {e}")
                return False
        else:
            self.log(f"❌ No hay comando para iniciar: {name}")
            return False

    def verificar_inactividad(self, proc: psutil.Process, config: ProcessConfig) -> bool:
        """Verifica si un proceso está inactivo"""
        cpu = self.obtener_cpu_proceso(proc)
        self.obtener_memoria_proceso(proc)

        # Si CPU es 0 por más tiempo, está inactivo
        if cpu < 0.1:  # Menos del 0.1% de CPU
            return True

        return False

    def optimizar_memoria(self):
        """Optimiza memoria congelando procesos inactivos"""
        self.log("=" * 60)
        self.log("INICIANDO OPTIMIZACIÓN DE MEMORIA")
        self.log("=" * 60)

        # Obtener memoria total
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_available_gb = mem.available / (1024**3)

        self.log(f"Memoria disponible: {mem_available_gb:.2f} GB ({mem_percent:.1f}%)")

        # Nivel 1: 80% RAM - Limpieza básica
        if mem_percent >= 80:
            self.log("🔴 NIVEL 1 (80%): Limpieza de logs, caché y archivos temporales")
            self.limpiar_logs_y_cache()

        # Nivel 2: 90% RAM - Detener agentes de baja prioridad
        if mem_percent >= 90:
            self.log("🔴🔴 NIVEL 2 (90%): Deteniendo agentes de prioridad 4-8")
            self.detener_agentes_baja_prioridad()

        # Nivel 3: 95% RAM - Reiniciar servicios pesados
        if mem_percent >= 95:
            self.log("🔴🔴🔴 NIVEL 3 (95%): Reiniciando servicios pesados")
            self.reiniciar_servicios_pesados()

        # Si memoria suficiente (> 4 GB), no optimizar procesos
        if mem_available_gb > 4:
            self.log("✅ Memoria suficiente, no se requiere optimización de procesos")
            return

        self.log("⚠️ Memoria baja, deteniendo procesos inactivos...")

        # Optimización tradicional (procesos del sistema)
        configs_ordenadas = sorted(self.configs, key=lambda x: x.priority, reverse=True)

        for config in configs_ordenadas:
            if config.priority <= 2:
                continue

            proc = self.obtener_proceso_por_patron(config.pattern)
            if not proc:
                continue

            memoria = self.obtener_memoria_proceso(proc)
            if memoria > config.min_memory_mb and self.verificar_inactividad(proc, config):
                self.log(f"🧊 Congelando {config.name} ({memoria:.1f} MB)")
                self.congelar_proceso(proc, config)

    def limpiar_logs_y_cache(self):
        """Limpieza básica: logs, caché de Redis y archivos temporales"""
        self.log("🧹 Limpiando logs antiguos...")

        # Limpiar logs antiguos (> 7 días)
        logs_dir = PROJECT_ROOT / "logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                if log_file.stat().st_mtime < time.time() - (7 * 24 * 3600):
                    try:
                        log_file.unlink()
                        self.log(f"   ✅ Eliminado: {log_file.name}")
                    except Exception as e:
                        self.log(f"   ⚠️ Error eliminando {log_file.name}: {e}")

        # Limpiar caché de Redis (si está disponible)
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, db=0)
            r.flushdb()
            self.log("   ✅ Caché de Redis limpiada")
        except:
            self.log("   ⚠️ Redis no disponible para limpieza")

        # Limpiar archivos temporales
        temp_dir = PROJECT_ROOT / "temp"
        if temp_dir.exists():
            for temp_file in temp_dir.glob("*"):
                try:
                    temp_file.unlink()
                    self.log(f"   ✅ Eliminado: {temp_file.name}")
                except Exception as e:
                    self.log(f"   ⚠️ Error eliminando {temp_file.name}: {e}")

    def detener_agentes_baja_prioridad(self):
        """Detiene agentes de baja prioridad (placeholder - implementar según necesidad)"""
        # Placeholder: implementar lógica específica para URA_App

    def reiniciar_servicios_pesados(self):
        """Reinicia servicios pesados (placeholder - implementar según necesidad)"""
        # Placeholder: implementar lógica específica para URA_App

    def reactivar_procesos_necesarios(self):
        """Reactiva procesos que se necesitan"""
        self.log("=" * 60)
        self.log("VERIFICANDO PROCESOS CONGELADOS")
        self.log("=" * 60)

        for pid_str, state in list(self.state.items()):
            if state.status != "frozen":
                continue

            try:
                proc = psutil.Process(int(pid_str))

                # Verificar si el proceso sigue existiendo
                if not proc.is_running():
                    self.log(f"⚠️ Proceso {state.name} ya no existe, eliminando del estado")
                    del self.state[pid_str]
                    self.guardar_estado()
                    continue

                # Verificar tiempo congelado
                frozen_at = datetime.fromisoformat(state.frozen_at)
                tiempo_congelado = datetime.now() - frozen_at

                # Si está congelado más tiempo del máximo, reactivar
                config = next((c for c in self.configs if c.pattern in state.name.lower()), None)
                if config and tiempo_congelado > timedelta(minutes=config.max_inactive_minutes):
                    if self.reanudar_proceso(proc, config):
                        self.state[pid_str] = ProcessState(
                            pid=proc.pid,
                            name=proc.name(),
                            memory_mb=self.obtener_memoria_proceso(proc),
                            cpu_percent=self.obtener_cpu_proceso(proc),
                            last_active=datetime.now().isoformat(),
                            status="running",
                            frozen_at=None,
                        )
                        self.guardar_estado()

            except psutil.NoSuchProcess:
                self.log(f"⚠️ Proceso {state.name} ya no existe, eliminando del estado")
                del self.state[pid_str]
                self.guardar_estado()

    def ejecutar_ciclo(self):
        """Ejecuta un ciclo completo de optimización"""
        self.reactivar_procesos_necesarios()
        self.optimizar_memoria()

    def ejecutar_monitoreo_continuo(self, intervalo_segundos: int = 60):
        """Ejecuta monitoreo continuo"""
        self.log("=" * 60)
        self.log("INICIANDO MONITOREO CONTINUO")
        self.log(f"Intervalo: {intervalo_segundos} segundos")
        self.log("=" * 60)

        try:
            while True:
                self.ejecutar_ciclo()
                time.sleep(intervalo_segundos)
        except KeyboardInterrupt:
            self.log("⚠️ Monitoreo detenido por usuario")

    def mostrar_estado(self):
        """Muestra estado actual de procesos"""
        self.log("=" * 60)
        self.log("ESTADO ACTUAL")
        self.log("=" * 60)

        for config in self.configs:
            proc = self.obtener_proceso_por_patron(config.pattern)
            if proc:
                memoria = self.obtener_memoria_proceso(proc)
                cpu = self.obtener_cpu_proceso(proc)
                pid_str = str(proc.pid)
                estado = self.state.get(
                    pid_str,
                    ProcessState(
                        pid=proc.pid,
                        name=proc.name(),
                        memory_mb=memoria,
                        cpu_percent=cpu,
                        last_active=datetime.now().isoformat(),
                        status="running",
                    ),
                )

                alert_status = ""
                if config.alert_on_freeze or config.alert_on_thaw:
                    alert_status = " [🔔 Alertas]"

                self.log(
                    f"{config.name}: {estado.status} (PID: {proc.pid}, RAM: {memoria:.1f} MB, CPU: {cpu:.1f}%){alert_status}"
                )
            else:
                self.log(f"{config.name}: No ejecutándose")

    def limpiar_procesos_zombi(self):
        """Limpia procesos zombi (procesos que ya no existen en el estado)"""
        pids_eliminados = []

        for pid_str in list(self.state.keys()):
            try:
                proc = psutil.Process(int(pid_str))
                if not proc.is_running():
                    pids_eliminados.append(pid_str)
                    del self.state[pid_str]
                    self.log(f"🧹 Proceso zombi eliminado del estado: PID {pid_str}")
            except psutil.NoSuchProcess:
                pids_eliminados.append(pid_str)
                del self.state[pid_str]
                self.log(f"🧹 Proceso zombi eliminado del estado: PID {pid_str}")

        if pids_eliminados:
            self.guardar_estado()
            self.log(f"✅ {len(pids_eliminados)} procesos zombi limpiados")

    def ajustar_configuracion_dinamica(self):
        """Ajusta umbrales dinámicamente basado en carga del sistema"""
        mem_stats = self.obtener_memoria_total()

        # Si memoria muy baja (< 2 GB), ser más agresivo
        if mem_stats["available_gb"] < 2:
            self.log("⚠️ Memoria crítica, ajustando umbrales dinámicamente")
            # Reducir tiempos de inactividad a la mitad
            for config in self.configs:
                config.max_inactive_minutes = max(2, config.max_inactive_minutes // 2)
                self.log(f"   {config.name}: umbral reducido a {config.max_inactive_minutes} min")
        elif mem_stats["available_gb"] > 6:
            self.log("✅ Memoria abundante, restaurando umbrales normales")
            # Restaurar umbrales originales (recargar config)
            self.configs = self.cargar_config()

    def predecir_uso_memoria(self, minutos: int = 30) -> float:
        """Predice uso de memoria en X minutos basado en historial"""
        if len(self.historial_memoria) < 10:
            return 0.0

        # Obtener últimos N registros
        recientes = self.historial_memoria[-10:]

        # Calcular tendencia
        usos = [r["used_gb"] for r in recientes]
        tendencia = (usos[-1] - usos[0]) / len(usos)  # GB por registro

        # Predecir
        prediccion = usos[-1] + (tendencia * minutos)  # Asumiendo 1 registro por minuto

        return max(0, prediccion)

    def obtener_estadisticas_historial(self, horas: int = 24) -> dict:
        """Obtiene estadísticas del historial de memoria"""
        if not self.historial_memoria:
            return {"promedio_uso": 0, "max_uso": 0, "min_uso": 0}

        # Filtrar por horas
        limite = datetime.now() - timedelta(hours=horas)
        recientes = [
            r for r in self.historial_memoria if datetime.fromisoformat(r["timestamp"]) > limite
        ]

        if not recientes:
            return {"promedio_uso": 0, "max_uso": 0, "min_uso": 0}

        usos = [r["used_gb"] for r in recientes]
        return {
            "promedio_uso": sum(usos) / len(usos),
            "max_uso": max(usos),
            "min_uso": min(usos),
            "registros": len(recientes),
        }


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Gestor de Memoria RAM URA")
    parser.add_argument("--ciclo", action="store_true", help="Ejecutar un ciclo de optimización")
    parser.add_argument("--monitoreo", type=int, help="Ejecutar monitoreo continuo (segundos)")
    parser.add_argument("--estado", action="store_true", help="Mostrar estado actual")
    parser.add_argument("--reactivar", help="Reactivar un proceso específico")
    parser.add_argument("--congelar", help="Congelar un proceso específico")
    parser.add_argument("--estadisticas", type=int, help="Mostrar estadísticas históricas (horas)")

    args = parser.parse_args()

    manager = MemoryManager()

    if args.estado:
        manager.mostrar_estado()
    elif args.reactivar:
        proc = manager.obtener_proceso_por_patron(args.reactivar)
        if proc:
            config = next(
                (c for c in manager.configs if c.pattern in args.reactivar.lower()),
                None,
            )
            if config:
                manager.reanudar_proceso(proc, config)
            else:
                manager.reanudar_proceso(proc, manager.configs[0])
    elif args.congelar:
        proc = manager.obtener_proceso_por_patron(args.congelar)
        if proc:
            config = next((c for c in manager.configs if c.pattern in args.congelar.lower()), None)
            if config:
                manager.congelar_proceso(proc, config)
            else:
                manager.congelar_proceso(proc, manager.configs[0])
    elif args.estadisticas:
        stats = manager.obtener_estadisticas_historial(args.estadisticas)
        print(f"Promedio uso: {stats['promedio_uso']:.2f} GB")
        print(f"Max uso: {stats['max_uso']:.2f} GB")
        print(f"Min uso: {stats['min_uso']:.2f} GB")
        print(f"Registros: {stats['registros']}")
    elif args.monitoreo:
        manager.ejecutar_monitoreo_continuo(args.monitoreo)
    elif args.ciclo:
        manager.ejecutar_ciclo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

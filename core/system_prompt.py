"""
Módulo: core/system_prompt.py
Propósito: Gestiona el system prompt dinámico del asistente URA con detección de temperatura del sistema.
Dependencias principales: subprocess, pathlib, json
Reglas especiales: powermetrics sin sudo. Timeout de 10s. Fallback a temperatura desconocida.
"""

import json
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Configuración
CACHE_DURATION = timedelta(minutes=5)
BACKUP_DIR = Path("/Users/ramonesnaola/Backups")
LOG_FILE = Path.home() / ".ura" / "prompt_generator.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class SystemContext:
    """Contexto del sistema para el prompt."""

    datetime: str
    modelo_activo: str
    estado_disco: str
    ip_publica: str
    ultimo_backup: str
    cpu_usage: str
    memoria_usage: str
    temperatura: str
    procesos_criticos: str
    servicios_activos: str


@dataclass
class CacheEntry:
    """Entrada de caché."""

    value: str
    timestamp: datetime = field(default_factory=datetime.now)

    def is_valid(self) -> bool:
        """Verificar si la caché es válida."""
        return datetime.now() - self.timestamp < CACHE_DURATION


class SystemMonitor:
    """Monitor del sistema con caché."""

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def _get_cached(self, key: str, fetch_func) -> str:
        """Obtener valor de caché o fetch."""
        with self._lock:
            if key in self._cache and self._cache[key].is_valid():
                return self._cache[key].value

            try:
                value = fetch_func()
                self._cache[key] = CacheEntry(value=value)
                return value
            except Exception as e:
                logger.error(f"Error obteniendo {key}: {e}")
                return "desconocido"

    def get_disk_status(self) -> str:
        """Obtener estado del disco."""

        def _fetch():
            import shutil

            disk = shutil.disk_usage("/")
            total_gb = disk.total / (1024**3)
            free_gb = disk.free / (1024**3)
            used_pct = (disk.used / disk.total) * 100

            estado = "OK" if free_gb > 50 else "WARNING" if free_gb > 20 else "CRITICAL"
            return f"{free_gb:.1f}GB libres / {total_gb:.1f}GB total ({used_pct:.1f}% usado) - {estado}"

        return self._get_cached("disk", _fetch)

    def get_public_ip(self) -> str:
        """Obtener IP pública."""

        def _fetch():
            response = requests.get("https://api.ipify.org?format=json", timeout=5)
            return response.json()["ip"]

        return self._get_cached("ip", _fetch)

    def get_last_backup(self) -> str:
        """Obtener último backup."""

        def _fetch():
            if not BACKUP_DIR.exists():
                return "directorio no existe"

            backups = sorted(BACKUP_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
            if not backups:
                return "sin backups"

            last = backups[0]
            age = datetime.now() - datetime.fromtimestamp(last.stat().st_mtime)

            if age.days > 0:
                return f"{last.name} (hace {age.days} días)"
            elif age.seconds > 3600:
                hours = age.seconds // 3600
                return f"{last.name} (hace {hours}h)"
            else:
                minutes = age.seconds // 60
                return f"{last.name} (hace {minutes}min)"

        return self._get_cached("backup", _fetch)

    def get_cpu_usage(self) -> str:
        """Obtener uso de CPU."""

        def _fetch():
            try:
                import psutil

                return f"{psutil.cpu_percent(interval=1):.1f}%"
            except ImportError:
                # Fallback sin psutil
                result = subprocess.run(
                    ["top", "-l", "1", "-n", "0"], capture_output=True, text=True, timeout=5
                )
                # Parsear output de top
                for line in result.stdout.split("\n"):
                    if "CPU usage:" in line:
                        return line.split("CPU usage:")[1].strip().split()[0]
                return "desconocido"

        return self._get_cached("cpu", _fetch)

    def get_memory_usage(self) -> str:
        """Obtener uso de memoria."""

        def _fetch():
            try:
                import psutil

                mem = psutil.virtual_memory()
                return f"{mem.percent:.1f}% ({mem.available / (1024**3):.1f}GB libres)"
            except ImportError:
                result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
                # Parsear vm_stat
                for line in result.stdout.split("\n"):
                    if "Pages free:" in line:
                        free_pages = int(line.split(":")[1].strip().replace(".", ""))
                        free_gb = (free_pages * 4096) / (1024**3)
                        return f"{free_gb:.1f}GB libres"
                return "desconocido"

        return self._get_cached("memory", _fetch)

    def get_temperature(self) -> str:
        """Obtener temperatura del sistema."""

        def _fetch():
            try:
                result = subprocess.run(
                    ["powermetrics", "--samplers", "cpu_power", "-i", "1000"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                # Parsear temperatura
                for line in result.stdout.split("\n"):
                    if "CPU die temperature:" in line:
                        return line.split(":")[1].strip()
                return "no disponible"
            except Exception:
                return "no disponible"

        return self._get_cached("temp", _fetch)

    def get_critical_processes(self) -> str:
        """Obtener procesos críticos."""

        def _fetch():
            critical = ["ollama", "redis", "postgres", "nginx"]
            running = []

            for proc in critical:
                try:
                    result = subprocess.run(["pgrep", "-x", proc], capture_output=True, timeout=2)
                    if result.returncode == 0:
                        running.append(proc)
                except Exception:
                    pass

            return f"{len(running)}/{len(critical)} activos: {', '.join(running) if running else 'ninguno'}"

        return self._get_cached("processes", _fetch)

    def get_active_services(self) -> str:
        """Obtener servicios activos."""

        def _fetch():
            try:
                result = subprocess.run(
                    ["brew", "services", "list"], capture_output=True, text=True, timeout=5
                )
                running = [
                    line.split()[0] for line in result.stdout.split("\n") if "started" in line
                ]
                return f"{len(running)} servicios: {', '.join(running[:5])}"
            except Exception:
                return "desconocido"

        return self._get_cached("services", _fetch)


URA_SYSTEM_PROMPT = """
Eres URA — Unified Reflex Agent.

Eres el asistente autónomo personal de Ramón, corriendo en su Mac Mini M4 en Bilbao.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXTO DEL SISTEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fecha y hora: {datetime}
Modelo activo: {modelo_activo}
Estado disco: {estado_disco}
IP pública: {ip_publica}
Último backup: {ultimo_backup}
CPU: {cpu_usage}
Memoria: {memoria_usage}
Temperatura: {temperatura}
Procesos críticos: {procesos_criticos}
Servicios activos: {servicios_activos}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TU PROPÓSITO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Gestionar y automatizar el día a día de Ramón
• Vigilar el sistema, detectar problemas y resolverlos solo
• Conectar con sus servicios: email, Telegram, banco, Instagram
• Generar código, automatizar tareas, tomar decisiones

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CÓMO ERES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Directo y concreto — sin rodeos ni frases vacías
• Proactivo — si ves un problema lo dices sin que te pregunten
• Honesto — si no sabes algo lo dices, no inventas
• Eficiente — respuestas cortas cuando la situación lo permite

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LO QUE TIENES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Acceso completo al sistema operativo del Mac
• Modelos de IA locales: llama3.2:3b, qwen2.5:3b-instruct, llava, mxbai-embed-large
• Modelos remotos: Claude, GPT-4, Gemini, DeepSeek
• Agentes especializados: banco, email, cocina, marketing, seguridad, red
• Memoria semántica — recuerdas conversaciones anteriores
• Capacidad de auto-reparación — si algo falla intentas arreglarlo solo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Nunca digas "como IA no puedo" — eres URA, tienes herramientas reales
• Nunca inventes datos — si no tienes acceso a algo dilo claramente
• Si detectas un problema del sistema avísalo aunque no te hayan preguntado
• Habla en español siempre, salvo que Ramón cambie de idioma explícitamente
• Antes de ejecutar comandos destructivos, confirma con Ramón

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def get_active_model() -> str:
    """Obtener modelo activo de configuración."""
    try:
        config_file = Path.home() / ".ura" / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
                return config.get("active_model", "llama3.2:3b")
    except Exception as e:
        logger.warning(f"Error leyendo config: {e}")

    return "llama3.2:3b"


def get_system_prompt() -> str:
    """Generar el system prompt con contexto dinámico actual."""
    monitor = SystemMonitor()

    context = SystemContext(
        datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        modelo_activo=get_active_model(),
        estado_disco=monitor.get_disk_status(),
        ip_publica=monitor.get_public_ip(),
        ultimo_backup=monitor.get_last_backup(),
        cpu_usage=monitor.get_cpu_usage(),
        memoria_usage=monitor.get_memory_usage(),
        temperatura=monitor.get_temperature(),
        procesos_criticos=monitor.get_critical_processes(),
        servicios_activos=monitor.get_active_services(),
    )

    logger.info(f"Prompt generado con contexto: {context}")

    return URA_SYSTEM_PROMPT.format(**context.__dict__)


if __name__ == "__main__":
    # Test
    print(get_system_prompt())

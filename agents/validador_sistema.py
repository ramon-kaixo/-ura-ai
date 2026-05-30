#!/usr/bin/env python3
# validador_sistema.py – Escáner de integridad para URA
# Comprueba: dependencias, puertos, procesos, configuracion, disco, Git, etc.

import json
import os
import socket
import subprocess
import sys
import yaml
from datetime import datetime

URA_PATH = "/opt/ura"
REQUIREMENTS = "/opt/ura/requirements.txt"
PUERTOS_CRITICOS = [8081, 8082, 3000, 3080, 5000, 5678, 9090, 3001, 11434]
AGENTES_CRITICOS = [
    "ura_api.py",
    "scheduler_orchestrator.py",
    "agente_backup.py",
    "monitor_circuit_breaker.py",
]
LOG_FILE = "/var/log/ura_validador.log"
NOTIFICAR_SCRIPT = "/opt/ura/scripts/notificar.sh"
SUGERENCIAS_FILE = "/opt/ura/data/sugerencias.json"
ERRORES: list[str] = []


def log_error(mensaje):
    ERRORES.append(mensaje)
    timestamp = datetime.now().isoformat()
    linea = f"{timestamp} - ERROR: {mensaje}"
    print(linea)
    with open(LOG_FILE, "a") as f:
        f.write(linea + "\n")


def log_info(mensaje):
    timestamp = datetime.now().isoformat()
    linea = f"{timestamp} - INFO: {mensaje}"
    print(linea)
    with open(LOG_FILE, "a") as f:
        f.write(linea + "\n")


def notificar(mensaje):
    if os.path.exists(NOTIFICAR_SCRIPT):
        subprocess.run([NOTIFICAR_SCRIPT, f"Validador: {mensaje}"])


def agregar_sugerencia(problema, solucion):
    sugerencias = []
    if os.path.exists(SUGERENCIAS_FILE):
        with open(SUGERENCIAS_FILE) as f:
            sugerencias = json.load(f)
    sugerencias.append(
        {
            "timestamp": datetime.now().timestamp(),
            "dominio": "validador",
            "problema": problema,
            "solucion": solucion,
            "gravedad": "alta",
        }
    )
    with open(SUGERENCIAS_FILE, "w") as f:
        json.dump(sugerencias, f, indent=2)


def check_dependencias():
    log_info("Comprobando dependencias...")
    venv_dir = "/tmp/ura_venv_check"
    subprocess.run(["python3", "-m", "venv", venv_dir], capture_output=True)
    pip = f"{venv_dir}/bin/pip"
    subprocess.run([pip, "install", "-r", REQUIREMENTS], capture_output=True)
    result = subprocess.run(
        [
            f"{venv_dir}/bin/python",
            "-c",
            f"import sys; sys.path.insert(0, '{URA_PATH}'); import core; import agents; print('OK')",
        ],
        capture_output=True,
    )
    subprocess.run(["rm", "-rf", venv_dir])
    if result.returncode != 0:
        log_error(f"Fallo en dependencias: {result.stderr.decode()}")
        return False
    return True


def check_puertos():
    log_info("Comprobando puertos...")
    puertos_ocupados = []
    for port in PUERTOS_CRITICOS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(("localhost", port))
        sock.close()
        if result == 0:
            puertos_ocupados.append(port)
    if len(puertos_ocupados) != len(set(puertos_ocupados)):
        log_error(f"Puertos duplicados en uso: {puertos_ocupados}")
        return False
    return True


def check_procesos():
    log_info("Comprobando procesos criticos...")
    fallos = []
    for agente in AGENTES_CRITICOS:
        result = subprocess.run(["pgrep", "-f", agente], capture_output=True)
        if result.returncode != 0:
            fallos.append(agente)
    if fallos:
        log_error(f"Agentes criticos no encontrados: {fallos}")
        return False
    return True


def check_configuracion():
    log_info("Validando archivos de configuracion...")
    errores = False
    config_dir = os.path.join(URA_PATH, "config")
    if not os.path.exists(config_dir):
        log_info("Directorio config no encontrado, se omite")
        return True
    for root, _dirs, files in os.walk(config_dir):
        for file in files:
            path = os.path.join(root, file)
            if file.endswith(".json"):
                try:
                    with open(path) as f:
                        json.load(f)
                except Exception as e:
                    log_error(f"JSON invalido {path}: {e}")
                    errores = True
            elif file.endswith((".yaml", ".yml")):
                try:
                    with open(path) as f:
                        yaml.safe_load(f)
                except Exception as e:
                    log_error(f"YAML invalido {path}: {e}")
                    errores = True
    return not errores


def check_espacio():
    statvfs = os.statvfs("/")
    free_mb = (statvfs.f_frsize * statvfs.f_bavail) / (1024 * 1024)
    if free_mb < 500:
        log_error(f"Espacio en disco bajo: {free_mb:.0f} MB libres")
        return False
    return True


def check_git():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=URA_PATH,
    )
    cambios = [line for line in result.stdout.splitlines() if not line.startswith("??")]
    if cambios:
        log_error(f"Cambios sin commit en Git: {len(cambios)} archivos modificados")
        return False
    return True


def check_duplicados_core():
    core_dir = os.path.join(URA_PATH, "core")
    agents_dir = os.path.join(URA_PATH, "agents")
    if not os.path.exists(core_dir) or not os.path.exists(agents_dir):
        return True
    core_files = set(os.listdir(core_dir)) - {"__pycache__", "__init__.py"}
    agents_files = set(os.listdir(agents_dir)) - {"__pycache__", "__init__.py"}
    duplicados = core_files.intersection(agents_files)
    if duplicados:
        log_error(f"Archivos duplicados entre core/ y agents/: {duplicados}")
        return False
    return True


def check_docker():
    log_info("Comprobando Docker...")
    docker_paths = ["/usr/local/bin/docker", "/opt/homebrew/bin/docker"]
    if not any(os.path.exists(d) for d in docker_paths):
        log_error("Docker no esta instalado en el sistema")
        return False
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        log_error("El servicio Docker no esta corriendo")
        return False
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=ura_sandbox", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if "ura_sandbox" not in result.stdout:
        log_info("Advertencia: contenedor ura_sandbox no encontrado")
    return True


def check_zombie_processes():
    log_info("Comprobando procesos zombie...")
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True,
    )
    zombies = [
        line for line in result.stdout.splitlines() if "defunct" in line or "<defunct>" in line
    ]
    if zombies:
        log_error(f"Se encontraron procesos zombie: {len(zombies)}")
        for z in zombies[:3]:
            log_info(f"  {z.strip()}")
        return False
    return True


def check_health_endpoints():
    log_info("Validando endpoints de Health API...")
    errores = False
    endpoints = [
        ("http://localhost:8081/health", 200, "Health API"),
        ("http://localhost:8081/api/estado_flota", 200, "Estado flota"),
        ("http://localhost:8081/api/red/dispositivos", 200, "Red dispositivos"),
    ]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    sandbox_up = sock.connect_ex(("localhost", 8082)) == 0
    sock.close()
    if sandbox_up:
        endpoints.append(("http://localhost:8082/health", 200, "Sandbox API"))

    for url, expected_status, nombre in endpoints:
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
                capture_output=True,
                text=True,
            )
            status = int(result.stdout.strip())
            if status != expected_status:
                log_error(
                    f"Endpoint {nombre} ({url}) devolvio {status}, se esperaba {expected_status}"
                )
                errores = True
            else:
                log_info(f"OK {nombre}")
        except Exception as e:
            log_error(f"No se pudo conectar a {nombre}: {e}")
            errores = True
    return not errores


def main():
    log_info("=== Inicio de validacion del sistema ===")

    checks = [
        ("Dependencias", check_dependencias),
        ("Puertos", check_puertos),
        ("Procesos", check_procesos),
        ("Configuracion", check_configuracion),
        ("Espacio", check_espacio),
        ("Git", check_git),
        ("Duplicados core/agents", check_duplicados_core),
        ("Docker", check_docker),
        ("Procesos zombie", check_zombie_processes),
        ("Health API endpoints", check_health_endpoints),
    ]

    for nombre, func in checks:
        if not func():
            notificar(f"Fallo en comprobacion: {nombre}")
            agregar_sugerencia(f"Fallo en {nombre}", "Revisar logs y corregir")

    if ERRORES:
        log_info(f"Se encontraron {len(ERRORES)} errores.")
        sys.exit(1)
    log_info("Todas las comprobaciones pasaron correctamente.")
    sys.exit(0)


if __name__ == "__main__":
    main()

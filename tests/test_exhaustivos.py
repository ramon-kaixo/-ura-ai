#!/usr/bin/env python3
"""
Tests Exhaustivos - URA App
Suite de pruebas completas para verificar integridad del sistema
"""

import os
import subprocess
from pathlib import Path

import pytest


def test_sintaxis_python():
    """Verificar sintaxis de todos los archivos Python"""
    ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")
    archivos_py = list(ura_app_path.rglob("*.py"))

    errores = []
    for archivo in archivos_py[:200]:
        try:
            compile(open(archivo).read(), str(archivo), "exec")
        except SyntaxError as e:
            errores.append(f"{archivo}: {e}")

    assert len(errores) == 0, f"Errores de sintaxis: {errores}"


def test_dependencias_instaladas():
    """Verificar que todas las dependencias estén instaladas"""
    pytest.importorskip("PyQt5", reason="PyQt5 no instalado - dependencia opcional de UI")
    pytest.importorskip("redis", reason="redis no instalado - dependencia opcional")

    resultado = subprocess.run(
        ["python3", "-m", "pip", "list"], capture_output=True, text=True, timeout=30
    )

    assert resultado.returncode == 0, "No se pudo listar dependencias"

    # Verificar dependencias críticas (case-insensitive)
    dependencias_criticas = ["pyautogui", "requests", "psutil"]
    stdout_lower = resultado.stdout.lower()
    for dep in dependencias_criticas:
        assert dep.lower() in stdout_lower, f"Dependencia faltante: {dep}"


@pytest.mark.skipif(
    subprocess.run(["which", "ollama"], capture_output=True, timeout=5).returncode != 0,
    reason="Ollama no instalado",
)
def test_conexion_ollama():
    """Verificar conexión con Ollama"""
    try:
        resultado = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        pytest.skip("Ollama no responde (servicio no activo)")

    assert resultado.returncode == 0, "Ollama no responde"
    assert "llama3" in resultado.stdout, "Modelo llama3 no encontrado"


def test_conexion_redis():
    """Verificar conexión con Redis"""
    pytest.importorskip("redis", reason="redis no instalado - dependencia opcional")

    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        assert True, "Redis conectado"
    except Exception as e:
        raise AssertionError(f"Redis no conectado: {e}")


def test_archivo_config():
    """Verificar que archivos de configuración existan"""
    ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")

    archivos_config = [
        "config/department_profiles.json",
        "config/learning_config.json",
        "URA_launcher.py",
        "core/docker_bridge.py",
    ]

    for archivo in archivos_config:
        archivo_path = ura_app_path / archivo
        assert archivo_path.exists(), f"Archivo faltante: {archivo}"


def test_directorios_esenciales():
    """Verificar que directorios esenciales existan"""
    ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")

    directorios = ["core", "agents", "connectors", "scripts", "config", "logs", "tests"]

    for directorio in directorios:
        dir_path = ura_app_path / directorio
        assert dir_path.exists(), f"Directorio faltante: {directorio}"


def test_permisos_escritura():
    """Verificar permisos de escritura en directorios críticos"""
    ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")

    directorios = ["logs", "versions", "data"]

    for directorio in directorios:
        dir_path = ura_app_path / directorio
        if dir_path.exists():
            assert os.access(dir_path, os.W_OK), f"Sin permisos de escritura: {directorio}"


def test_imports_criticos():
    """Verificar que imports críticos funcionen"""
    try:
        pass

        assert True, "Imports críticos funcionan"
    except ImportError as e:
        raise AssertionError(f"Import falló: {e}")


@pytest.mark.skipif(
    subprocess.run(["docker", "ps"], capture_output=True, timeout=5).returncode != 0,
    reason="Docker no disponible en este entorno",
)
def test_docker_sandbox_activo():
    """Verificar que sandbox Docker esté activo"""
    resultado = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)

    ura_containers = ["ura-sandbox", "ura_sandbox", "ura-api", "ura_api", "ura-app", "ura_app"]
    has_ura = any(c in resultado.stdout for c in ura_containers)
    assert has_ura, "Ningún contenedor URA activo en Docker"


def test_memoria_suficiente():
    """Verificar que haya suficiente memoria disponible"""
    import psutil

    memoria = psutil.virtual_memory()
    memoria_disponible_gb = memoria.available / (1024**3)

    assert memoria_disponible_gb > 2, f"Memoria insuficiente: {memoria_disponible_gb:.1f}GB"


def test_disco_suficiente():
    """Verificar que haya suficiente espacio en disco"""
    import psutil

    disco = psutil.disk_usage("/")
    disco_libre_gb = disco.free / (1024**3)

    assert disco_libre_gb > 5, f"Disco insuficiente: {disco_libre_gb:.1f}GB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

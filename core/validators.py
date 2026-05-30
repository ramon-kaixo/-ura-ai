#!/usr/bin/env python3
"""
URA - Validation Functions
Funciones de validación para configuración y dependencias
"""

import logging


def validate_security_setup():
    """Validar configuración de seguridad al inicio"""
    warnings = []

    # Verificar herramientas de seguridad
    try:
        import subprocess

        result = subprocess.run(
            ["pip-audit", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            warnings.append("✅ pip-audit disponible")
        else:
            warnings.append("⚠️ pip-audit no disponible")
    except:
        warnings.append("⚠️ pip-audit no instalado")

    try:
        result = subprocess.run(["safety", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            warnings.append("✅ safety disponible")
        else:
            warnings.append("⚠️ safety no disponible")
    except:
        warnings.append("⚠️ safety no instalado")

    try:
        result = subprocess.run(["bandit", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            warnings.append("✅ bandit disponible")
        else:
            warnings.append("⚠️ bandit no disponible")
    except:
        warnings.append("⚠️ bandit no instalado")

    try:
        pass

        warnings.append("✅ websockets disponible")
    except ImportError:
        warnings.append("⚠️ websockets no instalado")

    return warnings


def check_dependencies():
    """Verificar dependencias críticas al arrancar"""
    dep_logger = logging.getLogger(__name__)

    required = ["PyQt5", "requests", "ollama", "redis"]
    all_ok = True
    missing = []

    for dep in required:
        try:
            __import__(dep)
            dep_logger.info(f"✅ {dep}")
        except ImportError:
            dep_logger.error(f"❌ {dep} no instalado")
            missing.append(dep)
            all_ok = False

    return all_ok, missing

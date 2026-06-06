#!/usr/bin/env python3
"""file_security.py — Verificación y corrección de permisos en archivos URA.

Se ejecuta al inicio del supervisor para asegurar que logs/ y config/
tengan permisos 600 (solo lectura/escritura para el dueño).
"""

import logging
import os
import stat as statmod
from pathlib import Path

log = logging.getLogger("file_sec")

# Archivos/directorios críticos que deben tener permisos restringidos
CRITICAL_PATHS = [
    ".env",
    "config/baseline.json",
    "config/system_config.json",
    "core/auth_layer.py",
    "core/supervisor.py",
    "core/state.py",
]

# Directorios que deben existir con permisos 700
CRITICAL_DIRS = [
    "logs",
    "logs/telemetry",
    "config",
    "deploy",
]


def verify_and_fix() -> list[str]:
    """Verifica permisos de archivos críticos. Corrige si es necesario.

    Returns:
        Lista de alertas (vacía si todo está correcto).
    """
    base = Path(__file__).parent.parent
    alerts: list[str] = []

    # Asegurar que directorios críticos existan
    for d in CRITICAL_DIRS:
        path = base / d
        try:
            path.mkdir(parents=True, exist_ok=True)
            current = path.stat().st_mode & 0o777
            desired = 0o700
            if current != desired:
                path.chmod(desired)
                log.info("permisos corregidos: %s %o -> %o", d, current, desired)
        except Exception as e:
            alerts.append(f"No se pudo asegurar directorio {d}: {e}")

    # Verificar archivos críticos
    for f in CRITICAL_PATHS:
        path = base / f
        if not path.exists():
            alerts.append(f"Archivo crítico no encontrado: {f}")
            continue
        try:
            current = path.stat().st_mode & 0o777
            # Archivos regulares: 600, directorios: 700
            if path.is_dir():
                desired = 0o700
            else:
                desired = 0o600
            if current != desired:
                path.chmod(desired)
                log.info("permisos corregidos: %s %o -> %o", f, current, desired)
        except Exception as e:
            alerts.append(f"No se pudieron corregir permisos de {f}: {e}")

    # Verificar directorio logs/telemetry y sus archivos
    telemetry_dir = base / "logs" / "telemetry"
    if telemetry_dir.exists():
        for jf in telemetry_dir.glob("*.jsonl"):
            try:
                current = jf.stat().st_mode & 0o777
                if current != 0o600:
                    jf.chmod(0o600)
                    log.info("permisos corregidos: logs/telemetry/%s %o -> 600", jf.name, current)
            except Exception:
                pass

    if alerts:
        for a in alerts:
            log.warning("file_security: %s", a)
    else:
        log.info("file_security: todos los permisos verificados y correctos")

    return alerts

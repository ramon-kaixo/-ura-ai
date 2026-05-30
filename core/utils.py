#!/usr/bin/env python3
"""
URA - Shared Utilities
Funciones compartidas para evitar redundancias entre módulos
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path


# Configurar logging centralizado
def setup_logger(name: str, log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """
    Configurar logger centralizado

    Args:
        name: Nombre del logger
        log_file: Ruta al archivo de log
        level: Nivel de logging

    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicados de handlers
    if not logger.handlers:
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    return logger


def generate_hash(data: str) -> str:
    """
    Generar hash SHA256 de datos

    Args:
        data: Datos a hashear

    Returns:
        str: Hash SHA256
    """
    return hashlib.sha256(data.encode()).hexdigest()


def load_json_file(file_path: Path) -> dict | None:
    """
    Cargar archivo JSON de forma segura

    Args:
        file_path: Ruta al archivo JSON

    Returns:
        Optional[dict]: Contenido del JSON o None si falla
    """
    try:
        if file_path.exists():
            with open(file_path) as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error cargando JSON {file_path}: {e}")
    return None


def save_json_file(file_path: Path, data: dict) -> bool:
    """
    Guardar archivo JSON de forma segura

    Args:
        file_path: Ruta al archivo JSON
        data: Datos a guardar

    Returns:
        bool: True si exitoso, False si falla
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error guardando JSON {file_path}: {e}")
        return False


def get_relative_path(file_path: Path, base_path: Path | None = None) -> Path:
    """
    Obtener ruta relativa a base_path

    Args:
        file_path: Ruta absoluta
        base_path: Ruta base (default: directorio del proyecto actual)

    Returns:
        Path: Ruta relativa
    """
    if base_path is None:
        base_path = Path(__file__).parent.parent

    try:
        return file_path.relative_to(base_path)
    except ValueError:
        return file_path


def log_event(log_path: Path, event_type: str, message: str, level: str = "INFO"):
    """
    Registrar evento en archivo de log

    Args:
        log_path: Ruta al archivo de log
        event_type: Tipo de evento
        message: Mensaje del evento
        level: Nivel de logging
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] [{event_type}] {message}\n"

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(log_entry)
    except Exception as e:
        logging.error(f"Error escribiendo log {log_path}: {e}")


def clean_old_logs(log_dir: Path, days: int = 7) -> int:
    """
    Limpiar logs antiguos

    Args:
        log_dir: Directorio de logs
        days: Días de antigüedad para eliminar

    Returns:
        int: Número de archivos eliminados
    """
    from datetime import timedelta

    if not log_dir.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0

    for log_file in log_dir.glob("*.log"):
        try:
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                log_file.unlink()
                deleted_count += 1
        except Exception as e:
            logging.error(f"Error eliminando {log_file}: {e}")

    return deleted_count


def reset_log_file(log_path: Path, initial_content: str = ""):
    """
    Resetear archivo de log con contenido inicial

    Args:
        log_path: Ruta al archivo de log
        initial_content: Contenido inicial
    """
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            f.write(initial_content)
    except Exception as e:
        logging.error(f"Error reseteando {log_path}: {e}")


def sanitize_path(path: str) -> str:
    """
    Sanitizar ruta de archivo para evitar inyecciones

    Args:
        path: Ruta a sanitizar

    Returns:
        str: Ruta sanitizada
    """
    # Eliminar caracteres peligrosos
    dangerous_chars = ["..", "~", "$", "`", ";", "|", "&"]
    for char in dangerous_chars:
        path = path.replace(char, "")

    # Normalizar ruta
    return str(Path(path).as_posix())


def validate_file_path(file_path: Path, allowed_dirs: list[Path]) -> bool:
    """
    Validar que un archivo está dentro de directorios permitidos

    Args:
        file_path: Ruta a validar
        allowed_dirs: Lista de directorios permitidos

    Returns:
        bool: True si es válido, False si no
    """
    try:
        resolved_path = file_path.resolve()
        for allowed_dir in allowed_dirs:
            if resolved_path.is_relative_to(allowed_dir.resolve()):
                return True
        return False
    except Exception:
        return False


# Patrones peligrosos para sanitización de entrada
dangerous_patterns = ["rm -rf", "sudo ", "chmod 777", "dd if=/dev/zero", "mkfs", ":(){ :|:& };:"]


def safe_execute(func, fallback=None):
    """Ejecutar función de forma segura con fallback"""
    logger = logging.getLogger(__name__)
    try:
        return func()
    except Exception as e:
        logger.error(f"Error en {func.__name__ if hasattr(func, '__name__') else 'funcion'}: {e}")
        return fallback


def sanitize_log(message: str) -> str:
    """Sanitiza mensajes de log para ocultar secretos.

    Args:
        message: Mensaje de log original.

    Returns:
        Mensaje con secretos reemplazados por ***.
    """
    patterns = [
        r"(?i)(password|passwd|token|key|secret)\s*[:=]\s*[^\s]+",
        r"(?i)(bearer\s+)[^\s]+",
        r"(?i)(api[_-]?key\s*[:=]\s*)[^\s]+",
    ]
    for pat in patterns:
        message = re.sub(pat, r"\1***", message)
    return message


def sanitize_input(user_input):
    """Sanitizar entrada de usuario para prevenir comandos peligrosos"""
    logger = logging.getLogger(__name__)
    if not user_input:
        return user_input

    for pattern in dangerous_patterns:
        if pattern in user_input:
            logger.warning(f"Intento de comando peligroso bloqueado: {pattern}")
            return "⚠️ Comando no permitido por seguridad"

    return user_input

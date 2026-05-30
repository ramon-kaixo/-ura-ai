#!/usr/bin/env python3
"""
core/repetition_detector.py - Detector de tareas repetitivas
Lee logs/ buscando patrones de acciones repetidas y guarda candidatas
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("repetition_detector", log_dir="./logs")

# Configuración
REPETITION_THRESHOLD = 3  # Mínimo de repeticiones
TIME_WINDOW_DAYS = 7  # Ventana de tiempo en días
CANDIDATES_FILE = Path(__file__).parent.parent / "data" / "repetition_candidates.json"
LOGS_DIR = Path(__file__).parent.parent / "logs"


def _extract_function_call(log_line: str) -> dict | None:
    """Extrae información de función llamada de una línea de log"""
    # Patrones comunes de llamadas a funciones en logs
    patterns = [
        r"(\w+)\.(\w+)\((.*?)\)",  # module.function(args)
        r"calling (\w+)\((.*?)\)",  # calling function(args)
        r"executing (\w+)\((.*?)\)",  # executing function(args)
    ]

    for pattern in patterns:
        match = re.search(pattern, log_line, re.IGNORECASE)
        if match:
            if len(match.groups()) == 3:
                return {
                    "module": match.group(1),
                    "function": match.group(2),
                    "args": match.group(3),
                }
            elif len(match.groups()) == 2:
                return {"module": "unknown", "function": match.group(1), "args": match.group(2)}

    return None


def _normalize_params(params: str) -> str:
    """Normaliza parámetros para detectar similitudes"""
    # Eliminar valores específicos, mantener estructura
    normalized = re.sub(r'["\'].*?["\']', '"VALUE"', params)
    normalized = re.sub(r"\b\d+\b", "NUM", normalized)
    normalized = re.sub(r"\b[0-9a-fA-F]{8,}\b", "HASH", normalized)
    return normalized


def _read_logs(days: int = 7) -> list[str]:
    """Lee logs de los últimos N días"""
    log_lines = []
    cutoff_date = datetime.now() - timedelta(days=days)

    if not LOGS_DIR.exists():
        logger.warning(f"Directorio de logs no existe: {LOGS_DIR}")
        return log_lines

    for log_file in LOGS_DIR.glob("*.log"):
        try:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    # Extraer fecha del log (formato común: 2024-04-29 12:00:00)
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                    if date_match:
                        log_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                        if log_date >= cutoff_date:
                            log_lines.append(line.strip())
        except Exception as e:
            logger.error(f"Error leyendo {log_file}: {e}")

    return log_lines


def _detect_repetitions(log_lines: list[str]) -> dict[str, dict]:
    """Detecta patrones repetitivos en los logs"""
    pattern_counts: dict[str, dict] = {}

    for line in log_lines:
        call_info = _extract_function_call(line)
        if call_info:
            # Crear clave única: module.function + params normalizados
            normalized_params = _normalize_params(call_info.get("args", ""))
            key = f"{call_info['module']}.{call_info['function']}({normalized_params})"

            if key not in pattern_counts:
                pattern_counts[key] = {
                    "module": call_info["module"],
                    "function": call_info["function"],
                    "params_tipo": normalized_params,
                    "count": 0,
                    "first_seen": None,
                    "last_seen": None,
                }

            pattern_counts[key]["count"] += 1

            # Extraer fecha de la línea
            date_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if date_match:
                timestamp = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M:%S")
                if pattern_counts[key]["first_seen"] is None:
                    pattern_counts[key]["first_seen"] = timestamp.isoformat()
                pattern_counts[key]["last_seen"] = timestamp.isoformat()

    return pattern_counts


def _load_candidates() -> list[dict]:
    """Carga candidatas existentes"""
    if not CANDIDATES_FILE.exists():
        return []

    try:
        with open(CANDIDATES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando candidatas: {e}")
        return []


def _save_candidates(candidates: list[dict]) -> bool:
    """Guarda candidatas a archivo"""
    try:
        CANDIDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error guardando candidatas: {e}")
        return False


def detect_repetitions() -> list[dict]:
    """
    Detecta tareas repetitivas en los logs
    Returns:
        Lista de candidatas a automatización
    """
    logger.info("Iniciando detección de repeticiones...")

    # Leer logs
    log_lines = _read_logs(days=TIME_WINDOW_DAYS)
    logger.info(f"Leídos {len(log_lines)} líneas de log de los últimos {TIME_WINDOW_DAYS} días")

    # Detectar patrones
    pattern_counts = _detect_repetitions(log_lines)
    logger.info(f"Encontrados {len(pattern_counts)} patrones únicos")

    # Filtrar por umbral
    candidates = []
    for key, pattern in pattern_counts.items():
        if pattern["count"] >= REPETITION_THRESHOLD:
            candidates.append(
                {
                    "accion": f"{pattern['module']}.{pattern['function']}",
                    "frecuencia": pattern["count"],
                    "parametros_tipo": pattern["params_tipo"],
                    "primera_vez": pattern["first_seen"],
                    "ultima_vez": pattern["last_seen"],
                    "candidata_n8n": True,
                }
            )

    logger.info(f"Candidatas a automatización: {len(candidates)}")

    # Cargar candidatas existentes y actualizar
    existing_candidates = _load_candidates()

    # Combinar sin duplicados
    existing_keys = {c["accion"] + c["parametros_tipo"] for c in existing_candidates}
    new_candidates = [
        c for c in candidates if c["accion"] + c["parametros_tipo"] not in existing_keys
    ]

    all_candidates = existing_candidates + new_candidates

    # Guardar
    if _save_candidates(all_candidates):
        logger.info(
            f"Guardadas {len(all_candidates)} candidatas totales ({len(new_candidates)} nuevas)"
        )
    else:
        logger.error("Error guardando candidatas")

    return candidates


def get_candidates() -> list[dict]:
    """Devuelve lista de candidatas a automatización"""
    return _load_candidates()


def check_candidate_exists(descripcion: str) -> dict | None:
    """
    Verifica si una tarea ya existe como candidata
    Args:
        descripcion: Descripción en lenguaje natural
    Returns:
        Candidata si existe, None en caso contrario
    """
    candidates = get_candidates()

    # Normalizar descripción para comparación
    descripcion_lower = descripcion.lower()

    for candidate in candidates:
        # Comparar con acción y parámetros
        accion_lower = candidate["accion"].lower()
        if accion_lower in descripcion_lower or descripcion_lower in accion_lower:
            return candidate

    return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Ejecutar detección
    candidates = detect_repetitions()

    # Mostrar resultados
    print("\n=== CANDIDATAS A AUTOMATIZACIÓN ===")
    for i, candidate in enumerate(candidates, 1):
        print(f"\n{i}. {candidate['accion']}")
        print(f"   Frecuencia: {candidate['frecuencia']} veces")
        print(f"   Parámetros: {candidate['parametros_tipo']}")
        print(f"   Primera vez: {candidate['primera_vez']}")
        print(f"   Última vez: {candidate['ultima_vez']}")

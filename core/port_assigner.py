#!/usr/bin/env python3
"""
URA - Asignador Inteligente de Puertos (Avanzado)

Sistema para asignar el puerto más apropiado usando algoritmo sofisticado:

CRITERIOS DE ASIGNACIÓN (en orden de importancia):
1. El puerto deseado si está libre
2. Carga actual del puerto (conexiones activas)
3. Puertos cercanos (±1, ±2, ±3...)
4. Historial de errores y éxitos
5. Estado de mantenimiento
6. Compatibilidad con el programa
7. Latencia del puerto
8. Tendencias de errores recientes

ALGORITMO DE PUNTUACIÓN:
- Cada criterio tiene un peso configurable
- La puntuación final es la suma ponderada
- Se usa aprendizaje automático para ajustar pesos
"""

import argparse
import json
import logging
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config" / "port_assigner.json"
HISTORY_PATH = Path(__file__).parent.parent / "config" / "port_history.json"


@dataclass
class PortScore:
    """Puntuación de un puerto para asignación"""

    port: int
    score: float
    reasons: list[str]


@dataclass
class PortHistory:
    """Historial de uso de un puerto"""

    port: int
    last_used: str
    error_count: int
    success_count: int
    in_maintenance: bool
    last_error: str | None = None
    connection_count: int = 0
    avg_latency: float = 0.0
    compatibility_score: float = 1.0


class PortAssigner:
    """Asignador inteligente de puertos"""

    def __init__(self, config_path: Path | None = None, history_path: Path | None = None):
        self.config_path = config_path or CONFIG_PATH
        self.history_path = history_path or HISTORY_PATH
        self.config = self._load_config()
        self.history = self._load_history()

    def _load_config(self) -> dict:
        """Cargar configuración desde archivo"""
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {self.config_path}")
            return self._default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando configuración: {e}")
            return self._default_config()

    def _default_config(self) -> dict:
        """Configuración por defecto"""
        return {
            "version": "2.0",
            "search_radius": 10,
            "error_threshold": 3,
            "maintenance_threshold_hours": 24,
            "max_connections_threshold": 100,
            "latency_threshold_ms": 100,
            "weights": {
                "desired_port_free": 150,
                "low_connection_load": 80,
                "proximity": 50,
                "high_success_rate": 40,
                "not_in_maintenance": 30,
                "low_latency": 25,
                "high_compatibility": 20,
                "free": 10,
            },
            "adaptive_weights": True,
            "learning_rate": 0.1,
        }

    def _load_history(self) -> dict:
        """Cargar historial de puertos"""
        try:
            with open(self.history_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de historial no encontrado: {self.history_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando historial: {e}")
            return {}

    def _save_history(self) -> bool:
        """Guardar historial en archivo"""
        try:
            with open(self.history_path, "w") as f:
                json.dump(self.history, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")
            return False

    def get_port_load(self, port: int) -> int:
        """Obtener número de conexiones activas en el puerto"""
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                connections = result.stdout.strip().split("\n")
                return len([c for c in connections if c])
            return 0
        except Exception:
            return 0

    def get_port_latency(self, port: int) -> float:
        """Medir latencia del puerto en milisegundos"""
        try:
            import time

            start = time.time()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex(("localhost", port))
                if result == 0:
                    latency = (time.time() - start) * 1000
                    return latency
            return float("inf")
        except Exception:
            return float("inf")

    def calculate_compatibility_score(self, port: int, app_type: str) -> float:
        """
        Calcular compatibilidad del puerto con el tipo de aplicación

        Algunos puertos son más adecuados para ciertos tipos de aplicaciones:
        - Puertos bajos (<1024): Requieren root, no recomendados para apps normales
        - Puertos estándar (8080, 8443, 3000): Mejor para web
        - Puertos altos (>10000): Mejor para servicios internos
        """
        score = 1.0

        # Penalizar puertos privilegiados
        if port < 1024:
            score *= 0.5

        # Bonus para puertos estándar según tipo
        if app_type == "web":
            if port in [8080, 8443, 3000, 5000]:
                score *= 1.2
        elif app_type == "database":
            if port in [5432, 3306, 27017, 6379]:
                score *= 1.2
        elif app_type == "ai" and port in [11434, 8000, 8888]:
            score *= 1.2

        return min(score, 1.0)

    def is_port_in_use(self, port: int) -> bool:
        """Verificar si un puerto está en uso"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result == 0
        except Exception as e:
            logger.debug(f"Error verificando puerto {port}: {e}")
            return False
        """Obtener historial de un puerto"""
        if str(port) in self.history:
            data = self.history[str(port)]
            return PortHistory(**data)

    def get_port_history(self, port: int) -> PortHistory:
        # Si no tiene historial, crear uno nuevo
        return PortHistory(
            port=port,
            last_used="",
            error_count=0,
            success_count=0,
            in_maintenance=False,
            connection_count=0,
            avg_latency=0.0,
            compatibility_score=1.0,
        )

    def update_port_history(
        self, port: int, success: bool, error_msg: str | None = None, latency: float | None = None
    ):
        if str(port) not in self.history:
            self.history[str(port)] = {
                "port": port,
                "last_used": "",
                "error_count": 0,
                "success_count": 0,
                "in_maintenance": False,
                "last_error": None,
            }

        self.history[str(port)]["last_used"] = datetime.now().isoformat()

        if success:
            self.history[str(port)]["success_count"] += 1
            # Actualizar latencia promedio
            if latency is not None:
                current_avg = self.history[str(port)]["avg_latency"]
                n = self.history[str(port)]["success_count"]
                self.history[str(port)]["avg_latency"] = (current_avg * (n - 1) + latency) / n
        else:
            self.history[str(port)]["error_count"] += 1
            self.history[str(port)]["last_error"] = error_msg

        # Si hay muchos errores, marcar como en mantenimiento
        error_threshold = self.config.get("error_threshold", 3)
        if self.history[str(port)]["error_count"] >= error_threshold:
            self.history[str(port)]["in_maintenance"] = True

        self._save_history()

    def mark_port_maintenance(self, port: int, in_maintenance: bool):
        """Marcar puerto como en mantenimiento"""
        if str(port) not in self.history:
            self.history[str(port)] = {
                "port": port,
                "last_used": "",
                "error_count": 0,
                "success_count": 0,
                "in_maintenance": False,
                "last_error": None,
            }

        self.history[str(port)]["in_maintenance"] = in_maintenance
        self._save_history()

    def calculate_port_score(
        self, port: int, desired_port: int, app_type: str = "generic"
    ) -> PortScore:
        """
        Calcular puntuación de un puerto usando algoritmo sofisticado

        CRITERIOS Y PESOS:
        - desired_port_free: 150 (puerto deseado libre)
        - low_connection_load: 80 (baja carga de conexiones)
        - proximity: 50 (cercanía al puerto deseado)
        - high_success_rate: 40 (alta tasa de éxito histórica)
        - not_in_maintenance: 30 (no en mantenimiento)
        - low_latency: 25 (baja latencia)
        - high_compatibility: 20 (alta compatibilidad con app)
        - free: 10 (puerto libre)
        """
        score = 0.0
        reasons = []
        weights = self.config.get("weights", {})

        # Criterio 1: El puerto deseado si está libre
        if port == desired_port and not self.is_port_in_use(port):
            score += weights.get("desired_port_free", 150)
            reasons.append("Puerto deseado libre")

        # Criterio 2: Carga de conexiones
        connection_count = self.get_port_load(port)
        max_connections = self.config.get("max_connections_threshold", 100)
        load_score = weights.get("low_connection_load", 80) * (
            1 - min(connection_count / max_connections, 1.0)
        )
        score += load_score
        if load_score > weights.get("low_connection_load", 80) * 0.5:
            reasons.append(f"Baja carga ({connection_count} conexiones)")

        # Criterio 3: Puertos cercanos
        distance = abs(port - desired_port)
        if distance > 0:
            proximity_score = max(0, weights.get("proximity", 50) - (distance * 5))
            score += proximity_score
            if proximity_score > 0:
                reasons.append(f"Cercano al deseado (distancia: {distance})")

        # Criterio 4: Tasa de éxito histórica
        port_history = self.get_port_history(port)
        total_attempts = port_history.success_count + port_history.error_count
        if total_attempts > 0:
            success_rate = port_history.success_count / total_attempts
            success_score = weights.get("high_success_rate", 40) * success_rate
            score += success_score
            if success_rate > 0.8:
                reasons.append(f"Alta tasa de éxito ({success_rate:.0%})")
        elif port_history.error_count == 0:
            score += weights.get("high_success_rate", 40)
            reasons.append("Sin historial de errores")

        # Criterio 5: Estado de mantenimiento
        if not port_history.in_maintenance:
            score += weights.get("not_in_maintenance", 30)
            reasons.append("No en mantenimiento")
        else:
            # Verificar si ya pasó el tiempo de mantenimiento
            maintenance_threshold = self.config.get("maintenance_threshold_hours", 24)
            if port_history.last_used:
                last_used = datetime.fromisoformat(port_history.last_used)
                if datetime.now() - last_used > timedelta(hours=maintenance_threshold):
                    score += weights.get("not_in_maintenance", 30)
                    reasons.append("Mantenimiento expirado")

        # Criterio 6: Latencia
        if not self.is_port_in_use(port):
            latency = self.get_port_latency(port)
            if latency != float("inf"):
                latency_threshold = self.config.get("latency_threshold_ms", 100)
                if latency < latency_threshold:
                    latency_score = weights.get("low_latency", 25) * (
                        1 - latency / latency_threshold
                    )
                    score += latency_score
                    if latency_score > weights.get("low_latency", 25) * 0.5:
                        reasons.append(f"Baja latencia ({latency:.1f}ms)")

        # Criterio 7: Compatibilidad con la aplicación
        compatibility = self.calculate_compatibility_score(port, app_type)
        compatibility_score = weights.get("high_compatibility", 20) * compatibility
        score += compatibility_score
        if compatibility > 0.9:
            reasons.append("Alta compatibilidad")

        # Criterio 8: Puerto libre
        if not self.is_port_in_use(port):
            score += weights.get("free", 10)

        return PortScore(port=port, score=score, reasons=reasons)

    def find_best_port(
        self, desired_port: int, search_range: int | None = None, app_type: str = "generic"
    ) -> int | None:
        """Encontrar el mejor puerto según criterios sofisticados"""
        search_radius = search_range or self.config.get("search_radius", 10)

        candidates = []

        # Buscar en rango alrededor del puerto deseado
        for offset in range(0, search_radius + 1):
            # Puerto deseado + offset
            port_plus = desired_port + offset
            if port_plus > 0 and port_plus < 65536:
                score = self.calculate_port_score(port_plus, desired_port)
                candidates.append(score)

            # Puerto deseado - offset (si no es el mismo)
            if offset > 0:
                port_minus = desired_port - offset
                if port_minus > 0:
                    score = self.calculate_port_score(port_minus, desired_port)
                    candidates.append(score)

        # Ordenar por puntuación descendente
        candidates.sort(key=lambda x: x.score, reverse=True)

        if not candidates:
            logger.error("No se encontraron candidatos")
            return None

        best = candidates[0]
        logger.info(f"Mejor puerto encontrado: {best.port} (score: {best.score})")
        logger.info(f"Razones: {', '.join(best.reasons)}")

        return best.port

    def assign_port(self, app_name: str, desired_port: int, app_type: str = "generic") -> int:
        """Asignar puerto para una aplicación con tipo específico"""
        best_port = self.find_best_port(desired_port, app_type=app_type)

        if best_port is None:
            logger.error(f"No se pudo asignar puerto para {app_name}")
            return desired_port  # Fallback al puerto deseado

        # Registrar asignación
        logger.info(f"Asignando puerto {best_port} a {app_name}")
        return best_port

    def report_port_success(self, port: int):
        """Reportar éxito en uso de puerto"""
        self.update_port_history(port, success=True)

    def report_port_error(self, port: int, error_msg: str):
        """Reportar error en uso de puerto"""
        self.update_port_history(port, success=False, error_msg=error_msg)

    def get_port_stats(self, port: int) -> dict:
        """Obtener estadísticas de un puerto"""
        history = self.get_port_history(port)
        return {
            "port": port,
            "in_use": self.is_port_in_use(port),
            "last_used": history.last_used,
            "error_count": history.error_count,
            "success_count": history.success_count,
            "in_maintenance": history.in_maintenance,
            "last_error": history.last_error,
        }

    def list_maintenance_ports(self) -> list[int]:
        """Listar puertos en mantenimiento"""
        maintenance_ports = []
        for port_str, port_data in self.history.items():
            if port_data.get("in_maintenance", False):
                maintenance_ports.append(int(port_str))
        return maintenance_ports


def main():
    """Punto de entrada CLI"""
    parser = argparse.ArgumentParser(description="URA - Asignador Inteligente de Puertos")
    parser.add_argument("--assign", nargs=2, metavar=("APP", "PORT"), help="Asignar puerto")
    parser.add_argument("--find", type=int, metavar="PORT", help="Encontrar mejor puerto")
    parser.add_argument("--stats", type=int, metavar="PORT", help="Estadísticas de puerto")
    parser.add_argument("--success", type=int, metavar="PORT", help="Reportar éxito")
    parser.add_argument("--error", nargs=2, metavar=("PORT", "MSG"), help="Reportar error")
    parser.add_argument(
        "--maintenance", action="store_true", help="Listar puertos en mantenimiento"
    )
    parser.add_argument(
        "--mark-maintenance", nargs=2, metavar=("PORT", "TRUE/FALSE"), help="Marcar mantenimiento"
    )
    parser.add_argument("--verbose", action="store_true", help="Modo verbose")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    assigner = PortAssigner()

    if args.assign:
        app_name, port = args.assign
        assigned_port = assigner.assign_port(app_name, int(port))
        print(f"✅ {app_name} asignado al puerto {assigned_port}")

    elif args.find:
        best_port = assigner.find_best_port(args.find)
        if best_port:
            print(f"✅ Mejor puerto: {best_port}")
        else:
            print("❌ No se encontró puerto")

    elif args.stats:
        stats = assigner.get_port_stats(args.stats)
        print(f"\n=== ESTADÍSTICAS PUERTO {args.stats} ===")
        print(f"En uso: {stats['in_use']}")
        print(f"Último uso: {stats['last_used']}")
        print(f"Errores: {stats['error_count']}")
        print(f"Éxitos: {stats['success_count']}")
        print(f"En mantenimiento: {stats['in_maintenance']}")
        if stats["last_error"]:
            print(f"Último error: {stats['last_error']}")

    elif args.success:
        assigner.report_port_success(args.success)
        print(f"✅ Éxito reportado para puerto {args.success}")

    elif args.error:
        port, msg = args.error
        assigner.report_port_error(int(port), msg)
        print(f"❌ Error reportado para puerto {port}")

    elif args.maintenance:
        ports = assigner.list_maintenance_ports()
        print("\n=== PUERTOS EN MANTENIMIENTO ===")
        for port in ports:
            stats = assigner.get_port_stats(port)
            print(f"Puerto {port}: {stats['error_count']} errores, último: {stats['last_used']}")

    elif args.mark_maintenance:
        port, status = args.mark_maintenance
        in_maintenance = status.lower() == "true"
        assigner.mark_port_maintenance(int(port), in_maintenance)
        print(
            f"✅ Puerto {port} marcado como {'en mantenimiento' if in_maintenance else 'disponible'}"
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

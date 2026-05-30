import logging

#!/usr/bin/env python3
"""
Sistema de logging unificado para agentes de URA
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import json


class LogHandler(ABC):
    """Interfaz para handlers de log."""

    @abstractmethod
    def handle(self, log_entry: dict[str, any]) -> None:
        """Manejar entrada de log."""


class FileLogHandler(LogHandler):
    """Handler para logs en archivo."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def handle(self, log_entry: dict[str, any]) -> None:
        """Escribir log en archivo."""
        log_file = self.log_dir / f"ura_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_file, "a") as f:
            f.write(f"{log_entry['timestamp']} - {log_entry['level']} - {log_entry['message']}\n")


class ConsoleLogHandler(LogHandler):
    """Handler para logs en consola."""

    def handle(self, log_entry: dict[str, any]) -> None:
        """Escribir log en consola."""
        print(f"{log_entry['timestamp']} - {log_entry['level']} - {log_entry['message']}")


class UnifiedLogger:
    """Logger unificado para todos los agentes."""

    def __init__(self, log_dir: Path | None = None, handlers: list[LogHandler] | None = None):
        if log_dir is None:
            log_dir = Path.home() / ".ura" / "logs"

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Configurar logger principal
        self.logger = logging.getLogger("URA")
        self.logger.setLevel(logging.DEBUG)

        # Configurar handlers
        if handlers is None:
            handlers = [FileLogHandler(log_dir), ConsoleLogHandler()]

        self.handlers = handlers

        # Historial de interacciones
        self._interaction_history: list[dict[str, any]] = []
        self._degradation_history: list[dict[str, any]] = []
        self._max_history: int = 1000

    def log_agent_interaction(
        self,
        agent: str,
        intent: str,
        texto: str,
        response: str,
        confidence: float,
        metadata: dict[str, any] | None = None,
    ) -> None:
        """
        Registrar interacción con agente.

        Args:
            agent: Agente utilizado
            intent: Intención detectada
            texto: Texto de la consulta
            response: Respuesta del agente
            confidence: Confianza del routing
            metadata: Metadata adicional
        """
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "intent": intent,
            "texto": texto,
            "response": response[:200],  # Truncar respuesta larga
            "confidence": confidence,
            "metadata": metadata or {},
        }

        self._add_to_history(interaction, self._interaction_history)
        self._log("INFO", f"Agent: {agent}, Intent: {intent}, Confidence: {confidence:.2f}")

    def log_degradation(self, original_agent: str, fallback_agent: str, reason: str) -> None:
        """
        Registrar degradación de agente.

        Args:
            original_agent: Agente original solicitado
            fallback_agent: Agente alternativo usado
            reason: Razón de la degradación
        """
        degradation = {
            "timestamp": datetime.now().isoformat(),
            "original_agent": original_agent,
            "fallback_agent": fallback_agent,
            "reason": reason,
        }

        self._add_to_history(degradation, self._degradation_history)
        self._log("WARNING", f"Degradation: {original_agent} -> {fallback_agent}, Reason: {reason}")

    def _add_to_history(self, entry: dict[str, any], history: list[dict[str, any]]) -> None:
        """Añadir entrada al historial con límite."""
        history.append(entry)
        if len(history) > self._max_history:
            history.pop(0)

    def _log(self, level: str, message: str) -> None:
        """Log usando handlers configurados."""
        log_entry = {"timestamp": datetime.now().isoformat(), "level": level, "message": message}

        for handler in self.handlers:
            handler.handle(log_entry)

    def get_agent_stats(self, agent: str) -> dict[str, any]:
        """
        Obtener estadísticas de uso de un agente.

        Args:
            agent: Agente a consultar

        Returns:
            Dict con estadísticas
        """
        interactions = [i for i in self._interaction_history if i["agent"] == agent]

        return {
            "agent": agent,
            "total_interactions": len(interactions),
            "avg_confidence": (
                sum(i["confidence"] for i in interactions) / len(interactions)
                if interactions
                else 0
            ),
            "first_interaction": interactions[0]["timestamp"] if interactions else None,
            "last_interaction": interactions[-1]["timestamp"] if interactions else None,
        }

    def get_degradation_stats(self) -> dict[str, any]:
        """Obtener estadísticas de degradaciones."""
        return {
            "total_degradations": len(self._degradation_history),
            "degradations_by_agent": self._count_degradations_by_agent(),
            "recent_degradations": (
                self._degradation_history[-10:] if self._degradation_history else []
            ),
        }

    def _count_degradations_by_agent(self) -> dict[str, int]:
        """Contar degradaciones por agente original."""
        counts = {}
        for d in self._degradation_history:
            agent = d["original_agent"]
            counts[agent] = counts.get(agent, 0) + 1
        return counts

    def export_history(self, output_file: Path | None = None) -> Path:
        """
        Exportar historial a JSON.

        Args:
            output_file: Archivo de salida (se genera uno si no se proporciona)

        Returns:
            Path del archivo exportado
        """
        if output_file is None:
            output_file = self.log_dir / f"history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "interactions": self._interaction_history,
            "degradations": self._degradation_history,
            "exported_at": datetime.now().isoformat(),
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        self._log("INFO", f"History exported to {output_file}")
        return output_file

    def clear_history(self) -> None:
        """Limpiar historial."""
        self._interaction_history.clear()
        self._degradation_history.clear()
        self._log("INFO", "History cleared")

    def add_handler(self, handler: LogHandler) -> None:
        """Añadir handler personalizado."""
        self.handlers.append(handler)

    def set_max_history(self, max_history: int) -> None:
        """Establecer tamaño máximo del historial."""
        self._max_history = max_history


# Singleton global
_unified_logger: UnifiedLogger | None = None


def get_unified_logger() -> UnifiedLogger:
    """Obtener instancia singleton del logger unificado."""
    global _unified_logger
    if _unified_logger is None:
        _unified_logger = UnifiedLogger()
    return _unified_logger


def reset_unified_logger() -> None:
    """Resetear logger unificado (crear nueva instancia)."""
    global _unified_logger
    _unified_logger = UnifiedLogger()

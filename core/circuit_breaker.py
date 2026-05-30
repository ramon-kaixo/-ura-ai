#!/usr/bin/env python3
"""
core/circuit_breaker.py - Circuit Breaker para agentes
Implementa el patrón Circuit Breaker para prevenir fallos en cascada
"""

import json
import logging
import time
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("circuit_breaker", log_dir="./logs")

# Archivo de logs del circuit breaker
CIRCUIT_BREAKER_LOG = Path(__file__).parent.parent / "logs" / "circuit_breaker.jsonl"


# Estados del circuit breaker
class CircuitState(Enum):
    """Estados del Circuit Breaker"""

    CLOSED = "cerrado"  # Normal
    OPEN = "abierto"  # Bloqueado
    SEMI_OPEN = "semi_abierto"  # Permite un intento


class CircuitBreaker:
    """
    Circuit Breaker para prevenir fallos en cascada
    - 3 fallos seguidos → abierto (bloqueado)
    - 10 minutos en estado abierto → semi_abierto (permite un intento)
    - Si el intento funciona → vuelve a cerrado (normal)
    """

    def __init__(self, agent_name: str, failure_threshold: int = 3, timeout_seconds: int = 600):
        """
        Inicializar Circuit Breaker

        Args:
            agent_name: Nombre del agente
            failure_threshold: Número de fallos para abrir el circuito
            timeout_seconds: Tiempo en segundos para pasar de abierto a semi_abierto
        """
        self.agent_name = agent_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.last_state_change: float | None = None

        logger.info(f"CircuitBreaker inicializado para {agent_name}")

    def call(self, func, *args, **kwargs):
        """
        Ejecuta una función con protección del Circuit Breaker

        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre

        Returns:
            Resultado de la función o None si el circuito está abierto
        """
        # Si el circuito está abierto, verificar si debe pasar a semi_abierto
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.SEMI_OPEN
                self._log_state_change(
                    "abierto", "semi_abierto", "Timeout alcanzado, permitiendo un intento"
                )
            else:
                logger.warning(f"Circuito abierto para {self.agent_name} - bloqueando llamada")
                return None

        # Ejecutar función
        try:
            result = func(*args, **kwargs)

            # Si tuvo éxito, cerrar el circuito
            if self.state in [CircuitState.SEMI_OPEN, CircuitState.OPEN]:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self._log_state_change(str(self.state), "cerrado", "Éxito en llamada")

            return result

        except Exception as e:
            logger.error(f"Error en {self.agent_name}: {e}")
            self._on_failure()
            raise

    def _on_failure(self) -> None:
        """Maneja un fallo"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        logger.warning(f"Fallo #{self.failure_count} para {self.agent_name}")

        # Si alcanza el umbral, abrir el circuito
        if self.failure_count >= self.failure_threshold and self.state == CircuitState.CLOSED:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            self._log_state_change(
                "cerrado", "abierto", f"{self.failure_count} fallos consecutivos"
            )

            # Intentar auto-reparación antes de abrir
            self._attempt_auto_repair()

            # Avisar por Telegram
            self._send_telegram_alert()

    def _should_attempt_reset(self) -> bool:
        """Verifica si debe intentar reiniciar el circuito"""
        if self.last_state_change is None:
            return False

        elapsed = time.time() - self.last_state_change
        return elapsed >= self.timeout_seconds

    def _attempt_auto_repair(self) -> bool:
        """Intenta auto-reparación antes de abrir el circuito"""
        logger.info(f"Intentando auto-reparación para {self.agent_name}")

        try:
            from core.error_auto_repair import ErrorAutoRepair

            repair = ErrorAutoRepair()

            # Intentar reparar
            repaired = repair.attempt_repair(self.agent_name, self.failure_count)

            if repaired:
                logger.info(f"Auto-reparación exitosa para {self.agent_name}")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self._log_state_change("abierto", "cerrado", "Auto-reparación exitosa")
                return True
            else:
                logger.warning(f"Auto-reparación fallida para {self.agent_name}")
                return False

        except Exception as e:
            logger.error(f"Error en auto-reparación: {e}")
            return False

    def _send_telegram_alert(self) -> None:
        """Envía alerta por Telegram"""
        logger.info(f"Enviando alerta Telegram para {self.agent_name}")

        try:
            from core.messaging_tools import send_telegram_message

            message = f"""
⚠️ CIRCUITO ABIERTO ⚠️

Agente: {self.agent_name}
Fallos consecutivos: {self.failure_count}
Estado: {self.state.value}
Hora: {datetime.now(tz=UTC).isoformat()}

El agente ha sido bloqueado por fallos consecutivos.
Se intentará auto-reparación. Si falla, se requiere intervención manual.
            """

            send_telegram_message(message)
            logger.info("Alerta Telegram enviada")

        except Exception as e:
            logger.error(f"Error enviando alerta Telegram: {e}")

    def _log_state_change(self, from_state: str, to_state: str, reason: str) -> None:
        """Registra cambio de estado en el log"""
        log_entry = {
            "agent_name": self.agent_name,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "failure_count": self.failure_count,
        }

        try:
            CIRCUIT_BREAKER_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(CIRCUIT_BREAKER_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Error escribiendo log de circuit breaker: {e}")

    def get_state(self) -> CircuitState:
        """Devuelve el estado actual"""
        return self.state

    def reset(self) -> None:
        """Resetea el circuit breaker a estado cerrado"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_state_change = None
        logger.info(f"CircuitBreaker reseteado para {self.agent_name}")


# Registro global de circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(agent_name: str) -> CircuitBreaker:
    """
    Obtiene o crea un Circuit Breaker para un agente

    Args:
        agent_name: Nombre del agente

    Returns:
        CircuitBreaker para el agente
    """
    if agent_name not in _circuit_breakers:
        _circuit_breakers[agent_name] = CircuitBreaker(agent_name)

    return _circuit_breakers[agent_name]


def circuit_breaker_decorator(agent_name: str):
    """
    Decorador para aplicar Circuit Breaker a una función

    Args:
        agent_name: Nombre del agente
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            cb = get_circuit_breaker(agent_name)
            return cb.call(func, *args, **kwargs)

        return wrapper

    return decorator


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Prueba
    cb = CircuitBreaker("test_agent", failure_threshold=2, timeout_seconds=10)

    def test_function():
        print("Ejecutando función de prueba")
        return "Éxito"

    def failing_function():
        print("Ejecutando función que falla")
        raise Exception("Error simulado")

    # Primera llamada exitosa
    result = cb.call(test_function)
    print(f"Resultado: {result}")
    print(f"Estado: {cb.get_state().value}")

    # Dos fallos
    try:
        cb.call(failing_function)
    except Exception as e:
        logger.warning(f"Error silencioso en circuit_breaker.test_fallback: {e}")
        # fallback: continuar

    try:
        cb.call(failing_function)
    except Exception as e:
        logger.warning(f"Error silencioso en circuit_breaker.test_fallback2: {e}")
        # fallback: continuar

    print(f"Estado tras fallos: {cb.get_state().value}")
    print(f"Conteo de fallos: {cb.failure_count}")

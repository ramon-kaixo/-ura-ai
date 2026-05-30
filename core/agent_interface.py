#!/usr/bin/env python3
"""
Interfaz común para agentes de URA
Define la estructura base que todos los agentes deben implementar
"""

from abc import ABC, abstractmethod
from typing import Any


class AgentInterface(ABC):
    """Interfaz base para todos los agentes de URA."""

    @abstractmethod
    def procesar(self, texto: str) -> str:
        """
        Procesar texto y generar respuesta.

        Args:
            texto: Texto a procesar

        Returns:
            Respuesta generada
        """

    def ejecutar(self, texto: str) -> str:
        """
        Ejecutar acción basada en el texto.

        Args:
            texto: Texto con instrucción

        Returns:
            Resultado de la ejecución
        """
        return self.procesar(texto)

    def consultar(self, consulta: str) -> str:
        """
        Consultar información.

        Args:
            consulta: Consulta a realizar

        Returns:
            Respuesta de la consulta
        """
        return self.procesar(consulta)

    def responder(self, pregunta: str) -> str:
        """
        Responder pregunta.

        Args:
            pregunta: Pregunta a responder

        Returns:
            Respuesta
        """
        return self.procesar(pregunta)

    def get_info(self) -> dict[str, Any]:
        """
        Obtener información del agente.

        Returns:
            Dict con información del agente
        """
        return {
            "name": self.__class__.__name__,
            "module": self.__class__.__module__,
            "doc": self.__class__.__doc__,
        }

    def validate_input(self, texto: str) -> tuple[bool, str | None]:
        """
        Validar entrada antes de procesar.

        Args:
            texto: Texto a validar

        Returns:
            Tuple (is_valid, error_message)
        """
        if not texto or not isinstance(texto, str):
            return False, "Texto inválido: debe ser una cadena no vacía"

        if len(texto.strip()) == 0:
            return False, "Texto inválido: está vacío"

        return True, None

    def get_capabilities(self) -> dict[str, bool]:
        """
        Obtener capacidades del agente.

        Returns:
            Dict con capacidades disponibles
        """
        return {
            "procesar": hasattr(self, "procesar"),
            "ejecutar": hasattr(self, "ejecutar"),
            "consultar": hasattr(self, "consultar"),
            "responder": hasattr(self, "responder"),
            "validate_input": hasattr(self, "validate_input"),
        }

    def get_version(self) -> str:
        """
        Obtener versión del agente.

        Returns:
            Versión del agente
        """
        return "1.0.0"


class BaseAgent(AgentInterface):
    """Clase base para agentes con funcionalidad común."""

    def __init__(self):
        self._initialized = False
        self._config: dict[str, Any] = {}

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """
        Inicializar agente con configuración.

        Args:
            config: Configuración del agente
        """
        if config:
            self._config.update(config)
        self._initialized = True

    def is_initialized(self) -> bool:
        """Verificar si el agente está inicializado."""
        return self._initialized

    def get_config(self) -> dict[str, Any]:
        """Obtener configuración del agente."""
        return self._config.copy()

    def set_config(self, key: str, value: Any) -> None:
        """
        Establecer valor de configuración.

        Args:
            key: Clave de configuración
            value: Valor
        """
        self._config[key] = value

    def procesar(self, texto: str) -> str:
        """
        Procesar texto y generar respuesta (implementación base).

        Args:
            texto: Texto a procesar

        Returns:
            Respuesta generada
        """
        is_valid, error = self.validate_input(texto)
        if not is_valid:
            return f"Error: {error}"

        return f"{self.__class__.__name__} procesando: {texto}"

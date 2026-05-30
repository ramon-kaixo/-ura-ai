#!/usr/bin/env python3
"""
Validación de parámetros para agentes de URA
"""

from typing import Any
from dataclasses import dataclass
from enum import Enum


class ValidationType(Enum):
    """Tipos de validación."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"


@dataclass
class Parameter:
    """Definición de parámetro."""

    name: str
    type: ValidationType
    required: bool = True
    default: Any = None
    min_length: int | None = None
    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[Any] | None = None
    description: str = ""


class AgentValidator:
    """Validador de parámetros para agentes."""

    def __init__(self, parameters: list[Parameter]):
        self.parameters = {p.name: p for p in parameters}

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validar parámetros.

        Args:
            data: Diccionario con los datos a validar

        Returns:
            Tuple (is_valid, error_messages)
        """
        errors = []

        for param_name, param in self.parameters.items():
            # Verificar parámetros requeridos
            if param.required and param_name not in data:
                errors.append(f"Parámetro requerido: {param_name}")
                continue

            # Si no es requerido y no está presente, usar default
            if not param.required and param_name not in data:
                continue

            value = data.get(param_name)

            # Validar tipo
            if not self._validate_type(value, param.type):
                errors.append(
                    f"Tipo incorrecto para {param_name}: esperado {param.type.value}, obtenido {type(value).__name__}"
                )
                continue

            # Validar longitud
            if param.min_length and len(str(value)) < param.min_length:
                errors.append(f"{param_name}: longitud mínima {param.min_length}")

            if param.max_length and len(str(value)) > param.max_length:
                errors.append(f"{param_name}: longitud máxima {param.max_length}")

            # Validar rango numérico
            if (
                param.min_value is not None
                and isinstance(value, (int, float))
                and value < param.min_value
            ):
                errors.append(f"{param_name}: valor mínimo {param.min_value}")

            if (
                param.max_value is not None
                and isinstance(value, (int, float))
                and value > param.max_value
            ):
                errors.append(f"{param_name}: valor máximo {param.max_value}")

            # Validar valores permitidos
            if param.allowed_values and value not in param.allowed_values:
                errors.append(
                    f"{param_name}: valor no permitido. Valores permitidos: {param.allowed_values}"
                )

            # Validaciones específicas por tipo
            if param.type == ValidationType.EMAIL:
                if not self._validate_email(value):
                    errors.append(f"{param_name}: formato de email inválido")

            elif param.type == ValidationType.URL:
                if not self._validate_url(value):
                    errors.append(f"{param_name}: formato de URL inválido")

            elif param.type == ValidationType.PHONE:
                if not self._validate_phone(value):
                    errors.append(f"{param_name}: formato de teléfono inválido")

        return len(errors) == 0, errors

    def _validate_type(self, value: Any, expected_type: ValidationType) -> bool:
        """Validar tipo de valor."""
        type_map = {
            ValidationType.STRING: str,
            ValidationType.INTEGER: int,
            ValidationType.FLOAT: (int, float),
            ValidationType.BOOLEAN: bool,
            ValidationType.LIST: list,
            ValidationType.DICT: dict,
        }

        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])

        # Para EMAIL, URL, PHONE aceptamos strings
        if expected_type in [ValidationType.EMAIL, ValidationType.URL, ValidationType.PHONE]:
            return isinstance(value, str)

        return True

    def _validate_email(self, email: str) -> bool:
        """Validar formato de email."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    def _validate_url(self, url: str) -> bool:
        """Validar formato de URL."""
        import re

        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return re.match(pattern, url) is not None

    def _validate_phone(self, phone: str) -> bool:
        """Validar formato de teléfono."""
        import re

        # Acepta formatos: +34 123 456 789, 123-456-789, 123456789
        pattern = r"^[\d\-\+\s]+$"
        return re.match(pattern, phone) is not None and len(re.sub(r"[\-\+\s]", "", phone)) >= 9

    def get_parameters_info(self) -> dict[str, dict[str, Any]]:
        """Obtener información de los parámetros."""
        return {
            name: {
                "type": param.type.value,
                "required": param.required,
                "default": param.default,
                "description": param.description,
                "min_length": param.min_length,
                "max_length": param.max_length,
                "min_value": param.min_value,
                "max_value": param.max_value,
                "allowed_values": param.allowed_values,
            }
            for name, param in self.parameters.items()
        }

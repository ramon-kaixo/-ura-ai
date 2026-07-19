"""Compatibilidad entre versiones de Python.

Knowledge Engine soporta Python 3.10+.
Este módulo proporciona polyfills para features que no existen en versiones anteriores.
"""

from __future__ import annotations


# StrEnum está disponible desde Python 3.11.
# En 3.10, usamos un reemplazo basado en Enum + str mixin.

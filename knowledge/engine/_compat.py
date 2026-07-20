"""Compatibilidad entre versiones de Python.

Knowledge Engine soporta Python 3.10+.
Este módulo proporciona polyfills para features que no existen en versiones anteriores.
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass

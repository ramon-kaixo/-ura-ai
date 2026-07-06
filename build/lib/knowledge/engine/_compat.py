"""Compatibilidad entre versiones de Python.

Knowledge Engine soporta Python 3.10+.
Este módulo proporciona polyfills para features que no existen en versiones anteriores.
"""

from __future__ import annotations

import sys

# StrEnum está disponible desde Python 3.11.
# En 3.10, usamos un reemplazo basado en Enum + str mixin.
if sys.version_info >= (3, 11):
    from enum import StrEnum as StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """StrEnum polyfill para Python 3.10."""
        pass

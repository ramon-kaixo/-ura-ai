"""Compatibilidad entre versiones de Python.

Knowledge Engine soporta Python 3.10+.
Este módulo proporciona polyfills para features que no existen en versiones anteriores.
"""

from __future__ import annotations

from enum import StrEnum as StrEnum  # noqa: F401 — re-export for Python 3.11+


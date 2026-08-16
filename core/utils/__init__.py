"""core.utils — Utilidades de saneamiento y anonimización.

Fachada: la implementación canónica vive en motor/core/utils/anonymizer.py.
"""

from motor.core.utils.anonymizer import sanitize_text

__all__ = ["sanitize_text"]

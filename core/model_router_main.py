"""Model Router Enhanced — archivo de compatibilidad hacia atrás.

Reexporta todo desde core.model_router package.
Mantenido temporalmente para no romper imports existentes.
"""

from core.model_router import *  # noqa: F403
from core.model_router.cli import main

if __name__ == "__main__":
    main()

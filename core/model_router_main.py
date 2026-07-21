"""Model Router Enhanced — archivo de compatibilidad hacia atrás.

Reexporta todo desde core.model_router package.
Mantenido temporalmente para no romper imports existentes.
"""

from core.model_router import *  # noqa: F401, F403
from core.model_router.cli import main  # noqa: F401

if __name__ == "__main__":
    main()

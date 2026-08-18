"""path_setup.py — Bootstrap centralizado de sys.path para todo el proyecto.

Uso:

Elimina la repetición de sys.path.insert(0, ...) en ~25 archivos.
"""

import sys
from pathlib import Path

_PROJECT_ROOT: Path | None = None


def setup_path() -> None:
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return

    # Detecta la raíz del proyecto: este archivo está en core/path_setup.py
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent

    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))


def get_project_root() -> Path:
    if _PROJECT_ROOT is None:
        setup_path()
    return _PROJECT_ROOT  # type: ignore[return-value]

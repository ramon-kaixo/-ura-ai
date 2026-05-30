import os
import pytest

if not os.getenv("GX10_AVAILABLE"):
    pytest.skip(
        "GX10 no disponible. Usa export GX10_AVAILABLE=true para activar.", allow_module_level=True
    )

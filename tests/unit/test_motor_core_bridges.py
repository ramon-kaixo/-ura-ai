"""Tests de los puentes temporales core -> motor (TASK-20260825-005).

Los shims re-exportan la implementacion viva en core/model_router/.
Las pruebas de identidad corren en SUBPROCESO para ser inmunes al orden
aleatorio de la suite (tests que recargan/stubean modulos no pueden
contaminarlas).
"""

from __future__ import annotations

import subprocess
import sys

BRIDGE_IDENTITY_SNIPPET = """
from core.model_router.metrics import metrics as src
from motor.core.llm.metrics import metrics
assert metrics is src, "puente llm.metrics no es el singleton de core"
from core.model_router.router import get_urls as gu_src
from motor.core.model_router.router import CONN_TIMEOUT, READ_TIMEOUT, get_urls
assert get_urls is gu_src, "puente router.get_urls no es la funcion de core"
from core.model_router import router as r_src
assert CONN_TIMEOUT == r_src.CONN_TIMEOUT, "CONN_TIMEOUT divergente"
assert READ_TIMEOUT == r_src.READ_TIMEOUT, "READ_TIMEOUT divergente"
from core.model_router.model_selection import _record_success as rs_src
from motor.core.model_router.model_selection import _record_success
assert _record_success is rs_src, "puente model_selection roto"
print("PUENTES-OK")
"""


def test_bridges_identidad_en_subproceso() -> None:
    """Identidad de los 3 puentes, aislada del proceso de tests."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", BRIDGE_IDENTITY_SNIPPET],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PUENTES-OK" in result.stdout


def test_bridge_router_timeout_values() -> None:
    """Constantes positivas y lectura > conexion."""
    from motor.core.model_router.router import CONN_TIMEOUT, READ_TIMEOUT

    assert CONN_TIMEOUT > 0
    assert READ_TIMEOUT >= CONN_TIMEOUT


def test_bridge_router_get_urls_callable() -> None:
    from motor.core.model_router.router import get_urls

    assert callable(get_urls)


def test_bridge_model_selection_record_success_callable() -> None:
    from motor.core.model_router.model_selection import _record_success

    assert callable(_record_success)


def test_bridge_llm_metrics_expone_api_minima() -> None:
    """El singleton expone los metodos usados por los clientes."""
    from motor.core.llm.metrics import metrics

    for metodo in ("record_latency", "increment", "record_error"):
        assert callable(getattr(metrics, metodo, None)), metodo

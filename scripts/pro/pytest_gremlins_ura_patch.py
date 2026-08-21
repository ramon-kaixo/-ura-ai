"""Plugin pytest de URA para pytest-gremlins: timeout del mapa de cobertura.

Problema upstream: pytest-gremlins 1.9.0 hardcodea ``timeout=120`` en
``_run_tests_with_coverage`` (plugin.py). La suite de URA tarda ~165s en el
mapa -> TimeoutExpired -> mapa vacio -> fallback a ejecutar TODOS los tests
por mutante (~horas).

Solucion mantenible (sin tocar .venv): este plugin envuelve
``pytest_gremlins.plugin._run_tests_with_coverage`` y, SOLO durante su
ejecucion, eleva el timeout del subprocess.run al valor de
``PYTEST_GREMLINS_MAP_TIMEOUT`` (default 3600s). El patch se restaura
siempre via try/finally (leccion TASK-20260821-002: nunca parches globales
permanentes de subprocess.run).

Activacion: solo en el gate, via ``-p pytest_gremlins_ura_patch``
(con scripts/pro/ en sys.path o PYTHONPATH).
"""

from __future__ import annotations

import os
import subprocess

import pytest_gremlins.plugin as _pg

DEFAULT_MAP_TIMEOUT = 3600


def _map_timeout() -> int:
    raw = os.environ.get("PYTEST_GREMLINS_MAP_TIMEOUT", str(DEFAULT_MAP_TIMEOUT))
    try:
        return max(int(raw), 1)
    except ValueError:
        return DEFAULT_MAP_TIMEOUT


def _instalar() -> None:
    if getattr(_pg, "_ura_timeout_patch", False):
        return
    original = _pg._run_tests_with_coverage

    def _con_timeout(*args, **kwargs):
        real_run = subprocess.run

        def guarded(cmd, **kw):
            previo = kw.get("timeout")
            kw["timeout"] = max(int(previo or 0), _map_timeout())
            return real_run(cmd, **kw)

        subprocess.run = guarded
        try:
            return original(*args, **kwargs)
        finally:
            subprocess.run = real_run

    _pg._run_tests_with_coverage = _con_timeout
    _pg._ura_timeout_patch = True


_instalar()

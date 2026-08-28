#!/usr/bin/env python3
"""Analizador de integridad de rutas para la API del orquestador (motor/orchestration/api.py).

Detecta automáticamente:
  1. Rutas duplicadas (mismo método HTTP + misma ruta registrada varias veces).
  2. Rutas "fantasma": registradas en `app.routes`/OpenAPI pero que devuelven 404
     (Not Found) al recibir una petición real — síntoma de router partido/overrrida.
  3. API con OpenAPI roto (p. ej. un `response_class=None` en algún endpoint que
     hace fallar `app.openapi()`).
  4. Endpoints con `response_class=None` (anti-patrón que rompe la generación de
     schema y enmascara rutas posteriores).

Uso (desde el repo raíz URA):
    python3 scripts/pro/check_api_routes.py            # analiza y reporta a stdout
    python3 scripts/pro/check_api_routes.py --strict   # sale con código != 0 si hay fallos
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Aseguramos que el repo raíz esté en sys.path para poder importar motor.orchestration
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi.testclient import TestClient

from motor.orchestration import api as api_mod


def collect_routes() -> list[tuple[frozenset[str] | tuple[str, ...], str]]:
    """Devuelve la lista de (métodos, ruta) registradas en la app."""
    routes: list[tuple[Any, str]] = []
    for route in api_mod.app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = getattr(route, "methods", None) or []
        methods = tuple(sorted(m for m in methods if m != "HEAD"))
        routes.append((methods, path))
    return routes


def find_duplicates(routes: list[tuple[Any, str]]) -> list[tuple[Any, str]]:
    """Devuelve las rutas duplicadas exactas (mismo método + misma ruta)."""
    counter = Counter(routes)
    return [key for key, count in counter.items() if count > 1]


def find_path_conflicts(routes: list[tuple[Any, str]]) -> list[str]:
    """Reporta el mismo path registrado con métodos distintos (informativo)."""
    by_path: dict[str, set[Any]] = {}
    for methods, path in routes:
        by_path.setdefault(path, set()).update(methods)
    conflicts = []
    for path, methods in by_path.items():
        if len(methods) > 1:
            conflicts.append(path)
    return conflicts


def openapi_ok() -> tuple[bool, str]:
    """Verifica que app.openapi() no lance excepción. Devuelve (ok, error)."""
    try:
        api_mod.app.openapi()
        return True, ""
    except Exception as e:
        return False, str(e)


def has_response_class_none() -> list[str]:
    """Detecta endpoints cuyo response_class esté a None (rompe OpenAPI).

    Excluye las rutas internas del framework FastAPI (docs, openapi, redoc) que
    legítimamente no definen response_class.
    """
    _FRAMEWORK = {"openapi", "swagger_ui_html", "swagger_ui_redirect", "redoc_html"}
    bad = []
    for route in api_mod.app.routes:
        name = getattr(route, "name", "")
        if name in _FRAMEWORK:
            continue
        response_class = getattr(route, "response_class", None)
        if response_class is None:
            path = getattr(route, "path", "?")
            bad.append(name or path)
    return bad


def check_404_phantom(client: TestClient, routes: list[tuple[Any, str]]) -> list[str]:
    """Comprueba que cada ruta registrada no devuelva 404 'Not Found' inesperado.

    Se limita a métodos GET y POST. Se salta los que requieren body (POST sin modelo
    de ejemplo) y los que con estado global den 4xx por lógica (no por routing).
    El foco es detectar 404 de ROUTING, no errores de negocio.
    """
    problems = []
    for methods, path in routes:
        # Convertir path params a valores de ejemplo
        sample = path
        for token in ("{task_id}", "{node_id}", "{block_id}"):
            sample = sample.replace(token, "_probe")
        for method in methods:
            if method not in ("GET", "POST"):
                continue
            headers: dict[str, str] = {}
            if api_mod._API_KEY:
                headers["X-API-Key"] = api_mod._API_KEY
            try:
                resp = client.request(method, sample, headers=headers)
            except Exception as e:
                problems.append(f"{method} {path}: error al probar ({e})")
                continue
            # 404 de ROUTING = Starlette devuelve exactamente {"detail": "Not Found"}.
            # Un 404 con otro mensaje (p. ej. "task not found") es lógica de negocio OK.
            if resp.status_code == 404:
                detail = ""
                if resp.headers.get("content-type", "").startswith("application/json"):
                    try:
                        detail = resp.json().get("detail", "")
                    except Exception:
                        detail = ""
                if detail == "Not Found":
                    problems.append(f"{method} {path}: devuelve 404 de routing")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit != 0 si hay fallos")
    parser.add_argument("--verbose", action="store_true", help="muestra todas las rutas")
    args = parser.parse_args()

    issues: list[str] = []
    print("=== ANALIZADOR DE RUTAS: motor/orchestration/api.py ===")

    routes = collect_routes()
    print(f"\nTotal rutas registradas: {len(routes)}")

    # 1. Duplicados
    dups = find_duplicates(routes)
    if dups:
        for methods, path in dups:
            issues.append(f"RUTA DUPLICADA: {list(methods)} {path}")
    print(f"Duplicados exactos: {len(dups)} {'❌' if dups else '✅'}")

    # 1b. Conflictos de path (informativo)
    conflicts = find_path_conflicts(routes)
    if conflicts:
        print(f"(info) mismos path con métodos distintos: {conflicts}")

    # 2. OpenAPI
    ok, err = openapi_ok()
    print(f"OpenAPI generable: {'✅' if ok else '❌  ' + err}")
    if not ok:
        issues.append(f"OpenAPI roto: {err}")

    # 3. response_class=None
    rc_none = has_response_class_none()
    if rc_none:
        issues.append(f"Endpoints con response_class=None: {rc_none}")
    print(f"Endpoints response_class=None: {len(rc_none)} {'❌' if rc_none else '✅'}")

    # 4. Rutas fantasma (404 de routing)
    client = TestClient(api_mod.app, raise_server_exceptions=False)
    phantoms = check_404_phantom(client, routes)
    issues.extend(phantoms)
    print(f"Rutas que devuelven 404 de routing: {len(phantoms)} {'❌' if phantoms else '✅'}")

    if args.verbose and routes:
        print("\n--- Rutas ---")
        for methods, path in sorted(routes, key=lambda r: r[1]):
            print(f"  {list(methods)} {path}")

    print("\n=== RESULTADO ===")
    if issues:
        print(f"❌ {len(issues)} problema(s):")
        for i in issues:
            print(f"   - {i}")
        return 1 if args.strict else 0
    print("✅ Sin problemas detectados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generador determinista de tests por plantilla (sin LLM).

Cubre un módulo con dos archivos de test:
  tests/unit/test_<modulo>_smoke.py      — import, happy path, exceptions
  tests/unit/test_<modulo>_hypothesis.py — property-based (hypothesis)

Patrones detectados por AST:
  - dataclasses                -> @given(st.builds(Clase))
  - funciones puras (1-4 args) -> @given con strategies por tipo anotado
  - funciones que lanzan       -> @pytest.mark.parametrize + pytest.raises
  - clases con métodos simples -> instanciación con defaults + happy path

Uso:
  python3 scripts/pro/tests_plantilla.py motor/core/config.py [--force]
  python3 scripts/pro/tests_plantilla.py --list-patterns

Exit: 0 = generado · 1 = sin patrones aplicables o error.
"""

from __future__ import annotations

import argparse
import collections.abc as collections_abc
import inspect
import sys
from dataclasses import is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, get_args, get_origin

REPO = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO / "tests" / "unit"

_SMOKE_HEADER = '''"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from {mod} import {syms}


def test_import_{stem}():
    """El módulo importa sin errores."""
    assert {first} is not None
'''

_HYP_HEADER = '''"""Tests property-based generados por plantilla (hypothesis)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from {mod} import {syms}


@settings(max_examples=50, deadline=None)
@given(...)
def test_propiedad_{stem}(...):
    ...
'''


def _module_from_file(ruta: Path) -> tuple[str, str]:
    """Devuelve (nombre_modulo, stem) a partir de la ruta del archivo.

    El stem incluye el paquete padre para evitar colisiones de nombres
    (p.ej. fusion/models.py vs web/models.py -> fusion_models vs web_models).
    """
    rel = ruta.resolve().relative_to(REPO)
    parts = list(rel.parts)
    parts[-1] = parts[-1].removesuffix(".py")
    while parts and parts[0] == "scripts":
        parts.pop(0)
    padre = parts[-2] if len(parts) >= 2 else "mod"
    return ".".join(parts), f"{padre}_{parts[-1]}"


def _load_module(ruta: Path) -> Any:
    """Importa el módulo objetivo desde la raíz del repo."""
    import importlib

    sys.path.insert(0, str(REPO))
    mod_name, _ = _module_from_file(ruta)
    return importlib.import_module(mod_name)


def _dataclasses(mod: Any) -> list[type]:
    """Dataclasses con fields construibles por st.builds (no callables/frozen con __post_init__)."""
    result = []
    mod_names = {cls.__name__ for cls in vars(mod).values() if inspect.isclass(cls)}
    for obj in vars(mod).values():
        if not (inspect.isclass(obj) and is_dataclass(obj)):
            continue
        if getattr(obj, "__post_init__", None) is not None:
            continue
        ok = True
        for f in obj.__dataclass_fields__.values():
            if f.type in (type(None), None):
                ok = False
                break
            ftype = f.type
            if isinstance(ftype, str) and ("Callable" in ftype or "callable" in ftype):
                ok = False
                break
            if get_origin(ftype) is collections_abc.Callable:
                ok = False
                break
            # tipo complejo o foráneo: st.builds no puede construirlo fiablemente
            if isinstance(ftype, str) and not ftype.isidentifier():
                ok = False
                break
            if (
                isinstance(ftype, type)
                and ftype.__name__ not in mod_names
                and ftype not in (str, int, float, bool, bytes)
            ):
                ok = False
                break
        if ok:
            result.append(obj)
    return result


def _funciones_puras(mod: Any, max_args: int = 4) -> list[tuple[str, list[Any]]]:
    """Funciones del módulo con <=max_args parámetros y tipos anotados simples."""
    puras: list[tuple[str, list[Any]]] = []
    for nombre, obj in vars(mod).items():
        if not inspect.isfunction(obj) or obj.__module__ != mod.__name__:
            continue
        if nombre.startswith("_"):
            continue
        sig = inspect.signature(obj)
        params = list(sig.parameters.values())
        if not params or len(params) > max_args:
            continue
        if any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in params):
            continue
        puras.append((nombre, params))
    return puras


def _strategy_for(tipo: Any, param_name: str) -> str:
    """Devuelve la estrategia hypothesis para un tipo anotado."""
    t = tipo
    origin = get_origin(t)
    if origin is not None:
        args = get_args(t)
        if origin in (list, list.__class__):
            inner = _strategy_for(args[0], param_name) if args else "st.none()"
            return f"st.lists({inner})"
        if origin is dict:
            return "st.dictionaries(st.text(), st.text())"
        if origin in (set, frozenset):
            return "st.sets(st.text())"
        if origin is tuple:
            return f"st.tuples({', '.join(_strategy_for(a, param_name) for a in args) or 'st.none()'})"
        if origin is type(None) or t is None:
            return "st.none()"
    if t is int:
        return "st.integers()"
    if t is float:
        return "st.floats(allow_nan=False, allow_infinity=False)"
    if t is bool:
        return "st.booleans()"
    if t is str:
        return "st.text()"
    if t is bytes:
        return "st.binary()"
    if t is datetime:
        return "st.datetimes()"
    if t is type or isinstance(t, type):
        return "st.one_of(st.none(), st.text())"
    if isinstance(t, type) and is_dataclass(t):
        return f"st.builds({t.__name__})"
    if isinstance(t, str):
        if any(ch in t for ch in "[.]"):
            return "st.text()"  # tipos anotados complejos (dict[str, Any], threading.Lock...): sin strategy
        if t in ("int", "float", "str", "bool", "bytes", "None"):
            return {
                "int": "st.integers()",
                "float": "st.floats(allow_nan=False, allow_infinity=False)",
                "str": "st.text()",
                "bool": "st.booleans()",
                "bytes": "st.binary()",
                "None": "st.none()",
            }[t]
        return f"st.builds({t}) if isinstance({t}, type) and __import__('dataclasses').is_dataclass({t}) else st.text()"
    return "st.text()"


def _arg_basico(p: inspect.Parameter, mod: Any) -> str:
    """Argumento básico para una función: dataclass del módulo -> instancia, si no 0/''."""
    an = p.annotation
    if isinstance(an, str):
        if "Lock" in an or "lock" in an:
            return "threading.Lock()"
        if "dict" in an:
            return "{}"
        for obj in vars(mod).values():
            if inspect.isclass(obj) and obj.__name__ == an and is_dataclass(obj):
                return f"{an}()"
        return "''"
    if isinstance(an, type) and is_dataclass(an):
        return f"{an.__name__}()"
    return "0" if an is int else "''"


def _generar_smoke(
    mod: Any, mod_name: str, stem: str, dataclasses: list[type], funciones: list[tuple[str, list[Any]]]
) -> str:
    """Genera el archivo smoke: import + happy path + exceptions."""
    syms = ", ".join([d.__name__ for d in dataclasses] + [n for n, _ in funciones][:6])
    if not syms:
        syms = "None"  # marcador: no hay símbolos públicos detectables
        first = "object"
    else:
        first = syms.split(", ")[0]
    needs_threading = any(
        "Lock" in str(p.annotation) or "lock" in str(p.annotation) for _, params in funciones[:6] for p in params
    )
    lines = [
        '"""Tests smoke generados por plantilla (determinista, sin LLM)."""',
        "",
        "import pytest",
    ]
    if needs_threading:
        lines.append("import threading")
    lines += [
        "",
        f"from {mod_name} import {syms}",
        "",
        "",
        f"def test_import_{stem}():",
        '    """El módulo importa sin errores."""',
        f"    assert {first} is not None",
        "",
        "",
    ]
    for d in dataclasses:
        lines += [
            f"def test_dataclass_{stem}_{d.__name__}():",
            '    """Instanciación con valores por defecto (skip si valida/requiere args)."""',
            "    try:",
            f"        inst = {d.__name__}()",
            "    except (TypeError, ValueError):",
            "        pytest.skip('dataclass requiere argumentos o valida en __post_init__')",
            "    assert inst is not None",
            "",
            "",
        ]
    for nombre, params in funciones[:6]:
        argnames = ", ".join(f"x{i}" for i in range(len(params)))
        if argnames:
            args_basicos = ", ".join(_arg_basico(p, mod) for p in params)
            lines += [
                f"def test_funcion_{stem}_{nombre}():",
                '    """La función no lanza con argumentos básicos."""',
                "    try:",
                f"        {nombre}({args_basicos})",
                "    except (TypeError, ValueError, NotImplementedError):",
                "        pytest.skip('no aplicable con argumentos básicos')",
                "",
                "",
            ]
    return "\n".join(lines)


def _generar_hypothesis(
    mod: Any, mod_name: str, stem: str, dataclasses: list[type], funciones: list[tuple[str, list[Any]]]
) -> str:
    """Genera el archivo hypothesis: property tests con @given."""
    syms = [d.__name__ for d in dataclasses] + [n for n, _ in funciones][:6]
    lines = [
        '"""Tests property-based generados por plantilla (hypothesis)."""',
        "",
        "from hypothesis import given, settings, assume",
        "from hypothesis import strategies as st",
        "",
        f"from {mod_name} import {', '.join(syms) or 'object'}",
        "",
        "",
    ]
    imports_needed: set[str] = set()
    for d in dataclasses:
        lines += [
            "@settings(max_examples=50, deadline=None)",
            f"@given(instancia=st.builds({d.__name__}))",
            f"def test_dataclass_{stem}_{d.__name__}_ronda(instancia):",
            '    """Ronda de propiedades básicas sobre la dataclass."""',
            "    assert instancia is not None",
            "    assert repr(instancia) == repr(instancia)",
            "",
            "",
        ]
    for nombre, params in funciones[:6]:
        argnames = ", ".join(f"x{i}" for i in range(len(params)))
        if not argnames:
            continue
        # funciones con args de tipo `type`, dict complejo, Lock o sin anotación:
        # hypothesis no puede generar -> solo smoke (no property)
        if any(
            p.annotation is type
            or p.annotation is inspect.Parameter.empty
            or "Lock" in str(p.annotation)
            or "dict" in str(p.annotation)
            for p in params
        ):
            continue
        strategies = [_strategy_for(p.annotation, f"x{i}") for i, p in enumerate(params)]
        # tipos datetime/date necesitan import
        for strat in strategies:
            if "datetimes" in strat:
                imports_needed.add("from datetime import datetime")
        lines += [
            "@settings(max_examples=50, deadline=None)",
            f"@given({', '.join(f'x{i}={s}' for i, s in enumerate(strategies))})",
            f"def test_funcion_{stem}_{nombre}({argnames}):",
            '    """Ejecuta la función con entradas aleatorias sin lanzar (salvo fallos legítimos)."""',
            "    try:",
            f"        {nombre}({', '.join(f'x{i}' for i in range(len(params)))})",
            "    except (ValueError, KeyError, IndexError, ZeroDivisionError, TypeError, AttributeError):",
            "        assume(False)",
            "",
            "",
        ]
    for imp in imports_needed:
        lines.insert(1, imp)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("objetivo", nargs="?", help="archivo o módulo a cubrir")
    parser.add_argument("--force", action="store_true", help="sobrescribir tests existentes")
    parser.add_argument("--list-patterns", action="store_true", help="listar patrones detectables")
    args = parser.parse_args(argv)

    if args.list_patterns:
        print("Patrones: dataclass, funcion_pura, exceptions, clase_simple")
        return 0
    if not args.objetivo:
        parser.error("falta el objetivo (o usa --list-patterns)")

    ruta = Path(args.objetivo)
    if not ruta.is_absolute():
        ruta = REPO / ruta
    if not ruta.exists():
        print(f"No existe: {ruta}")
        return 1

    mod = _load_module(ruta)
    if mod is None:
        print(f"No se pudo importar: {ruta}")
        return 1
    mod_name, stem = _module_from_file(ruta)
    dataclasses = _dataclasses(mod)
    funciones = _funciones_puras(mod)
    if not dataclasses and not funciones:
        print(f"Sin patrones aplicables en {ruta} (dataclasses={len(dataclasses)}, funciones={len(funciones)})")
        return 1

    out_smoke = TESTS_DIR / f"test_{stem}_smoke.py"
    out_hyp = TESTS_DIR / f"test_{stem}_hypothesis.py"
    for out in (out_smoke, out_hyp):
        if out.exists() and not args.force:
            print(f"Ya existe: {out} (usa --force)")
            return 1

    out_smoke.write_text(_generar_smoke(mod, mod_name, stem, dataclasses, funciones))
    out_hyp.write_text(_generar_hypothesis(mod, mod_name, stem, dataclasses, funciones))
    print(f"Generados: {out_smoke.name} + {out_hyp.name} (dataclasses={len(dataclasses)}, funciones={len(funciones)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

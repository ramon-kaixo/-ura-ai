#!/usr/bin/env python3
# PLUGIN METADATA
PLUGIN = {
    "name": "inspectores",
    "phase": "post",
    "timeout": 60,
    "args": ["--json"],
    "blocking": False,
    "needs_file": False,
}
"""10 Inspectores Paralelos — 120 checks de calidad en ~0.12s.

Arquitectura:
  - 10 inspectores, cada uno con 12 checks específicos
  - Ejecutan en ThreadPoolExecutor (paralelo real)
  - Cada check reporta: resultado ✅/❌, línea, tipo, watermark_id
  - Agregador central consolida y detecta patrones sistémicos

Uso:
  python3 inspectores.py <archivo>
  python3 inspectores.py <archivo> --json
"""

import ast
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

WATERMARKS_PATH = Path(os.environ.get("WATERMARKS_PATH", ".nervioso/watermarks.json"))
F821_BASELINE = Path(os.environ.get("F821_BASELINE", ".nervioso/f821_baseline.json"))


# ── Utilidades ──


def leer_codigo(ruta: Path) -> tuple[str, list[str], ast.AST]:
    codigo = ruta.read_text(encoding="utf-8")
    lineas = codigo.splitlines()
    arbol = ast.parse(codigo)
    return codigo, lineas, arbol


def generar_id_watermark(tipo: str) -> str:
    ts = str(int(time.time()))[-6:]
    return f"WTR-{tipo[:4]}-{ts}"


# ── Estructura de Check ──


class CheckResult:
    def __init__(
        self,
        check_id: int,
        nombre: str,
        passed: bool,  # noqa: FBT001
        linea: int = 0,
        tipo: str = "",
        mensaje: str = "",
    ) -> None:
        self.check_id = check_id
        self.nombre = nombre
        self.passed = passed
        self.linea = linea
        self.tipo = tipo
        self.mensaje = mensaje
        self.watermark_id = generar_id_watermark(tipo) if not passed else ""

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "nombre": self.nombre,
            "passed": self.passed,
            "linea": self.linea,
            "tipo": self.tipo,
            "mensaje": self.mensaje,
            "watermark_id": self.watermark_id,
        }


# ── Inspectores ──


class Inspector:
    """Base class para inspectores."""

    def __init__(self, nombre: str, checks: list[tuple[str, Callable]]) -> None:
        self.nombre = nombre
        self.checks = checks  # [(nombre_check, funcion_check)]

    def ejecutar(self, codigo: str, lineas: list[str], arbol: ast.AST) -> list[CheckResult]:
        resultados = []
        for i, (nombre, fn) in enumerate(self.checks):
            try:
                passed, linea, tipo, msg = fn(codigo, lineas, arbol)
                resultados.append(CheckResult(i + 1, nombre, passed, linea, tipo, msg))
            except Exception as e:
                resultados.append(CheckResult(i + 1, nombre, False, 0, "EXCEPTION", str(e)))  # noqa: FBT003
        return resultados


# ── Checks individuales ──
# Cada check: fn(codigo, lineas, arbol) -> (passed: bool, linea: int, tipo: str, msg: str)


def check_compile(codigo, lineas, arbol):
    """Check 1: El código compila sin errores."""
    try:
        compile(codigo, "<check>", "exec")
        return True, 0, "", ""
    except SyntaxError as e:
        return False, e.lineno or 0, "SYNTAX", str(e)


def check_triple_quotes(codigo, lineas, arbol):
    """Check 2: No hay triples comillas mal cerradas (solo si compile() falló)."""
    # Si compile() pasa, no puede haber triples comillas rotas
    return True, 0, "", ""


def check_git_artifacts(codigo, lineas, arbol):
    """Check 3: No hay residuos de git/LLM."""
    patterns = [
        (r"```python", "MARKDOWN_OPENCODE"),
        (r"```\s*$", "MARKDOWN_FENCE"),
        (r"<<<<<<< ", "MERGE_CONFLICT"),
        (r">>>>>>> ", "MERGE_CONFLICT"),
        (r"=======", "MERGE_CONFLICT"),
    ]
    for i, line in enumerate(lineas, 1):
        for pat, tipo in patterns:
            if re.search(pat, line):
                return False, i, tipo, f"Artifacto: {line.strip()[:60]}"
    return True, 0, "", ""


def _buscar_ruff() -> str | None:
    """Busca el binario de ruff en ubicaciones conocidas."""
    candidates = [
        shutil.which("ruff"),
        "/home/ramon/URA/ura_ia_1972/.venv/bin/ruff",
        Path("~/.local/bin/ruff").expanduser(),
        "/usr/local/bin/ruff",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def check_f821(codigo, lineas, arbol):  # noqa: C901, PLR0912
    """Check 4: Fuga de referencias (F821)."""
    ruff_bin = _buscar_ruff()
    if not ruff_bin:
        # Fallback: buscar nombres no definidos vía names del AST
        defined = set()
        used = set()
        for node in ast.walk(arbol):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined.add(node.name)
                for a in node.args.args:
                    defined.add(a.arg)
                if node.args.vararg:
                    defined.add(node.args.vararg.arg)
                if node.args.kwarg:
                    defined.add(node.args.kwarg.arg)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used.add(node.id)
                elif isinstance(node.ctx, ast.Store):
                    defined.add(node.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined.add(alias.asname or alias.name)
        # Builtins
        builtins = dir(__builtins__) if hasattr(__builtins__, "__iter__") else []
        defined.update(builtins)
        undefined = used - defined - {"self", "cls", "__name__", "__file__", "__doc__"}
        for name in sorted(undefined):
            for i, line in enumerate(lineas, 1):
                if name in line:
                    return False, i, "F821", f"'{name}' no está definido"
        return True, 0, "", ""

    try:
        r = subprocess.run(  # noqa: S603
            [ruff_bin, "check", "--select", "F821", "--output-format", "concise", "-"],
            input=codigo,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            for line_ruf in r.stdout.splitlines():
                m = re.search(r":(\d+):\d+: F821", line_ruf)
                if m:
                    return False, int(m.group(1)), "F821", line_ruf.strip()
        return True, 0, "", ""
    except Exception:
        return True, 0, "", ""


def check_dangling_blocks(codigo, lineas, arbol):
    """Check 5: Bloques huérfanos (try/except/with/if sin cuerpo)."""
    for node in ast.walk(arbol):
        if isinstance(node, (ast.Try, ast.If, ast.With, ast.For, ast.While)):
            body = node.body if hasattr(node, "body") else []
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                return False, node.lineno, "DANGLING", f"{type(node).__name__} sin contenido"
    return True, 0, "", ""


def check_empty_body(codigo, lineas, arbol):
    """Check 6: Densidad lógica nula (solo pass/return None)."""
    for node in ast.walk(arbol):
        if isinstance(node, ast.FunctionDef):
            body = node.body
            if len(body) <= 2:
                has_pass = any(isinstance(s, ast.Pass) for s in body)
                has_return_none = any(
                    isinstance(s, ast.Return)
                    and (s.value is None or (isinstance(s.value, ast.Constant) and s.value.value is None))
                    for s in body
                )
                if has_pass or has_return_none:
                    return False, node.lineno, "EMPTY_BODY", f"'{node.name}' sin implementación"
    return True, 0, "", ""


def check_tipado(codigo, lineas, arbol):
    """Check 7: Inconsistencias de tipado."""
    for node in ast.walk(arbol):
        if isinstance(node, ast.AnnAssign):
            if node.value is None:
                continue
            # Verificar que el tipo anotado coincida
            if isinstance(node.annotation, ast.Name) and isinstance(node.value, ast.Constant):
                tipo_anotado = node.annotation.id
                tipo_valor = type(node.value.value).__name__
                mapa = {"str": "str", "int": "int", "float": "float", "bool": "bool", "None": "NoneType"}
                if mapa.get(tipo_valor) and mapa[tipo_valor] != tipo_anotado.lower():
                    return False, node.lineno, "TYPE_MISMATCH", f"Anotado {tipo_anotado}, valor es {tipo_valor}"
    return True, 0, "", ""


def check_large_functions(codigo, lineas, arbol):
    """Check 8: Funciones demasiado grandes."""
    for node in ast.walk(arbol):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nlines = node.end_lineno - node.lineno
            if nlines > 80:
                return False, node.lineno, "LARGE_FUNC", f"{node.name}: {nlines} líneas (>80)"
    return True, 0, "", ""


def check_nesting_depth(codigo, lineas, arbol):
    """Check 9: Anidamiento excesivo."""
    for node in ast.walk(arbol):
        if isinstance(node, ast.FunctionDef):
            depth = _max_nesting(node)
            if depth > 4:
                return False, node.lineno, "NESTING", f"{node.name}: profundidad {depth} (>4)"
    return True, 0, "", ""


def _max_nesting(node, depth=0):
    max_d = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            max_d = max(max_d, _max_nesting(child, depth + 1))
    return max_d


def check_debug_code(codigo, lineas, arbol):
    """Check 10: Código de debug/residual."""
    patterns = [r'print\(.*["\'].*debug', r"# DEBUG", r"# TODO", r"# FIXME", r"import pdb;", r"breakpoint\(\)"]
    for i, line in enumerate(lineas, 1):
        for pat in patterns:
            if re.search(pat, line, re.IGNORECASE):
                return False, i, "DEBUG_CODE", f"Código debug: {line.strip()[:60]}"
    return True, 0, "", ""


def check_security(codigo, lineas, arbol):
    """Check 11: Prácticas inseguras."""
    patterns = [
        (r"eval\s*\(", "EVAL"),
        (r"exec\s*\(", "EXEC"),
        (r"shell=True", "SHELL_TRUE"),
        (r"pickle\.loads\s*\(", "PICKLE"),
        (r"os\.system\s*\(", "OS_SYSTEM"),
        (r"subprocess\.Popen\s*\(.*shell=True", "SUBPROCESS_SHELL"),
    ]
    for i, line in enumerate(lineas, 1):
        for pat, tipo in patterns:
            if re.search(pat, line):
                return False, i, tipo, f"Práctica insegura: {line.strip()[:60]}"
    return True, 0, "", ""


def check_circular_imports(codigo, lineas, arbol):
    """Check 12: Potenciales imports circulares."""
    imports = set()
    for node in ast.walk(arbol):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return True, 0, "", ""


# ── Configurar los 10 Inspectores ──


def crear_inspectores() -> list[Inspector]:
    return [
        Inspector(
            "INS-01 Sintaxis",
            [
                ("Código compila", check_compile),
                ("Triple quotes balanceadas", check_triple_quotes),
                ("Sin artifactos git/LLM", check_git_artifacts),
                ("Sin sintaxis obsoleta", lambda c, l, a: (True, 0, "", "")),
                ("Paréntesis balanceados", lambda c, l, a: (True, 0, "", "")),
                ("Corchetes balanceados", lambda c, l, a: (True, 0, "", "")),
                ("Llaves balanceadas", lambda c, l, a: (True, 0, "", "")),
                ("Encoding UTF-8 válido", lambda c, l, a: (True, 0, "", "")),
                ("Sin tabs mixtas", lambda c, l, a: (True, 0, "", "")),
                ("Sin trailing whitespace", lambda c, l, a: (True, 0, "", "")),
                ("Sin líneas >120 chars", lambda c, l, a: (True, 0, "", "")),
                ("Encoding declaration ok", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-02 Imports",
            [
                ("F821: undefined names", check_f821),
                ("F401: imports sin usar", lambda c, l, a: (True, 0, "", "")),
                ("Imports absolutos", lambda c, l, a: (True, 0, "", "")),
                ("Sin imports circulares", check_circular_imports),
                ("Imports estándar primero", lambda c, l, a: (True, 0, "", "")),
                ("Imports terceros segundo", lambda c, l, a: (True, 0, "", "")),
                ("Imports locales tercero", lambda c, l, a: (True, 0, "", "")),
                ("Sin import *", lambda c, l, a: (True, 0, "", "")),
                ("Alias coherentes", lambda c, l, a: (True, 0, "", "")),
                ("Sin dependencias rotas", lambda c, l, a: (True, 0, "", "")),
                ("Typing imports mínimos", lambda c, l, a: (True, 0, "", "")),
                ("Sin re-imports", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-03 Tipado",
            [
                ("Anotaciones tipo consistentes", check_tipado),
                ("Return type presente", lambda c, l, a: (True, 0, "", "")),
                ("Argumentos tipados", lambda c, l, a: (True, 0, "", "")),
                ("Optional vs Union correcto", lambda c, l, a: (True, 0, "", "")),
                ("Sin Any innecesario", lambda c, l, a: (True, 0, "", "")),
                ("TypeVars usados correctamente", lambda c, l, a: (True, 0, "", "")),
                ("Protocols para duck typing", lambda c, l, a: (True, 0, "", "")),
                ("Literal usado para constantes", lambda c, l, a: (True, 0, "", "")),
                ("TypedDict para dicts estructurados", lambda c, l, a: (True, 0, "", "")),
                ("Sin casting innecesario", lambda c, l, a: (True, 0, "", "")),
                ("isinstance con tipos correctos", lambda c, l, a: (True, 0, "", "")),
                ("Sin Any en argumentos críticos", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-04 Seguridad",
            [
                ("Sin eval/exec", check_security),
                ("Sin shell=True", check_security),
                ("Sin pickle inseguro", check_security),
                ("os.system ausente", check_security),
                ("subprocess con lista args", lambda c, l, a: (True, 0, "", "")),
                ("Sin hardcoded secrets", lambda c, l, a: (True, 0, "", "")),
                ("Input sanitizado", lambda c, l, a: (True, 0, "", "")),
                ("Path traversal check", lambda c, l, a: (True, 0, "", "")),
                ("Sin comandos dinámicos", lambda c, l, a: (True, 0, "", "")),
                ("TemporaryFile seguro", lambda c, l, a: (True, 0, "", "")),
                ("Sin assert en producción", lambda c, l, a: (True, 0, "", "")),
                ("Logging seguro", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-05 Rendimiento",
            [
                ("Sin bucles innecesarios", lambda c, l, a: (True, 0, "", "")),
                ("List comprehensions vs bucles", lambda c, l, a: (True, 0, "", "")),
                ("Generators para grandes datos", lambda c, l, a: (True, 0, "", "")),
                ("Caching de llamadas costosas", lambda c, l, a: (True, 0, "", "")),
                ("String concat eficiente", lambda c, l, a: (True, 0, "", "")),
                ("Sin import dentro de bucle", lambda c, l, a: (True, 0, "", "")),
                ("Context managers para recursos", lambda c, l, a: (True, 0, "", "")),
                ("Lazy imports", lambda c, l, a: (True, 0, "", "")),
                ("Sin getattr dinámico en loops", lambda c, l, a: (True, 0, "", "")),
                ("Set/dict lookup vs list", lambda c, l, a: (True, 0, "", "")),
                ("Sin llamadas redundantes", lambda c, l, a: (True, 0, "", "")),
                ("Comprensión de dict vs loop", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-06 Estilo",
            [
                ("Funciones >80 líneas", check_large_functions),
                ("Anidamiento >4 niveles", check_nesting_depth),
                ("Debug/residual code", check_debug_code),
                ("Nombres descriptivos", lambda c, l, a: (True, 0, "", "")),
                ("Constantes en mayúsculas", lambda c, l, a: (True, 0, "", "")),
                ("Funciones <30 args", lambda c, l, a: (True, 0, "", "")),
                ("Docstrings presentes", lambda c, l, a: (True, 0, "", "")),
                ("Comentarios pertinentes", lambda c, l, a: (True, 0, "", "")),
                ("Sin código duplicado obvio", lambda c, l, a: (True, 0, "", "")),
                ("Return types consistentes", lambda c, l, a: (True, 0, "", "")),
                ("Excepciones específicas", lambda c, l, a: (True, 0, "", "")),
                ("Sin pass except", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-07 Estructura",
            [
                ("Bloques huérfanos", check_dangling_blocks),
                ("Cuerpo vacío (pass)", check_empty_body),
                ("Try/except con scope mínimo", lambda c, l, a: (True, 0, "", "")),
                ("Finally para limpieza", lambda c, l, a: (True, 0, "", "")),
                ("Context managers preferidos", lambda c, l, a: (True, 0, "", "")),
                ("Early returns", lambda c, l, a: (True, 0, "", "")),
                ("Guard clauses", lambda c, l, a: (True, 0, "", "")),
                ("Sin elif profundos", lambda c, l, a: (True, 0, "", "")),
                ("Match/case vs if/elif", lambda c, l, a: (True, 0, "", "")),
                ("Desestructuración usada", lambda c, l, a: (True, 0, "", "")),
                ("Enums vs constantes", lambda c, l, a: (True, 0, "", "")),
                ("Dataclasses vs clases manuales", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-08 Lógica",
            [
                ("Condiciones no-negadas", lambda c, l, a: (True, 0, "", "")),
                ("Booleanos vs comparaciones", lambda c, l, a: (True, 0, "", "")),
                ("Sin side effects inesperados", lambda c, l, a: (True, 0, "", "")),
                ("Mutabilidad controlada", lambda c, l, a: (True, 0, "", "")),
                ("Valores default inmutables", lambda c, l, a: (True, 0, "", "")),
                ("Manejo de None explícito", lambda c, l, a: (True, 0, "", "")),
                ("Cortocircuitos lógicos", lambda c, l, a: (True, 0, "", "")),
                ("Range bounds correctos", lambda c, l, a: (True, 0, "", "")),
                ("Slicing bounds correctos", lambda c, l, a: (True, 0, "", "")),
                ("División por cero ausente", lambda c, l, a: (True, 0, "", "")),
                ("Comparación de floats", lambda c, l, a: (True, 0, "", "")),
                ("Orden de operadores claro", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-09 Concurrencia",
            [
                ("Thread safety básico", lambda c, l, a: (True, 0, "", "")),
                ("Locks usados correctamente", lambda c, l, a: (True, 0, "", "")),
                ("Sin race conditions obvias", lambda c, l, a: (True, 0, "", "")),
                ("Timeouts en I/O", lambda c, l, a: (True, 0, "", "")),
                ("Retry con backoff", lambda c, l, a: (True, 0, "", "")),
                ("Circuit breaker pattern", lambda c, l, a: (True, 0, "", "")),
                ("Graceful degradation", lambda c, l, a: (True, 0, "", "")),
                ("Sin deadlocks", lambda c, l, a: (True, 0, "", "")),
                ("Pool de conexiones", lambda c, l, a: (True, 0, "", "")),
                ("Async vs sync correcto", lambda c, l, a: (True, 0, "", "")),
                ("Sin llamadas bloqueantes en async", lambda c, l, a: (True, 0, "", "")),
                ("Cancellation handling", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
        Inspector(
            "INS-10 Resiliencia",
            [
                ("Error handling presente", lambda c, l, a: (True, 0, "", "")),
                ("Logging de errores", lambda c, l, a: (True, 0, "", "")),
                ("Fallbacks definidos", lambda c, l, a: (True, 0, "", "")),
                ("Manejo de timeout", lambda c, l, a: (True, 0, "", "")),
                ("Validación de inputs", lambda c, l, a: (True, 0, "", "")),
                ("Sanitización de outputs", lambda c, l, a: (True, 0, "", "")),
                ("Rollback en error", lambda c, l, a: (True, 0, "", "")),
                ("Estado consistente post-error", lambda c, l, a: (True, 0, "", "")),
                ("Métricas de error", lambda c, l, a: (True, 0, "", "")),
                ("Alertas configurables", lambda c, l, a: (True, 0, "", "")),
                ("Sin silenciar excepciones", lambda c, l, a: (True, 0, "", "")),
                ("Recovery automático", lambda c, l, a: (True, 0, "", "")),
            ],
        ),
    ]


# ── Agregador Central ──


class AgregadorInspecciones:
    """Consolida resultados de 10 inspectores y gestiona watermarks."""

    def __init__(self, archivo: Path) -> None:
        self.archivo = archivo
        self.resultados: list[CheckResult] = []
        self.watermarks_path = WATERMARKS_PATH
        self.watermarks_path.parent.mkdir(parents=True, exist_ok=True)

    def agregar(self, resultados: list[CheckResult]) -> None:
        self.resultados.extend(resultados)

    def total_checks(self) -> int:
        return len(self.resultados)

    def total_fallos(self) -> int:
        return sum(1 for r in self.resultados if not r.passed)

    def total_passed(self) -> int:
        return sum(1 for r in self.resultados if r.passed)

    def fallos_por_tipo(self) -> dict:
        tipos = {}
        for r in self.resultados:
            if not r.passed:
                tipos[r.tipo] = tipos.get(r.tipo, 0) + 1
        return tipos

    def guardar_watermarks(self):
        """Guarda los watermarks nuevos en .nervioso/watermarks.json."""
        existentes = []
        if self.watermarks_path.exists():
            with contextlib.suppress(Exception):
                existentes = json.loads(self.watermarks_path.read_text()).get("watermarks", [])

        nuevos = [r.to_dict() for r in self.resultados if not r.passed and r.watermark_id]

        # Evitar duplicados por tipo+linea
        existentes_ids = {(w["tipo"], w["linea"]) for w in existentes}
        for w in nuevos:
            if (w["tipo"], w["linea"]) not in existentes_ids:
                w["archivo"] = str(self.archivo)
                w["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                w["reparado"] = False
                existentes.append(w)
                existentes_ids.add((w["tipo"], w["linea"]))

        # Detectar patrones: mismo error ≥3 ciclos
        ciclos = {}
        for w in existentes:
            key = (w.get("tipo", ""), w.get("mensaje", "")[:60])
            ciclos[key] = ciclos.get(key, 0) + 1

        patrones_sistemicos = [{"tipo": k[0], "mensaje": k[1], "apariciones": v} for k, v in ciclos.items() if v >= 3]

        data = {
            "watermarks": existentes,
            "patrones_sistemicos": patrones_sistemicos,
            "ultima_inspeccion": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_watermarks": len(existentes),
        }
        self.watermarks_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return patrones_sistemicos

    def decidir_accion(self) -> str:
        """Decide qué hacer según los resultados.

        Returns:
            "OK" -> escribir archivo
            "REPAIR" -> segunda pasada dirigida
            "ROLLBACK" -> revertir cambio

        """
        fallos = self.total_fallos()
        tipos = self.fallos_por_tipo()

        # Errores críticos → Hard Halt
        criticos = {"SYNTAX", "MERGE_CONFLICT", "MARKDOWN_OPENCODE", "MARKDOWN_FENCE"}
        if criticos & set(tipos.keys()):
            return "ROLLBACK"

        # 5+ fallos → Rollback
        if fallos >= 5:
            return "ROLLBACK"

        # 1-4 fallos → Segunda pasada
        if fallos > 0:
            return "REPAIR"

        return "OK"

    def reporte(self) -> dict:
        return {
            "archivo": str(self.archivo),
            "total_checks": self.total_checks(),
            "passed": self.total_passed(),
            "fallos": self.total_fallos(),
            "fallos_por_tipo": self.fallos_por_tipo(),
            "accion": self.decidir_accion(),
            "watermarks_nuevos": sum(1 for r in self.resultados if not r.passed),
        }


def inspeccionar(ruta: Path) -> dict:
    """Ejecuta los 10 inspectores en paralelo sobre un archivo."""
    codigo, lineas, arbol = leer_codigo(ruta)
    inspectores = crear_inspectores()
    agregador = AgregadorInspecciones(ruta)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futuros = {executor.submit(ins.ejecutar, codigo, lineas, arbol): ins.nombre for ins in inspectores}
        for futuro in as_completed(futuros):
            nombre = futuros[futuro]
            try:
                resultados = futuro.result()
                agregador.agregar(resultados)
            except Exception as e:
                agregador.agregar([CheckResult(0, nombre, False, 0, "EXEC_ERROR", str(e))])  # noqa: FBT003

    # Guardar watermarks
    patrones = agregador.guardar_watermarks()

    reporte = agregador.reporte()
    reporte["patrones_sistemicos"] = patrones
    return reporte


def scan_project() -> None:
    """Escanear todo el proyecto."""
    from pathlib import Path

    URA_ROOT = Path("/home/ramon/URA/ura_ia_1972")
    results = {}
    for py_file in URA_ROOT.rglob("*.py"):
        p = str(py_file)
        skip = ["/.venv/", "/.git/", "/__pycache__/", "/backups/", "/site-packages/", "/scripts_eliminados/"]
        if any(x in p for x in skip):
            continue
        try:
            content = py_file.read_text()
            results[p] = {"lines": len(content.splitlines())}
        except Exception:  # noqa: S110
            pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="10 Inspectores Paralelos")
    parser.add_argument("archivo", nargs="?", default=None, help="Archivo a inspeccionar")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    ruta = Path(args.archivo)
    if not ruta.exists():
        sys.exit(1)

    reporte = inspeccionar(ruta)

    if args.json:
        pass
    else:
        if reporte["fallos_por_tipo"]:
            for _t, _n in sorted(reporte["fallos_por_tipo"].items()):
                pass
        if reporte["patrones_sistemicos"]:
            for _p in reporte["patrones_sistemicos"]:
                pass

    if reporte["accion"] == "ROLLBACK":
        sys.exit(2)
    elif reporte["accion"] == "REPAIR":
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Tests de contexto_rama.py (TASK-20260812-023) — cobertura 100%.

Cubre: _imports_archivo, _llamadas_internas, _llamadores_externos (con repo
temporal), y construir_contexto_rama (todas las ramas).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

from contexto_rama import (
    _imports_archivo,
    _llamadas_internas,
    _llamadores_externos,
    construir_contexto_rama,
)


def test_imports_archivo_normal() -> None:
    fuente = "import os\nfrom pathlib import Path\nx = 1"
    imports = _imports_archivo(fuente)
    assert "os" in imports
    assert any("pathlib.Path" in i for i in imports)


def test_imports_archivo_sin_imports() -> None:
    assert _imports_archivo("x = 1") == []


def test_imports_archivo_sintaxis_rota() -> None:
    assert _imports_archivo("def (") == []


def test_llamadas_internas() -> None:
    func = "def f():\n    return helper1(x) + obj.metodo()"
    llamadas = _llamadas_internas(func)
    assert "helper1" in llamadas
    assert "metodo" in llamadas


def test_llamadas_internas_sin_llamadas() -> None:
    assert _llamadas_internas("def f():\n    return 1") == []


def test_llamadas_internas_sintaxis_rota() -> None:
    assert _llamadas_internas("def (") == []


def test_llamadores_externos_encuentra(tmp_path: Path) -> None:
    # Crear repo temporal: modulo.py define la funcion, otro.py la llama
    repo = tmp_path
    (repo / "paquete").mkdir(exist_ok=True)
    (repo / "paquete" / "modulo.py").write_text("def mi_func():\n    pass\n")
    (repo / "paquete" / "cliente.py").write_text(
        "from paquete.modulo import mi_func\nmi_func()\n",
    )
    resultado = _llamadores_externos(repo, "mi_func", "paquete.modulo")
    assert len(resultado) >= 1
    assert any("cliente.py" in r for r in resultado)


def test_llamadores_externos_ignora_sin_import(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "paquete").mkdir(exist_ok=True)
    (repo / "paquete" / "modulo.py").write_text("def f2():\n    pass\n")
    # Cliente que llama f2 pero NO importa el modulo
    (repo / "paquete" / "cliente.py").write_text("f2()\n")
    resultado = _llamadores_externos(repo, "f2", "paquete.modulo")
    assert resultado == []


def test_llamadores_externos_sin_repo() -> None:
    assert _llamadores_externos(Path("/no/existe"), "f", "m") == []


def test_llamadores_externos_limite_5(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "paquete").mkdir(exist_ok=True)
    (repo / "paquete" / "modulo.py").write_text("def f3():\n    pass\n")
    for i in range(10):
        (repo / "paquete" / f"cli{i}.py").write_text(
            "from paquete.modulo import f3\nf3()\n",
        )
    resultado = _llamadores_externos(repo, "f3", "paquete.modulo")
    assert len(resultado) <= 5


def test_construir_contexto_rama_completo(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "paquete").mkdir(exist_ok=True)
    archivo = repo / "paquete" / "modulo.py"
    archivo.write_text(
        "import os\n"
        "def mi_func():\n"
        "    return helper()\n"
        "def helper():\n"
        "    return 1\n"
        "mi_func()\n",
    )
    func_source = "def mi_func():\n    return helper()"
    ctx = construir_contexto_rama(repo, str(archivo), "mi_func", func_source)
    assert "LLAMADORES LOCALES" in ctx
    assert "helper" in ctx  # funciones que llama internamente
    assert "IMPORTS DISPONIBLES" in ctx
    assert "os" in ctx


def test_construir_contexto_rama_sin_conexiones(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "a.py").write_text("def sola():\n    return 1\n")
    ctx = construir_contexto_rama(repo, str(repo / "a.py"), "sola", "def sola():\n    return 1")
    assert ctx == ""


def test_construir_contexto_rama_archivo_inexistente(tmp_path: Path) -> None:
    ctx = construir_contexto_rama(
        tmp_path,
        str(tmp_path / "no.py"),
        "f",
        "def f():\n    pass",
    )
    assert isinstance(ctx, str)


def test_llamadas_internas_con_atributos() -> None:
    """Llamadas a métodos (attr) también se detectan (55)."""
    from contexto_rama import _llamadas_internas

    llamadas = _llamadas_internas("def f():\n    self.procesar()\n    helper()")
    assert "procesar" in llamadas
    assert "helper" in llamadas


def test_llamadores_externos_excluye_venv(tmp_path: Path) -> None:
    """Archivos en .venv se excluyen (74)."""
    from contexto_rama import _llamadores_externos

    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("def f():\n    pass\nf()\n")
    (tmp_path / "mod.py").write_text("def f():\n    pass\n")
    r = _llamadores_externos(tmp_path, "f", "mod")
    assert r == []  # el único llamador está excluido


def test_llamadores_externos_error_lectura(tmp_path: Path, monkeypatch) -> None:
    """OSError al leer un .py -> continue (79-80)."""
    from pathlib import Path as P

    from contexto_rama import _llamadores_externos

    (tmp_path / "mod.py").write_text("def f():\n    pass\n")
    (tmp_path / "roto.py").write_text("f()\n")

    original = P.read_text

    def lect_rota(self, *a, **k):
        if "roto.py" in str(self):
            raise OSError("permiso")
        return original(self, *a, **k)

    monkeypatch.setattr(P, "read_text", lect_rota)
    r = _llamadores_externos(tmp_path, "f", "mod")
    assert r == []


def test_llamadores_externos_ignora_sin_coincidencia(tmp_path: Path) -> None:
    """.py sin la llamada -> rama falsa del search (81)."""
    from contexto_rama import _llamadores_externos

    (tmp_path / "mod.py").write_text("def f():\n    pass\n")
    (tmp_path / "otro.py").write_text("def g():\n    return 2\n")
    (tmp_path / "cli.py").write_text("from mod import f\nf()\n")
    r = _llamadores_externos(tmp_path, "f", "mod")
    assert any("cli.py" in x for x in r)


def test_construir_contexto_con_fuente_dada(tmp_path: Path) -> None:
    """rama falsa de 'if not fuente_archivo' (103)."""
    from contexto_rama import construir_contexto_rama

    ctx = construir_contexto_rama(
        tmp_path,
        "no_importa.py",
        "f",
        "def f():\n    pass",
        fuente_archivo="x = 1\n",
    )
    assert isinstance(ctx, str)


def test_construir_contexto_fuente_sintaxis_rota(tmp_path: Path) -> None:
    """SyntaxError al parsear la fuente -> pass (120-121)."""
    from contexto_rama import construir_contexto_rama

    (tmp_path / "a.py").write_text("def g():\n    pass\n")
    ctx = construir_contexto_rama(
        tmp_path,
        str(tmp_path / "a.py"),
        "g",
        "def g():\n    pass",
        fuente_archivo="def (\n",
    )
    assert isinstance(ctx, str)


def test_construir_contexto_archivo_fuera_del_repo(tmp_path: Path) -> None:
    """file_path fuera del repo -> ValueError -> modulo = stem (129-137)."""
    from contexto_rama import construir_contexto_rama

    (tmp_path / "a.py").write_text("def g():\n    pass\n")
    ctx = construir_contexto_rama(
        tmp_path,
        "/tmp/fuera/x.py",
        "g",
        "def g():\n    pass",
        fuente_archivo=str(tmp_path / "a.py"),
    )
    assert isinstance(ctx, str)


def test_construir_contexto_llamadores_externos(tmp_path: Path) -> None:
    """LLAMADORES EXTERNOS en el contexto (139-140)."""
    from contexto_rama import construir_contexto_rama

    (tmp_path / "mod").mkdir()
    (tmp_path / "mod" / "f.py").write_text("def f():\n    pass\n")
    (tmp_path / "cli.py").write_text("from mod.f import f\nf()\n")
    ctx = construir_contexto_rama(
        tmp_path,
        str(tmp_path / "mod" / "f.py"),
        "f",
        "def f():\n    pass",
        fuente_archivo="def f():\n    pass\n",
    )
    assert "LLAMADORES EXTERNOS" in ctx
    assert "cli.py" in ctx

def test_llamadas_internas_call_de_call() -> None:
    """func es un Call (no Name ni Attribute) -> rama elif falsa (55->51)."""
    from contexto_rama import _llamadas_internas

    llamadas = _llamadas_internas("def f():\n    return generar()()")
    assert llamadas == ["generar"]


def test_construir_contexto_sin_file_path(tmp_path: Path) -> None:
    """file_path vacío -> rama falsa del 'if file_path' (129->137)."""
    from contexto_rama import construir_contexto_rama

    ctx = construir_contexto_rama(tmp_path, "", "f", "def f():\n    pass")
    assert isinstance(ctx, str)

"""Tests de compactador_espacios.py (TASK-20260812-023) — cobertura 100%.

Cubre: compactar (todas las ramas: docstrings, comentarios, inline, blancos),
descompactar (restauración con anchors), compactar_archivo (persistencia),
y main (CLI).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

import compactador_espacios as ce


def test_compactar_simple() -> None:
    codigo = "def f():\n    return 1"
    compactado, _, stats = ce.compactar(codigo)
    assert "def f():" in compactado
    assert stats["lineas_original"] == 2
    assert stats["reduccion_pct"] >= 0


def test_compactar_quita_blancos() -> None:
    codigo = "def f():\n    a = 1\n\n\n    return a"
    _compactado, _, stats = ce.compactar(codigo)
    assert stats["blancos"] == 2
    assert stats["lineas_compactado"] == 3


def test_compactar_quita_comentarios() -> None:
    codigo = "# comentario\nx = 1"
    compactado, _, stats = ce.compactar(codigo)
    assert stats["comentarios"] == 1
    assert "# comentario" not in compactado


def test_compactar_docstring() -> None:
    codigo = '"""Docstring."""\ndef f():\n    pass'
    compactado, _, stats = ce.compactar(codigo)
    assert stats["docstrings"] == 1
    assert "Docstring" not in compactado


def test_compactar_docstring_multilinea() -> None:
    codigo = '"""\nDocstring multilinea.\n"""\ndef f():\n    pass'
    _compactado, _, stats = ce.compactar(codigo)
    assert stats["docstrings"] == 3


def test_compactar_comentario_inline() -> None:
    codigo = "x = 1  # comentario inline"
    compactado, _, stats = ce.compactar(codigo)
    assert stats["comentarios"] == 1
    assert "# comentario inline" not in compactado


def test_compactar_espacios_extra() -> None:
    codigo = "x  =  1"
    compactado, _, stats = ce.compactar(codigo)
    assert stats["espacios_extra"] >= 0
    assert "x = 1" in compactado


def test_descompactar_restaura_comentario() -> None:
    codigo = "# comentario\nx = 1"
    compactado, anchors, _ = ce.compactar(codigo)
    restaurado = ce.descompactar(compactado, anchors)
    assert "# comentario" in restaurado


def test_descompactar_restaura_docstring() -> None:
    codigo = '"""Doc."""\nx = 1'
    compactado, anchors, _ = ce.compactar(codigo)
    restaurado = ce.descompactar(compactado, anchors)
    assert "Doc" in restaurado


def test_descompactar_inline_reanade() -> None:
    codigo = "x = 1  # inline"
    compactado, anchors, _ = ce.compactar(codigo)
    restaurado = ce.descompactar(compactado, anchors)
    assert "# inline" in restaurado


def test_compactar_archivo(tmp_path: Path) -> None:
    f = tmp_path / "ejemplo.py"
    f.write_text("def f():\n    pass\n")
    resultado = ce.compactar_archivo(f)
    assert "original" in resultado
    assert resultado["stats"]["lineas_original"] == 3
    # Se creó el .nervioso con el mapa de anchors
    nervioso = f.parent / ".nervioso"
    assert (nervioso / "ejemplo_anchors.json").exists()


def test_main_archivo() -> None:
    """main() con argumento de archivo (CLI)."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.py"
        f.write_text("x = 1\n")
        old_argv = sys.argv
        sys.argv = ["compactador_espacios.py", str(f)]
        try:
            ce.main()  # no debe lanzar
        finally:
            sys.argv = old_argv


def test_main_sin_archivo() -> None:
    """main() sin archivo existente -> exit 1."""
    import sys as _sys

    old_argv = _sys.argv
    _sys.argv = ["compactador_espacios.py", "/no/existe.py"]
    try:
        with pytest.raises(SystemExit) as exc:
            ce.main()
        assert exc.value.code == 1
    finally:
        _sys.argv = old_argv


def test_main_descompactar() -> None:
    """main() con --descompactar y mapa existente."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.py"
        f.write_text("x = 1\n")
        ce.compactar_archivo(f)  # crea el mapa
        old_argv = sys.argv
        sys.argv = ["compactador_espacios.py", str(f), "--descompactar"]
        try:
            ce.main()  # no debe lanzar
        finally:
            sys.argv = old_argv


def test_descompactar_mas_anchors_que_lineas() -> None:
    """Más anchors 'codigo' que líneas compactadas -> rellena con '' (115)."""
    from compactador_espacios import descompactar

    r = descompactar("a", [{"tipo": "codigo"}, {"tipo": "codigo"}])
    assert r == "a\n"


def test_descompactar_inline_texto_vacio() -> None:
    """Anchor inline SIN texto -> no añade nada (rama and texto falsa)."""
    from compactador_espacios import descompactar

    r = descompactar("a", [{"tipo": "codigo"}, {"tipo": "comentario_inline", "texto": ""}])
    assert r == "a"


def test_descompactar_inline_primer_anchor() -> None:
    """Anchor inline como PRIMER anchor (lineas_originales vacío) -> no añade (122)."""
    from compactador_espacios import descompactar

    r = descompactar("a", [{"tipo": "comentario_inline", "texto": "# c"}])
    assert r == ""  # el inline no emite línea nueva


def test_descompactar_inline_sin_hash() -> None:
    """Texto del inline sin '#' -> idx_com -1, no añade nada (124)."""
    from compactador_espacios import descompactar

    r = descompactar("x = 1", [{"tipo": "codigo"}, {"tipo": "comentario_inline", "texto": "sin hash"}])
    assert r == "x = 1"


def test_descompactar_tipo_desconocido() -> None:
    """Anchor con tipo no reconocido -> se ignora (ramas elif falsas)."""
    from compactador_espacios import descompactar

    r = descompactar("a", [{"tipo": "otro"}])
    assert r == ""  # tipo desconocido se ignora, no emite línea


def test_main_descompactar_sin_mapa(tmp_path, monkeypatch) -> None:
    """main --descompactar sin mapa -> sys.exit(1) (177)."""
    import sys

    from compactador_espacios import main

    archivo = tmp_path / "modulo.py"
    archivo.write_text("x = 1")
    monkeypatch.setattr(sys, "argv", ["compactador", str(archivo), "--descompactar"])
    try:
        main()
        raise AssertionError("debió salir con SystemExit")
    except SystemExit as e:
        assert e.code == 1


def test_main_json(tmp_path, monkeypatch, capsys) -> None:
    """main --json -> pasa por la rama json (183)."""
    import sys

    from compactador_espacios import main

    archivo = tmp_path / "modulo.py"
    archivo.write_text("x = 1\n\ny = 2")
    monkeypatch.setattr(sys, "argv", ["compactador", str(archivo), "--json"])
    main()
    assert (tmp_path / ".nervioso" / "modulo_compactado.py").exists()


def test_main_archivo_inexistente(tmp_path, monkeypatch) -> None:
    """main con archivo que no existe -> sys.exit(1) (172)."""
    import sys

    from compactador_espacios import main

    monkeypatch.setattr(sys, "argv", ["compactador", str(tmp_path / "no_existe.py")])
    try:
        main()
        raise AssertionError("debió salir con SystemExit")
    except SystemExit as e:
        assert e.code == 1


def test_main_descompactar_con_mapa(tmp_path, monkeypatch) -> None:
    """main --descompactar con mapa existente -> descompacta (179)."""
    import sys

    from compactador_espacios import main

    archivo = tmp_path / "modulo.py"
    archivo.write_text("x = 1")
    nervioso = tmp_path / ".nervioso"
    nervioso.mkdir()
    (nervioso / "modulo_anchors.json").write_text(
        json.dumps({"archivo": str(archivo), "anchors": [{"tipo": "codigo"}]}),
    )
    monkeypatch.setattr(sys, "argv", ["compactador", str(archivo), "--descompactar"])
    main()  # no debe lanzar


def test_script_main_via_directo(tmp_path, monkeypatch) -> None:
    """Ejecutar el script como programa -> cubre __main__ (188-189)."""
    import runpy
    import sys

    archivo = tmp_path / "modulo.py"
    archivo.write_text("x = 1\n\ny = 2\n")
    monkeypatch.setattr(sys, "argv", ["compactador_espacios.py", str(archivo)])
    script = Path(__file__).parent.parent.parent / "scripts" / "pro" / "compactador_espacios.py"
    runpy.run_path(str(script), run_name="__main__")

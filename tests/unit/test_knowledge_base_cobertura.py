"""Cobertura 100x100 de knowledge/engine/knowledge_base.py (TASK-20260815-003, P2).

Generación MkDocs desde el grafo: sanitización de nombres/markdown, verificación
de enlaces, manifest incremental, escritura atómica con swap, y generación
end-to-end con BD sqlite real en tmp_path. Mocks FakeConn/FakeRow por
subcadena SQL + params para las rutas de grafo.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from knowledge.engine import knowledge_base as kb


class FakeRow(dict):
    """Fila sqlite3.Row simulada con acceso por clave."""


class FakeConn:
    """Conexión sqlite simulada. Coincide por subcadena SQL."""

    def __init__(self, results: dict[str, Any]) -> None:
        self._results = results
        self.executed: list[str] = []
        self.closed = False
        self._current: Any = None

    def execute(self, sql: str, params: Any = ()) -> FakeConn:
        self.executed.append(sql)
        self._current = None
        for key, val in self._results.items():
            if key in sql:
                self._current = val
                break
        return self

    def fetchone(self) -> Any:
        return self._current

    def fetchall(self) -> Any:
        return self._current if self._current is not None else []

    def close(self) -> None:
        self.closed = True


def _row(**vals: Any) -> FakeRow:
    return FakeRow(vals)


class TestSanitizeFilename:
    def test_normal(self) -> None:
        assert kb._sanitize_filename("My Doc") == "my_doc"

    def test_especiales(self) -> None:
        assert kb._sanitize_filename("A/B?C:D*E") == "a_b_c_d_e"

    def test_vacio_queda_untitled(self) -> None:
        assert kb._sanitize_filename("___") == "untitled"

    def test_trunca_a_200(self) -> None:
        name = "x" * 500
        assert len(kb._sanitize_filename(name)) == kb._MAX_FILENAME_LENGTH

    def test_mantiene_guiones_y_digitos(self) -> None:
        assert kb._sanitize_filename("Doc-123_abc") == "doc-123_abc"


class TestSafeMarkdown:
    def test_escapa_menor_y_ampersand(self) -> None:
        assert kb._safe_markdown("a < b & c") == "a &lt; b &amp; c"

    def test_no_escapa_otros(self) -> None:
        assert kb._safe_markdown('> y "comillas" y \'ap\'') == '> y "comillas" y \'ap\''

    def test_preserva_bloques_codigo(self) -> None:
        text = "```python\nif a < b: pass\n```"
        assert kb._safe_markdown(text) == "```python\nif a &lt; b: pass\n```"

    def test_preserva_entidades_html(self) -> None:
        assert kb._safe_markdown("&#169; &copy;") == "&#169; &copy;"

    def test_corrige_doble_escape(self) -> None:
        assert kb._safe_markdown("&amp;lt;") == "&lt;"

    def test_entidades_numericas_preservadas(self) -> None:
        assert kb._safe_markdown("x &#8212; y") == "x &#8212; y"


class TestVerifyLinks:
    def test_sin_enlaces(self) -> None:
        assert kb._verify_links("texto sin enlaces", {"a"}) == []

    def test_enlace_valido(self) -> None:
        content = "ver (aabbccddeeff.md) y (112233445566.md)"
        assert kb._verify_links(content, {"aabbccddeeff", "112233445566"}) == []

    def test_enlace_roto(self) -> None:
        content = "roto (000000000000.md) y (aabbccddeeff.md)"
        assert kb._verify_links(content, {"aabbccddeeff"}) == ["000000000000"]

    def test_no_confunde_no_enlace(self) -> None:
        assert kb._verify_links("(no es hex).md", set()) == []


class TestManifest:
    def test_load_sin_archivo(self, tmp_path: Path) -> None:
        assert kb._load_manifest(tmp_path) == {}

    def test_load_valido(self, tmp_path: Path) -> None:
        meta = tmp_path / ".meta"
        meta.mkdir()
        (meta / "manifest.json").write_text(json.dumps({"a": "h1"}))
        assert kb._load_manifest(tmp_path) == {"a": "h1"}

    def test_load_corrupto(self, tmp_path: Path) -> None:
        meta = tmp_path / ".meta"
        meta.mkdir()
        (meta / "manifest.json").write_text("{not json")
        assert kb._load_manifest(tmp_path) == {}

    def test_load_error_oserror(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = tmp_path / ".meta"
        meta.mkdir()
        f = meta / "manifest.json"
        f.write_text("{}")

        def boom(_self: Path) -> str:
            raise OSError("io")

        monkeypatch.setattr(Path, "read_text", boom)
        assert kb._load_manifest(tmp_path) == {}

    def test_save_crea_archivo(self, tmp_path: Path) -> None:
        kb._save_manifest(tmp_path, {"b": "h2", "a": "h1"})
        manifest_file = tmp_path / ".meta" / "manifest.json"
        assert manifest_file.exists()
        assert json.loads(manifest_file.read_text()) == {"a": "h1", "b": "h2"}


class TestContentHash:
    def test_sha256_estable(self) -> None:
        h1 = kb._content_hash("hola")
        assert h1 == kb._content_hash("hola")
        assert len(h1) == 64
        assert h1 != kb._content_hash("hola2")


class TestGenerateKnowledgeBase:
    def test_bd_vacia_devuelve_cero(self, tmp_path: Path) -> None:
        db = tmp_path / "grafo.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE kg_nodes (id TEXT)")
        conn.commit()
        conn.close()
        out = tmp_path / "out"
        assert kb.generate_knowledge_base(db, out) == 0
        assert not out.exists()

    def test_sin_cursor_devuelve_cero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        conn = FakeConn({"SELECT COUNT(*) as c FROM kg_nodes": None})

        def fake_open_db(_path: Any) -> FakeConn:
            return conn

        monkeypatch.setattr("knowledge.engine.connection.open_db", fake_open_db)
        assert kb.generate_knowledge_base(tmp_path / "n.db") == 0
        assert conn.closed

    def test_end_to_end(self, tmp_path: Path) -> None:
        db = tmp_path / "grafo.db"
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE kg_nodes (id TEXT PRIMARY KEY, type TEXT, path TEXT, frontmatter TEXT, body TEXT)"
        )
        conn.execute("CREATE TABLE kg_edges (src TEXT, dst TEXT, relation TEXT)")
        conn.execute(
            "CREATE TABLE op_feedback_agg (doc_id TEXT, avg_rating REAL, n_ratings INTEGER)"
        )
        conn.executemany(
            "INSERT INTO kg_nodes (id, type, path, frontmatter, body) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "aabbccddeeff",
                    "guia",
                    "/docs/guia.md",
                    '{"title": "Guía & <Demo>", "tags": ["core", "v2"]}',
                    "Texto con enlace a (112233445566.md)",
                ),
                (
                    "112233445566",
                    "guia",
                    "/docs/otra.md",
                    '{"title": "Otra"}',
                    "sin enlaces",
                ),
            ],
        )
        conn.execute(
            "INSERT INTO kg_edges (src, dst, relation) VALUES (?, ?, ?)",
            ("aabbccddeeff", "112233445566", "relaciona"),
        )
        conn.execute(
            "INSERT INTO op_feedback_agg (doc_id, avg_rating, n_ratings) VALUES (?, ?, ?)",
            ("112233445566", 4.5, 2),
        )
        conn.commit()
        conn.close()

        out = tmp_path / "kb"
        count = kb.generate_knowledge_base(db, out)
        assert count == 2

        doc_file = out / "guia" / "aabbccddeeff.md"
        assert doc_file.exists()
        content = doc_file.read_text()
        assert "Guía &amp; &lt;Demo>" in content
        assert "## Relaciones" in content
        assert "- [relaciona](112233445566.md)" in content

        otra = out / "guia" / "112233445566.md"
        assert "**Rating:** ⭐⭐⭐⭐ (4.5/5, 2 votes)" in otra.read_text()

        assert (out / "index.md").exists()
        assert (out / "mkdocs.yml").exists()
        manifest = out / ".meta" / "manifest.json"
        assert manifest.exists()
        assert set(json.loads(manifest.read_text())) == {"aabbccddeeff", "112233445566"}


class TestGenerarKnowledgeBase:
    def test_ok_atomico(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        nodes = [
            _row(
                id="aa1122334455",
                type="tipo",
                path="/p/a.md",
                frontmatter='{"title": "A", "tags": ["x"]}',
                body="cuerpo",
            )
        ]
        conn = FakeConn(
            {
                "FROM kg_edges": [_row(src="aa1122334455", dst="bb1122334455", relation="r")],
                "FROM op_feedback_agg": [
                    _row(doc_id="aa1122334455", avg_rating=3.6, n_ratings=3)
                ],
                "FROM kg_nodes ORDER BY": nodes,
            }
        )
        assert kb._generar_knowledge_base(conn, 1, out) == 1
        assert conn.closed
        assert (out / "tipo" / "aa1122334455.md").exists()
        assert (out / ".meta" / "manifest.json").exists()

    def test_excepcion_devuelve_cero(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        class BoomConn:
            def execute(self, sql: str, params: Any = ()) -> BoomConn:
                raise sqlite3.OperationalError("boom")

        with caplog.at_level("ERROR", logger="ura.knowledge.knowledge_base"):
            assert kb._generar_knowledge_base(BoomConn(), 1, tmp_path / "out") == 0
        assert "Knowledge base generation failed" in caplog.text


class TestLogResultado:
    def test_sin_enlaces_rotos(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO", logger="ura.knowledge.knowledge_base"):
            kb._log_resultado(3, 1, Path("/tmp/out"), 0)
        assert "3 docs (1 changed) in /tmp/out" in caplog.text
        assert "broken" not in caplog.text

    def test_con_enlaces_rotos(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO", logger="ura.knowledge.knowledge_base"):
            kb._log_resultado(3, 2, Path("/tmp/out"), 5)
        assert "3 docs (2 changed) in /tmp/out (5 broken links)" in caplog.text


class TestCargarDatosGrafo:
    def test_lee_edges_feedback_y_nodos(self) -> None:
        nodes = [
            _row(id="aa11", type="t", path="/a", frontmatter="{}", body="b"),
            _row(id="bb22", type=None, path="/b", frontmatter=None, body=None),
        ]
        conn = FakeConn(
            {
                "SELECT src, dst, relation FROM kg_edges": [
                    _row(src="aa11", dst="bb22", relation="r1")
                ],
                "SELECT doc_id, avg_rating, n_ratings FROM op_feedback_agg": [
                    _row(doc_id="aa11", avg_rating=2.0, n_ratings=1)
                ],
                "SELECT id, type, path, frontmatter, body FROM kg_nodes ORDER BY": nodes,
            }
        )
        all_ids, by_type = kb._cargar_datos_grafo(conn, 2)
        assert all_ids == {"aa11", "bb22"}
        assert set(by_type) == {"t", "doc"}
        assert by_type["t"][0]["rels"] == ["bb22"]
        assert by_type["doc"][0]["title"] == "bb22"

    def test_batch_vacio_termina_loop(self) -> None:
        conn = FakeConn(
            {
                "FROM kg_edges": [],
                "FROM op_feedback_agg": [],
                "FROM kg_nodes ORDER BY": [],
            }
        )
        all_ids, by_type = kb._cargar_datos_grafo(conn, 1000000)
        assert all_ids == set()
        assert by_type == {}


class TestConstruirDocEntry:
    def test_con_frontmatter_edges_feedback(self) -> None:
        r = _row(
            id="aa11",
            type="t",
            path="/a",
            frontmatter='{"title": "Titulo", "tags": ["t1"]}',
            body="cuerpo",
        )
        entry = kb._construir_doc_entry(
            r,
            {"aa11": [{"dst": "bb22", "relation": "r"}]},
            {"aa11": {"doc_id": "aa11", "avg_rating": 5.0, "n_ratings": 1}},
        )
        assert entry["id"] == "aa11"
        assert entry["title"] == "Titulo"
        assert entry["rels"] == ["bb22"]
        assert "# Titulo" in entry["content"]
        assert "## Relaciones" in entry["content"]

    def test_sin_frontmatter_sin_relaciones(self) -> None:
        r = _row(id="bb22", type="t", path="/b", frontmatter=None, body=None)
        entry = kb._construir_doc_entry(r, {}, {})
        assert entry["title"] == "bb22"
        assert "**Tags:** none" in entry["content"]
        assert "## Relaciones" not in entry["content"]


class TestConstruirRelaciones:
    def test_vacio(self) -> None:
        assert kb._construir_relaciones([]) == ""

    def test_con_relaciones(self) -> None:
        rels = [{"dst": "bb22", "relation": "rel <a>"}, {"dst": "cc33", "relation": "x"}]
        out = kb._construir_relaciones(rels)
        assert out.startswith("\n\n## Relaciones\n")
        assert "- [rel &lt;a>](bb22.md)" in out
        assert "- [x](cc33.md)" in out


class TestConstruirRating:
    def test_none(self) -> None:
        assert kb._construir_rating(None) == ""

    def test_cero_votos(self) -> None:
        assert kb._construir_rating({"n_ratings": 0, "avg_rating": 4.0}) == ""

    def test_positivo(self) -> None:
        out = kb._construir_rating({"n_ratings": 2, "avg_rating": 4.6})
        assert "⭐" * 5 in out
        assert "(4.6/5, 2 votes)" in out


class TestConstruirContent:
    def test_con_tags(self) -> None:
        fm = {"title": "T", "tags": ["a", "b"]}
        r = _row(id="aa11", type="t", path="/p", frontmatter=None, body=None)
        out = kb._construir_content("aa11", "t", "T", fm, r, "cuerpo", "", "")
        assert "**Tags:** a, b" in out
        assert "# T" in out
        assert "*Generated by Knowledge Engine v0.2.0*" in out

    def test_sin_tags(self) -> None:
        fm: dict[str, Any] = {}
        r = _row(id="aa11", type="t", path="/p", frontmatter=None, body=None)
        out = kb._construir_content("aa11", "t", "T", fm, r, "", "", "")
        assert "**Tags:** none" in out
        assert "cuerpo" not in out


class TestEscribirDocs:
    def _by_type(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "zeta": [
                {
                    "id": "zz11",
                    "title": "Zeta",
                    "content": "contenido z",
                    "path": "/z",
                    "rels": [],
                }
            ],
            "alfa": [
                {
                    "id": "aa11",
                    "title": "Alfa",
                    "content": "contenido a",
                    "path": "/a",
                    "rels": [],
                }
            ],
        }

    def test_escribe_ordenado(self, tmp_path: Path) -> None:
        nav, count, changed = kb._escribir_docs(tmp_path, self._by_type(), {}, {})
        assert count == 2
        assert changed == 2
        assert [next(iter(e)) for e in nav] == ["alfa", "zeta"]
        assert (tmp_path / "alfa" / "aa11.md").read_text() == "contenido a"

    def test_documento_sin_cambios_no_reescribe(self, tmp_path: Path) -> None:
        prev = {"aa11": kb._content_hash("contenido a"), "zz11": "otro"}
        _nav, count, changed = kb._escribir_docs(tmp_path, self._by_type(), prev, {})
        assert count == 2
        assert changed == 1
        assert not (tmp_path / "alfa" / "aa11.md").exists()
        assert (tmp_path / "zeta" / "zz11.md").exists()


class TestVerificarEnlaces:
    def test_sin_rotos(self) -> None:
        by_type = {"t": [{"id": "aa11", "content": "ok (bb22cc33dd44.md)"}]}
        assert kb._verificar_enlaces(by_type, {"bb22cc33dd44"}) == 0

    def test_con_rotos(self, caplog: pytest.LogCaptureFixture) -> None:
        by_type = {"t": [{"id": "aa11", "content": "roto (000000000000.md) y (111111111111.md)"}]}
        with caplog.at_level("WARNING", logger="ura.knowledge.knowledge_base"):
            assert kb._verificar_enlaces(by_type, set()) == 2
        assert "Broken links in doc aa11" in caplog.text


class TestEscribirConfigMkdocs:
    def test_genera_yml_y_manifest(self, tmp_path: Path) -> None:
        nav = [{"tipo": [{"Titulo": "tipo/aa11.md"}]}]
        kb._escribir_config_mkdocs(tmp_path, nav, {"aa11": "h1"})
        yml = (tmp_path / "mkdocs.yml").read_text()
        assert "site_name: Knowledge Base" in yml
        assert "aa11" in (tmp_path / ".meta" / "manifest.json").read_text()


class TestEscribirIndex:
    def test_index_ordenado(self, tmp_path: Path) -> None:
        by_type = {
            "zeta": [{"id": "zz11", "title": "Zeta", "path": "/z"}],
            "alfa": [
                {"id": "bb22", "title": "Beta", "path": "/b"},
                {"id": "aa11", "title": "Alfa", "path": "/a"},
            ],
        }
        kb._escribir_index(tmp_path, by_type, 3)
        idx = (tmp_path / "index.md").read_text()
        assert "**3 documents**" in idx
        assert idx.index("### Alfa") < idx.index("### Zeta")
        assert "- [Alfa](alfa/aa11.md)" in idx
        assert "- [Beta](alfa/bb22.md)" in idx


class TestSwapAtomico:
    def test_sin_destino_previo(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        dest = tmp_path / "tmp" / "docs"
        dest.mkdir(parents=True)
        (dest / "f.md").write_text("x")
        kb._swap_atomico(out, dest)
        assert (out / "f.md").exists()
        assert not dest.exists()
        assert not (tmp_path / "out.bak").exists()

    def test_con_destino_previo(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        out.mkdir()
        (out / "old.md").write_text("old")
        dest = tmp_path / "tmp" / "docs"
        dest.mkdir(parents=True)
        (dest / "new.md").write_text("new")
        kb._swap_atomico(out, dest)
        assert (out / "new.md").exists()
        assert not (out / "old.md").exists()
        assert not (tmp_path / "out.bak").exists()

    def test_con_backup_previo_eliminado(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        out.mkdir()
        (out / "old.md").write_text("old")
        backup = tmp_path / "out.bak"
        backup.mkdir()
        (backup / "stale.md").write_text("stale")
        dest = tmp_path / "tmp" / "docs"
        dest.mkdir(parents=True)
        (dest / "new.md").write_text("new")
        kb._swap_atomico(out, dest)
        assert (out / "new.md").exists()
        assert not backup.exists()

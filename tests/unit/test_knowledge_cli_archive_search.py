"""Tests para knowledge/engine/cli/ — archive y search."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from knowledge.engine.cli.archive import (
    cmd_archive_list,
    cmd_archive_restore,
    cmd_archive_source,
    cmd_archive_verify,
)
from knowledge.engine.cli.search import cmd_read, cmd_related, cmd_search


class TestCmdArchiveSource:
    def test_ok_con_todo(self, monkeypatch, tmp_path) -> None:
        archiver = mock.Mock()
        monkeypatch.setattr("knowledge.engine.archiver.archive_source", archiver)
        args = SimpleNamespace(
            source_dir=str(tmp_path / "src"),
            archive_dir=str(tmp_path / "arc"),
            retention_days=30,
            db_path=str(tmp_path / "db.sqlite"),
        )
        assert cmd_archive_source(args) == 0
        archiver.assert_called_once()
        assert archiver.call_args.kwargs["retention_days"] == 30

    def test_ok_sin_opcionales(self, monkeypatch, tmp_path) -> None:
        archiver = mock.Mock()
        monkeypatch.setattr("knowledge.engine.archiver.archive_source", archiver)
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
        assert cmd_archive_source(args) == 0
        assert archiver.call_args.kwargs["source_dir"] is None
        assert archiver.call_args.kwargs["retention_days"] is None


class TestCmdArchiveList:
    def test_vacio(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.archiver.list_archives", mock.Mock(return_value=[]))
        args = SimpleNamespace(archive_dir=str(tmp_path / "arc"))
        assert cmd_archive_list(args) == 0

    def test_con_manifests(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.archiver.list_archives", mock.Mock(return_value=[mock.Mock(), mock.Mock()]))
        args = SimpleNamespace(archive_dir=str(tmp_path / "arc"))
        assert cmd_archive_list(args) == 0


class TestCmdArchiveVerify:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.archiver.verify_archive", mock.Mock(return_value=True))
        args = SimpleNamespace(manifest="m1.json", archive_dir=str(tmp_path / "arc"))
        assert cmd_archive_verify(args) == 0

    def test_falla(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.archiver.verify_archive", mock.Mock(return_value=False))
        args = SimpleNamespace(manifest="m1.json", archive_dir=str(tmp_path / "arc"))
        assert cmd_archive_verify(args) == 1


class TestCmdArchiveRestore:
    def test_ok_con_dest(self, monkeypatch, tmp_path) -> None:
        restore = mock.Mock()
        monkeypatch.setattr("knowledge.engine.archiver.restore_source", restore)
        args = SimpleNamespace(manifest="m1.json", dest=str(tmp_path / "dest"), archive_dir=str(tmp_path / "arc"), db_path=str(tmp_path / "db.sqlite"))
        assert cmd_archive_restore(args) == 0
        assert restore.call_args.kwargs["dest_dir"] == tmp_path / "dest"

    def test_ok_sin_dest(self, monkeypatch, tmp_path) -> None:
        restore = mock.Mock()
        monkeypatch.setattr("knowledge.engine.archiver.restore_source", restore)
        args = SimpleNamespace(manifest="m1.json", dest=None, archive_dir=None, db_path=str(tmp_path / "db.sqlite"))
        assert cmd_archive_restore(args) == 0
        assert restore.call_args.kwargs["dest_dir"] is None


class TestCmdRead:
    def test_db_no_existe(self, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"), doc_id="d1")
        assert cmd_read(args) == 1

    def test_doc_no_encontrado(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.get_document.return_value = None
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        args = SimpleNamespace(db_path=str(db), doc_id="d1")
        assert cmd_read(args) == 1

    def test_ok(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.get_document.return_value = mock.Mock(body="contenido del doc")
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(db), doc_id="d1")
            assert cmd_read(args) == 0


class TestCmdSearch:
    def test_db_no_existe(self, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"), query="q")
        assert cmd_search(args) == 1

    def test_ok_con_filtros(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.search.return_value = [mock.Mock(doc_id="d1", snippet="snippet corto")]
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(db), query="q", type="doc", mode="hybrid", limit=5)
            assert cmd_search(args) == 0
        reader.search.assert_called_once_with("q", mode="hybrid", filters={"type": "doc"}, limit=5)

    def test_sin_resultados(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.search.return_value = []
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        args = SimpleNamespace(db_path=str(db), query="q")
        assert cmd_search(args) == 0


class TestCmdRelated:
    def test_db_no_existe(self, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "nope.sqlite"), doc_id="d1")
        assert cmd_related(args) == 1

    def test_ok(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.related.return_value = [mock.Mock(src="a", dst="b", relation="related")]
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(db), doc_id="d1")
            assert cmd_related(args) == 0

    def test_sin_relacionados(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.related.return_value = []
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        with mock.patch("builtins.print"):
            args = SimpleNamespace(db_path=str(db), doc_id="d1")
            assert cmd_related(args) == 0

    def test_error(self, monkeypatch, tmp_path) -> None:
        db = tmp_path / "db.sqlite"
        db.write_bytes(b"x")
        reader = mock.Mock()
        reader.related.side_effect = OSError("boom")
        monkeypatch.setattr("knowledge.engine.cli.search.KnowledgeReader", mock.Mock(return_value=reader))
        args = SimpleNamespace(db_path=str(db), doc_id="d1")
        assert cmd_related(args) == 1

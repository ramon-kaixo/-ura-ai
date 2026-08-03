"""Tests para knowledge/engine/cli/metadata.py."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from knowledge.engine.cli.metadata import (
    cmd_memory_create,
    cmd_memory_link,
    cmd_memory_list,
    cmd_memory_search,
    cmd_memory_show,
    cmd_metadata_context,
    cmd_metadata_lineage,
    cmd_metadata_policy,
    cmd_metadata_retrieve,
)


class TestCmdMetadataLineage:
    def test_sin_eventos(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.get_lineage.return_value = []
        monkeypatch.setattr("knowledge.engine.lineage_store.SQLiteLineageStore", mock.Mock(return_value=store))
        args = SimpleNamespace(asset_id="a1", db_path=str(tmp_path / "db.sqlite"))
        assert cmd_metadata_lineage(args) == 0
        store.get_upstream.assert_not_called()

    def test_con_eventos(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.get_lineage.return_value = [mock.Mock(), mock.Mock()]
        store.get_upstream.return_value = [mock.Mock()]
        store.get_downstream.return_value = []
        monkeypatch.setattr("knowledge.engine.lineage_store.SQLiteLineageStore", mock.Mock(return_value=store))
        args = SimpleNamespace(asset_id="a1", db_path=str(tmp_path / "db.sqlite"))
        assert cmd_metadata_lineage(args) == 0
        store.get_upstream.assert_called_once()
        store.get_downstream.assert_called_once()


class TestCmdMetadataPolicy:
    def test_sin_asset(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.list_policies.return_value = []
        monkeypatch.setattr("knowledge.engine.governance_store.SQLiteGovernanceStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
        assert cmd_metadata_policy(args) == 0
        store.list_policies.assert_called_once()

    def test_con_asset(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.get_policies.return_value = [mock.Mock()]
        monkeypatch.setattr("knowledge.engine.governance_store.SQLiteGovernanceStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), asset_id="a1")
        assert cmd_metadata_policy(args) == 0
        store.get_policies.assert_called_once_with("a1")


class TestCmdMemoryCreate:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.save.return_value = True
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), kind="idea", title="t", content="c", tags="a, b, c")
        assert cmd_memory_create(args) == 0
        rec = store.save.call_args.args[0]
        assert rec.kind == "idea"
        assert rec.tags == ("a", "b", "c")

    def test_sin_tags(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.save.return_value = True
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), kind="idea", title="t", content="c", tags="")
        assert cmd_memory_create(args) == 0
        assert store.save.call_args.args[0].tags == ()

    def test_falla(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.save.return_value = False
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), kind="k", title="t", content="c", tags="")
        assert cmd_memory_create(args) == 1


class TestCmdMemoryList:
    def test_vacio(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.list.return_value = []
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), kind=None, limit=50)
        assert cmd_memory_list(args) == 0
        store.list.assert_called_once_with(kind=None, limit=50)

    def test_con_resultados(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.list.return_value = [mock.Mock()]
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), kind="idea", limit=10)
        assert cmd_memory_list(args) == 0


class TestCmdMemoryShow:
    def test_no_encontrado(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.get.return_value = None
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), memory_id="m1")
        assert cmd_memory_show(args) == 1

    def test_encontrado(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.get.return_value = mock.Mock()
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), memory_id="m1")
        assert cmd_memory_show(args) == 0


class TestCmdMemorySearch:
    def test_sin_resultados(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.search.return_value = []
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), query="q", kind=None, limit=5)
        assert cmd_memory_search(args) == 0

    def test_con_resultados(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.search.return_value = [mock.Mock()]
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), query="q", kind="idea", limit=10)
        assert cmd_memory_search(args) == 0


class TestCmdMemoryLink:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.link_asset.return_value = True
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), memory_id="m1", asset_id="a1")
        assert cmd_memory_link(args) == 0
        store.link_asset.assert_called_once_with("m1", "a1")

    def test_falla(self, monkeypatch, tmp_path) -> None:
        store = mock.Mock()
        store.link_asset.return_value = False
        monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", mock.Mock(return_value=store))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), memory_id="m1", asset_id="a1")
        assert cmd_memory_link(args) == 1


class TestCmdMetadataRetrieve:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        retriever = mock.Mock()
        ctx = mock.Mock()
        ctx.assets = [mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()]
        retriever.build_context.return_value = ctx
        monkeypatch.setattr("knowledge.engine.graphrag.SQLiteGraphRetriever", mock.Mock(return_value=retriever))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), query="q", limit=8)
        assert cmd_metadata_retrieve(args) == 0
        retriever.build_context.assert_called_once_with(query="q", max_assets=8, max_memories=5)


class TestCmdMetadataContext:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        retriever = mock.Mock()
        monkeypatch.setattr("knowledge.engine.graphrag.SQLiteGraphRetriever", mock.Mock(return_value=retriever))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), query="q")
        assert cmd_metadata_context(args) == 0
        retriever.build_context.assert_called_once_with(query="q", max_assets=20, max_memories=10)

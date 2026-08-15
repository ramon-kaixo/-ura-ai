"""Cobertura 100x100 de motor/core/memory_engine.py (TASK-20260815-003).

Cubre el Memory Engine RAG completo: _get_qdrant (singleton), _sha256
(hashing real en chunks de 8192), _chunk_text (troceado con solape),
persistencia del manifest JSON (load/save con verificación de espacio en
disco), index_documents (nuevo/modificado/unchanged/eliminado/force/
degradación), _escanear_archivos, _construir_batch, query con filtro por
similitud, get_sources, _chromadb_available, rag_enabled, _build_context,
_generate, ask y todos los fallos (Qdrant no disponible, JSON corrupto,
errores de lectura/escritura, batches fallidos, espacio insuficiente).

Las dependencias externas (Qdrant, sistema de archivos, LLM) se aíslan con
monkeypatch; el comportamiento lógico (hashing, serialización, chunking,
filtrado, estadísticas) es el real del módulo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from motor.core import memory_engine as me
from motor.core.memory_engine import (
    _build_context,
    _chromadb_available,
    _chunk_text,
    _construir_batch,
    _generate,
    _get_qdrant,
    _procesar_eliminados,
    _sha256,
    ask,
    get_sources,
    index_documents,
    load_manifest,
    query,
    rag_enabled,
    save_manifest,
)


class FakeQdrant:
    """Cliente Qdrant simulado con inyectores de fallo."""

    def __init__(self, disponible: bool = True) -> None:
        self.disponible = disponible
        self.saved_batches: list[list[Any]] = []
        self.deleted_filters: list[dict[str, Any]] = []
        self.search_results: list[dict[str, Any]] = []
        self.search_limits: list[int] = []
        self.fail_batch = False
        self.fail_delete = False
        self.fail_search = False

    def guardar_documentos_batch(self, docs: list[Any]) -> int:
        """Guarda y devuelve el número de documentos recibidos."""
        if self.fail_batch:
            raise RuntimeError("upsert fail")
        self.saved_batches.append(docs)
        return len(docs)

    def eliminar_por_filtro(self, filtro: dict[str, Any]) -> bool:
        """Registra el filtro de borrado."""
        if self.fail_delete:
            raise RuntimeError("delete fail")
        self.deleted_filters.append(filtro)
        return True

    def buscar_documentos(self, question: str, limit: int = 5) -> list[dict[str, Any]]:
        """Registra el límite y devuelve resultados prefijados."""
        if self.fail_search:
            raise RuntimeError("search fail")
        self.search_limits.append(limit)
        return self.search_results


class FakeMotorQdrant:
    """Sustituto de motor.core.qdrant_client.QdrantClient para _get_qdrant."""

    inst: Any = None

    @classmethod
    def instancia(cls, config: Any) -> Any:
        """Devuelve la instancia prefijada sin conexión real."""
        return cls.inst


def _fake_manifest() -> dict[str, Any]:
    """Manifest vacío en el formato real del módulo."""
    return {"indexed_at": None, "total_documents": 0, "total_chunks": 0, "files": {}}


def _capture_log(monkeypatch: pytest.MonkeyPatch, method: str) -> list[str]:
    """Reemplaza un método del logger por un registrador de argumentos."""
    calls: list[str] = []

    def _record(*args: Any, **kwargs: Any) -> None:
        calls.append(str(args))

    monkeypatch.setattr(me.log, method, _record)
    return calls


@pytest.fixture(autouse=True)
def _fresh_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reinicia el singleton _qdrant para que cada test parta de cero."""
    monkeypatch.setattr(me, "_qdrant", None)


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirige DATA_DIR/DOCS_DIR/MANIFEST_PATH a un árbol temporal."""
    data = tmp_path / "data"
    docs = data / "documentos"
    manifest = data / ".index_manifest.json"
    monkeypatch.setattr(me, "DATA_DIR", data)
    monkeypatch.setattr(me, "DOCS_DIR", docs)
    monkeypatch.setattr(me, "MANIFEST_PATH", manifest)
    return {"data": data, "docs": docs, "manifest": manifest}


class TestGetQdrant:
    """_get_qdrant: singleton perezoso del cliente Qdrant."""

    def test_crea_instancia_cuando_es_nula(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant()
        FakeMotorQdrant.inst = fake
        monkeypatch.setattr(me.UraConfig, "load", staticmethod(lambda: object()))
        monkeypatch.setattr(me, "QdrantClient", FakeMotorQdrant)

        result = _get_qdrant()

        assert result is fake
        assert me._qdrant is fake

    def test_reutiliza_instancia_existente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant()
        me._qdrant = fake
        calls: list[Any] = []
        monkeypatch.setattr(
            me,
            "QdrantClient",
            type("Fake", (), {"instancia": classmethod(lambda cls, config: calls.append(config))}),
        )

        result = _get_qdrant()

        assert result is fake
        assert calls == []


class TestSha256:
    """_sha256: hash SHA-256 real de archivos en chunks de 8192."""

    def test_hash_archivo_multichunk(self, tmp_path: Path) -> None:
        p = tmp_path / "bin.dat"
        data = b"ab" * 20000
        p.write_bytes(data)

        digest = _sha256(p)

        expected = hashlib.sha256(data).hexdigest()
        assert digest == expected
        assert len(digest) == 64

    def test_hash_archivo_vacio(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.txt"
        p.write_bytes(b"")

        assert _sha256(p) == hashlib.sha256(b"").hexdigest()


class TestChunkText:
    """_chunk_text: troceado por palabras con solape."""

    def test_texto_corto_devuelve_tal_cual(self) -> None:
        text = "hola mundo"

        assert _chunk_text(text, size=5, overlap=2) == [text]

    def test_texto_con_tantas_palabras_como_size(self) -> None:
        text = "a b c d e"

        assert _chunk_text(text, size=5, overlap=2) == [text]

    def test_texto_largo_se_trocea_con_solape(self) -> None:
        words = [f"w{i}" for i in range(12)]
        text = " ".join(words)

        chunks = _chunk_text(text, size=5, overlap=2)

        assert [len(c.split()) for c in chunks] == [5, 5, 5, 3]
        assert chunks[0] == " ".join(words[:5])
        assert chunks[1] == " ".join(words[3:8])
        assert chunks[-1].endswith(words[-1])

    def test_overlap_cero_trocea_contiguo(self) -> None:
        chunks = _chunk_text(" ".join(f"w{i}" for i in range(6)), size=2, overlap=0)

        assert chunks == ["w0 w1", "w2 w3", "w4 w5"]

    def test_palabra_unica(self) -> None:
        assert _chunk_text("solo", size=5, overlap=2) == ["solo"]


class TestLoadManifest:
    """load_manifest: lectura del manifest de índice."""

    def test_sin_archivo_devuelve_vacio(self) -> None:
        assert load_manifest() == {
            "indexed_at": None,
            "total_documents": 0,
            "total_chunks": 0,
            "files": {},
        }

    def test_archivo_valido(self, paths: dict[str, Path]) -> None:
        paths["data"].mkdir(parents=True)
        manifest = {"indexed_at": "2026-08-15T10:00:00+00:00", "total_documents": 1, "total_chunks": 2, "files": {"a.txt": {"sha256": "x"}}}
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")

        assert load_manifest() == manifest

    def test_json_corrupto_devuelve_vacio_y_avisa(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["data"].mkdir(parents=True)
        paths["manifest"].write_text("{no-json", encoding="utf-8")
        warnings = _capture_log(monkeypatch, "warning")

        result = load_manifest()

        assert result == {
            "indexed_at": None,
            "total_documents": 0,
            "total_chunks": 0,
            "files": {},
        }
        assert len(warnings) == 1


class TestSaveManifest:
    """save_manifest: escritura con verificación de espacio en disco."""

    def test_escribe_json_ordenado(self, paths: dict[str, Path]) -> None:
        manifest = {"files": {"b.txt": {"sha256": "y"}, "a.txt": {"sha256": "x"}}}

        save_manifest(manifest)

        written = paths["manifest"].read_text(encoding="utf-8")
        assert written == json.dumps(manifest, indent=2, sort_keys=True)
        assert paths["data"].is_dir()

    def test_espacio_insuficiente_levanta_oserror(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        monkeypatch.setattr("shutil.disk_usage", lambda path: type("DU", (), {"free": 0, "total": 1, "used": 1})())
        logs = _capture_log(monkeypatch, "exception")

        with pytest.raises(OSError, match="Espacio en disco insuficiente"):
            save_manifest(_fake_manifest())

        assert len(logs) == 1
        assert not paths["manifest"].exists()


class TestIndexDocuments:
    """index_documents: ciclo completo de indexación idempotente."""

    def test_qdrant_no_disponible_devuelve_error(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        fake = FakeQdrant(disponible=False)
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        result = index_documents(force=False)

        assert result == {"error": "Qdrant no disponible"}
        assert not paths["manifest"].exists()

    def test_indexa_archivo_nuevo(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        file = paths["docs"] / "a.txt"
        file.write_text(" ".join(f"palabra{i}" for i in range(30)), encoding="utf-8")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        stats = index_documents(force=False)

        assert stats["new"] == 1
        assert stats["modified"] == 0
        assert stats["unchanged"] == 0
        assert stats["deleted"] == 0
        assert stats["chunks_added"] > 0
        manifest = load_manifest()
        assert manifest["total_documents"] == 1
        assert manifest["total_chunks"] == stats["chunks_added"]
        entry = manifest["files"]["a.txt"]
        assert entry["sha256"] == _sha256(file)
        assert entry["chunks"] == stats["chunks_added"]
        assert len(fake.saved_batches) == 1
        doc_ids = [d[0] for d in fake.saved_batches[0]]
        assert doc_ids == [f"a.txt_{i}" for i in range(stats["chunks_added"])]

    def test_archivo_sin_cambios_no_reenvia(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        file = paths["docs"] / "a.txt"
        file.write_text("contenido estable", encoding="utf-8")
        manifest = _fake_manifest()
        manifest["files"]["a.txt"] = {"sha256": _sha256(file), "chunks": 1, "indexed_at": "x"}
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        stats = index_documents(force=False)

        assert stats == {"new": 0, "modified": 0, "unchanged": 1, "deleted": 0, "chunks_added": 0}
        assert fake.saved_batches == []
        assert fake.deleted_filters == []

    def test_archivo_eliminado_borra_chunks(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        manifest = _fake_manifest()
        manifest["files"]["gone.txt"] = {"sha256": "deadbeef", "chunks": 1, "indexed_at": "x"}
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        stats = index_documents(force=False)

        assert stats["deleted"] == 1
        assert fake.deleted_filters == [{"source": "gone.txt"}]
        assert "gone.txt" not in load_manifest()["files"]

    def test_archivo_modificado_se_reindexa(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        file = paths["docs"] / "a.txt"
        file.write_text("contenido v2" * 30, encoding="utf-8")
        manifest = _fake_manifest()
        manifest["files"]["a.txt"] = {"sha256": "hash-distinto", "chunks": 1, "indexed_at": "x"}
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        stats = index_documents(force=False)

        assert stats["modified"] == 1
        assert fake.deleted_filters == [{"source": "a.txt"}]
        assert load_manifest()["files"]["a.txt"]["sha256"] == _sha256(file)

    def test_force_reindexa_aun_con_hash_igual(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        file = paths["docs"] / "a.txt"
        file.write_text("contenido", encoding="utf-8")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        stats = index_documents(force=True)

        assert stats["new"] == 1
        assert stats["unchanged"] == 0
        assert len(fake.saved_batches) == 1
        assert load_manifest()["files"]["a.txt"]["sha256"] == _sha256(file)

    def test_fallo_batch_no_registra_el_archivo(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        (paths["docs"] / "a.txt").write_text("contenido" * 40, encoding="utf-8")
        fake = FakeQdrant()
        fake.fail_batch = True
        logs = _capture_log(monkeypatch, "exception")
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        stats = index_documents(force=False)

        assert stats["chunks_added"] == 0
        assert "a.txt" not in load_manifest()["files"]
        assert len(logs) == 1


class TestEscanearArchivos:
    """_escanear_archivos: listado recursivo ignorando archivos ocultos."""

    def test_solo_archivos_no_ocultos_con_hash(self, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        (paths["docs"] / "a.txt").write_text("hola", encoding="utf-8")
        (paths["docs"] / ".hidden").write_text("secreto", encoding="utf-8")
        sub = paths["docs"] / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("mundo", encoding="utf-8")
        (sub / ".h2").write_text("x", encoding="utf-8")

        found = me._escanear_archivos()

        assert set(found) == {"a.txt", "sub/b.txt"}
        assert found["a.txt"] == _sha256(paths["docs"] / "a.txt")
        assert all(len(v) == 64 for v in found.values())


class TestProcesarEliminados:
    """_procesar_eliminados: borrado de documentos ausentes."""

    def test_elimina_y_actualiza_stats(self, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest = {"files": {"gone.txt": {}}}
        stats = {"deleted": 0}
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        _procesar_eliminados(manifest, {}, fake, stats)

        assert stats == {"deleted": 1}
        assert manifest["files"] == {}
        assert fake.deleted_filters == [{"source": "gone.txt"}]

    def test_fallo_eliminando_deja_manifest_y_avisa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest = {"files": {"gone.txt": {}}}
        stats = {"deleted": 0}
        fake = FakeQdrant()
        fake.fail_delete = True
        warnings = _capture_log(monkeypatch, "warning")

        _procesar_eliminados(manifest, {}, fake, stats)

        assert stats == {"deleted": 0}
        assert "gone.txt" in manifest["files"]
        assert len(warnings) == 1


class TestIndexarArchivo:
    """_indexar_archivo: indexación individual de un archivo."""

    def test_archivo_nuevo(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        file = paths["docs"] / "n.txt"
        file.write_text(" ".join(f"p{i}" for i in range(8)), encoding="utf-8")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)
        manifest = _fake_manifest()
        stats = {"new": 0, "modified": 0, "unchanged": 0, "chunks_added": 0}

        me._indexar_archivo("n.txt", "hash-nuevo", manifest, fake, stats, False)

        assert stats["new"] == 1
        assert stats["chunks_added"] == 1
        entry = manifest["files"]["n.txt"]
        assert entry["sha256"] == "hash-nuevo"
        assert entry["chunks"] == 1
        assert entry["indexed_at"]
        assert fake.deleted_filters == []

    def test_sin_cambios_no_indexa(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        manifest = {"files": {"n.txt": {"sha256": "same-hash", "chunks": 1, "indexed_at": "x"}}, "indexed_at": None, "total_chunks": 0, "total_documents": 0}
        stats = {"new": 0, "modified": 0, "unchanged": 0, "chunks_added": 0}
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        me._indexar_archivo("n.txt", "same-hash", manifest, fake, stats, False)

        assert stats == {"new": 0, "modified": 0, "unchanged": 1, "chunks_added": 0}
        assert fake.saved_batches == []

    def test_force_con_hash_igual_marca_modificado(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        (paths["docs"] / "n.txt").write_text("palabra" * 10, encoding="utf-8")
        manifest = {"files": {"n.txt": {"sha256": "same-hash"}}, "indexed_at": None, "total_chunks": 0, "total_documents": 0}
        stats = {"new": 0, "modified": 0, "unchanged": 0, "chunks_added": 0}
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        me._indexar_archivo("n.txt", "same-hash", manifest, fake, stats, True)

        assert stats["modified"] == 1
        assert stats["unchanged"] == 0
        assert fake.deleted_filters == [{"source": "n.txt"}]

    def test_error_leyendo_archivo_aborta(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        (paths["docs"] / "n.txt").write_text("x", encoding="utf-8")
        manifest = _fake_manifest()
        stats = {"new": 0, "modified": 0, "unchanged": 0, "chunks_added": 0}
        fake = FakeQdrant()
        logs = _capture_log(monkeypatch, "exception")
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        def boom(self: Path, **kwargs: Any) -> str:
            raise OSError("no readable")

        monkeypatch.setattr(Path, "read_text", boom)

        me._indexar_archivo("n.txt", "h", manifest, fake, stats, False)

        assert stats["new"] == 1
        assert stats["chunks_added"] == 0
        assert manifest["files"] == {}
        assert len(logs) == 1

    def test_chunks_vacios_no_guardan(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        (paths["docs"] / "n.txt").write_text("x", encoding="utf-8")
        manifest = _fake_manifest()
        stats = {"new": 0, "modified": 0, "unchanged": 0, "chunks_added": 0}
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)
        monkeypatch.setattr(me, "_chunk_text", lambda *args, **kwargs: [])

        me._indexar_archivo("n.txt", "h", manifest, fake, stats, False)

        assert stats["chunks_added"] == 0
        assert fake.saved_batches == []
        assert "n.txt" not in manifest["files"]

    def test_fallo_guardando_aborta_sin_manifest(self, monkeypatch: pytest.MonkeyPatch, paths: dict[str, Path]) -> None:
        paths["docs"].mkdir(parents=True)
        (paths["docs"] / "n.txt").write_text("palabra" * 10, encoding="utf-8")
        manifest = _fake_manifest()
        stats = {"new": 0, "modified": 0, "unchanged": 0, "chunks_added": 0}
        fake = FakeQdrant()
        fake.fail_batch = True
        logs = _capture_log(monkeypatch, "exception")
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        me._indexar_archivo("n.txt", "h", manifest, fake, stats, False)

        assert stats["new"] == 1
        assert stats["chunks_added"] == 0
        assert manifest["files"] == {}
        assert len(logs) == 1


class TestConstruirBatch:
    """_construir_batch: construcción del lote de documentos Qdrant."""

    def test_metadatos_por_chunk(self) -> None:
        batch = _construir_batch("doc.txt", "h1", ["uno", "dos", "tres"], "2026-08-15T00:00:00+00:00")

        assert batch == [
            ("doc.txt_0", "uno", {"source": "doc.txt", "chunk_index": 0, "total_chunks": 3, "sha256": "h1", "indexed_at": "2026-08-15T00:00:00+00:00"}),
            ("doc.txt_1", "dos", {"source": "doc.txt", "chunk_index": 1, "total_chunks": 3, "sha256": "h1", "indexed_at": "2026-08-15T00:00:00+00:00"}),
            ("doc.txt_2", "tres", {"source": "doc.txt", "chunk_index": 2, "total_chunks": 3, "sha256": "h1", "indexed_at": "2026-08-15T00:00:00+00:00"}),
        ]

    def test_sin_chunks_devuelve_vacio(self) -> None:
        assert _construir_batch("doc.txt", "h1", [], "now") == []


class TestQuery:
    """query: búsqueda en Qdrant con filtro por similitud."""

    def test_qdrant_no_disponible_devuelve_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant(disponible=False)
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        assert query("pregunta") == []

    def test_excepcion_en_busqueda_devuelve_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant()
        fake.fail_search = True
        logs = _capture_log(monkeypatch, "exception")
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        assert query("pregunta") == []
        assert len(logs) == 1

    def test_filtra_resultados_bajo_umbral(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant()
        fake.search_results = [
            {"payload": {"texto": "ctx1", "source": "a.txt", "chunk_index": 0}, "score": 0.9},
            {"payload": {"texto": "ctx2", "source": "b.txt", "chunk_index": 1}, "score": 0.4},
            {"payload": {"texto": "ctx3", "source": "c.txt"}, "score": 0.93456},
        ]
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)
        monkeypatch.setattr(me, "SIMILARITY_THRESHOLD", 0.7)

        hits = query("pregunta")

        assert hits == [
            {"content": "ctx1", "source": "a.txt", "chunk_index": 0, "similarity": 0.9},
            {"content": "ctx3", "source": "c.txt", "chunk_index": 0, "similarity": 0.9346},
        ]

    def test_resultado_sin_score_se_descarta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant()
        fake.search_results = [{"payload": {"texto": "x", "source": "s"}, "score": 0}]
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)
        monkeypatch.setattr(me, "SIMILARITY_THRESHOLD", 0.1)

        assert query("pregunta") == []

    def test_top_k_limitado_a_10(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        query("pregunta", top_k=15)
        query("pregunta", top_k=2)

        assert fake.search_limits == [10, 2]


class TestGetSources:
    """get_sources: fuentes únicas con conteo de chunks usados."""

    def test_fuentes_unicas_e_incremento_conteo(self) -> None:
        results = [
            {"source": "a.txt"},
            {"source": "a.txt"},
            {"source": "b.txt"},
        ]

        assert get_sources(results) == [{"source": "a.txt", "chunks_used": 2}, {"source": "b.txt", "chunks_used": 1}]

    def test_fuente_ausente_es_unknown(self) -> None:
        assert get_sources([{}, {}]) == [{"source": "unknown", "chunks_used": 2}]

    def test_vacio(self) -> None:
        assert get_sources([]) == []


class TestChromadbAvailable:
    """_chromadb_available: ChromaDB desinstalado, siempre False."""

    def test_siempre_false(self) -> None:
        assert _chromadb_available() is False


class TestRagEnabled:
    """rag_enabled: RAG activo solo si config, Qdrant y directorio existen."""

    def test_no_habilitado_en_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(me, "CONFIG", {"rag": {"enabled": False}})

        assert rag_enabled() is False

    def test_qdrant_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(me, "CONFIG", {"rag": {"enabled": True}})
        fake = FakeQdrant(disponible=False)
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        assert rag_enabled() is False

    def test_directorio_documentos_inexistente(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(me, "CONFIG", {"rag": {"enabled": True}})
        monkeypatch.setattr(me, "DOCS_DIR", tmp_path / "no-existe")
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        assert rag_enabled() is False

    def test_habilitado_completo(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        docs_dir = tmp_path / "documentos"
        docs_dir.mkdir()
        monkeypatch.setattr(me, "CONFIG", {"rag": {"enabled": True}})
        monkeypatch.setattr(me, "DOCS_DIR", docs_dir)
        fake = FakeQdrant()
        monkeypatch.setattr(me, "_get_qdrant", lambda: fake)

        assert rag_enabled() is True


class TestBuildContext:
    """_build_context: construcción del contexto textual para el LLM."""

    def test_vacio_devuelve_cadena_vacia(self) -> None:
        assert _build_context([]) == ""

    def test_ignora_resultados_sin_contenido(self) -> None:
        results = [
            {"content": "primer contenido", "source": "a.txt", "similarity": 0.9},
            {"source": "b.txt", "similarity": 0.8},
        ]

        ctx = _build_context(results)

        assert ctx == "[1] (fuente: a.txt, similitud: 0.90)\nprimer contenido"

    def test_varios_resultados_ordenados(self) -> None:
        results = [
            {"content": "c1", "source": "a.txt", "similarity": 0.9345},
            {"content": "c2", "source": "b.txt", "similarity": 0.8},
        ]

        ctx = _build_context(results)

        assert ctx == (
            "[1] (fuente: a.txt, similitud: 0.93)\nc1\n\n"
            "[2] (fuente: b.txt, similitud: 0.80)\nc2"
        )

    def test_trunca_a_max_chars(self) -> None:
        ctx = _build_context([{"content": "x" * 50, "source": "a", "similarity": 0.9}], max_chars=10)

        assert len(ctx) == 10

    def test_fuente_ausente_devuelve_unknown(self) -> None:
        assert _build_context([{"content": "texto", "similarity": 0.5}]) == "[1] (fuente: unknown, similitud: 0.50)\ntexto"


class TestGenerate:
    """_generate: generación de respuesta delegando en motor.core.llm."""

    def test_sin_contexto_devuelve_mensaje_por_defecto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        monkeypatch.setattr(me, "llm_generate", lambda prompt: calls.append(prompt) or "ok")

        assert _generate("", "¿qué es?") == "No se encontraron documentos relevantes para generar una respuesta."
        assert calls == []

    def test_con_contexto_llama_al_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        prompts: list[str] = []
        monkeypatch.setattr(me, "llm_generate", lambda prompt: prompts.append(prompt) or "Respuesta IA")

        result = _generate("CONTEXTO", "¿qué es?")

        assert result == "Respuesta IA"
        assert len(prompts) == 1
        assert "CONTEXTO" in prompts[0]
        assert "¿qué es?" in prompts[0]
        assert prompts[0].startswith("Eres un asistente experto")


class TestAsk:
    """ask: pipeline RAG completo recuperación + generación."""

    def test_ask_completo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        query_calls: list[tuple[str, int | None]] = []
        monkeypatch.setattr(me, "query", lambda question, top_k=5: query_calls.append((question, top_k)) or [{"content": "ctx", "source": "a.txt", "similarity": 0.9}])
        monkeypatch.setattr(me, "llm_generate", lambda prompt: "respuesta final")

        result = ask("¿pregunta?")

        assert result == "respuesta final"
        assert query_calls == [("¿pregunta?", 5)]

    def test_ask_con_top_k_explicito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        query_calls: list[int | None] = []
        monkeypatch.setattr(me, "query", lambda question, top_k=5: query_calls.append(top_k) or [])
        monkeypatch.setattr(me, "llm_generate", lambda prompt: "")

        ask("¿pregunta?", top_k=3)

        assert query_calls == [3]

"""Snapshot tests — output estructurado que NO debe cambiar sin revisión.

Regla (Plan de Testing): si un snapshot falla, revisar si el cambio es
intencional. NUNCA actualizar con --snapshot-update sin permiso de Ramón.
"""
from __future__ import annotations

import json

from knowledge.engine.chunker import chunk_text
from motor.core.llm._logging import percentile
from scripts.pro.tuneladora.pipeline.runner import _build_json_report
from scripts.pro.tuneladora.pipeline.tools.base import Status


class TestSnapshotEstables:
    def test_percentil_resultado(self, snapshot) -> None:
        """Percentil de datos conocidos: formato determinista."""
        snapshot.assert_match(str(percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50)), "percentil_p50.txt")

    def test_chunk_text_formato(self, snapshot) -> None:
        """Chunk de texto: text, chunk_index, metadata."""
        chunks = chunk_text("una dos tres cuatro cinco", max_words=3, overlap=1)
        data = [{"index": c.chunk_index, "text": c.text, "doc_id": c.doc_id} for c in chunks]
        snapshot.assert_match(json.dumps(data, indent=2), "chunk_text.json")

    def test_reporte_tuneladora_formato(self, snapshot) -> None:
        """Formato del reporte JSON del runner (Gap #5)."""
        report = _build_json_report(
            episode_id="snap-ep", verdict=Status.OK, msg="ok", duration_ms=123.4,
            mode="check", files=["a.py"], telemetry={"coverage_global": 78.5},
            sofia_n_criticos=0, sofia_n_advertencias=1,
        )
        report.pop("timestamp", None)  # no-determinista: excluido del snapshot
        snapshot.assert_match(json.dumps(report, indent=2), "reporte_tuneladora.json")

    def test_errores_tuneladora_formato(self, snapshot) -> None:
        """Formato del reporte FAIL (misma estructura, verdict distinto)."""
        report = _build_json_report(
            episode_id="snap-fail", verdict=Status.FAIL, msg="boom", duration_ms=1.0,
            mode="check", files=[], telemetry={},
            sofia_n_criticos=1, sofia_n_advertencias=0,
        )
        report.pop("timestamp", None)  # no-determinista: excluido del snapshot
        snapshot.assert_match(json.dumps(report, indent=2), "reporte_fail.json")

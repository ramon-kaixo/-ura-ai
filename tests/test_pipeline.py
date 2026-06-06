"""Tests de integración: scraper → analyzer → analytics.db"""
import json
import sys
import tempfile
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import core.data_scraper as scraper
import core.data_analyzer as analyzer


class TestPipelineScraperToFile:
    def setup_method(self):
        self._orig_dir = scraper.DATA_DIR
        self.tmp = Path(tempfile.mkdtemp())
        scraper.DATA_DIR = self.tmp

    def teardown_method(self):
        scraper.DATA_DIR = self._orig_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scraper_writes_jsonl(self):
        scraper.collect_snapshot_sync()
        files = list(self.tmp.glob("*.jsonl"))
        assert len(files) >= 1
        content = files[0].read_text().strip()
        assert len(content.split("\n")) >= 1
        parsed = json.loads(content.split("\n")[0])
        assert "ts" in parsed and "source" in parsed and "data" in parsed


class TestPipelineAnalyzerToDb:
    def setup_method(self):
        self._orig_raw = analyzer.RAW_DIR
        self._orig_proc = analyzer.PROCESSED_DIR
        self.raw = Path(tempfile.mkdtemp())
        self.proc = Path(tempfile.mkdtemp())
        analyzer.RAW_DIR = self.raw
        analyzer.PROCESSED_DIR = self.proc
        analyzer.DB_PATH = self.proc / "analytics.db"
        analyzer._source_buffers = {}
        analyzer._last_processed_file = ""
        (self.raw / "data_test.jsonl").write_text(
            '{"ts":"T1","source":"btc_test","data":{"price":50000},"latency_ms":50}\n'
            '{"ts":"T2","source":"btc_test","data":{"price":51000},"latency_ms":60}\n'
        )

    def teardown_method(self):
        analyzer.RAW_DIR = self._orig_raw
        analyzer.PROCESSED_DIR = self._orig_proc
        analyzer.DB_PATH = self._orig_proc / "analytics.db"
        shutil.rmtree(self.raw, ignore_errors=True)
        shutil.rmtree(self.proc, ignore_errors=True)

    def test_analyzer_creates_db(self):
        analyzer.process_raw_files_sync()
        assert analyzer.DB_PATH.exists()
        assert analyzer.DB_PATH.stat().st_size > 0

    def test_analyzer_computes_moving_avg(self):
        analyzer.process_raw_files_sync()
        import sqlite3
        conn = sqlite3.connect(str(analyzer.DB_PATH))
        rows = conn.execute("SELECT metric_name, metric_value, moving_avg FROM analytics ORDER BY id").fetchall()
        conn.close()
        assert len(rows) >= 2
        prices = [r[1] for r in rows if r[0] == "price"]
        avgs = [r[2] for r in rows if r[0] == "price"]
        assert len(prices) >= 2
        assert avgs[-1] > 50000


class TestPipelineFullCycle:
    def setup_method(self):
        self._orig_scraper_dir = scraper.DATA_DIR
        self._orig_analyzer_raw = analyzer.RAW_DIR
        self._orig_analyzer_proc = analyzer.PROCESSED_DIR
        self.tmp = Path(tempfile.mkdtemp())
        scraper.DATA_DIR = self.tmp
        analyzer.RAW_DIR = self.tmp
        self.proc = Path(tempfile.mkdtemp())
        analyzer.PROCESSED_DIR = self.proc
        analyzer.DB_PATH = self.proc / "analytics.db"
        analyzer._source_buffers = {}
        analyzer._last_processed_file = ""

    def teardown_method(self):
        scraper.DATA_DIR = self._orig_scraper_dir
        analyzer.RAW_DIR = self._orig_analyzer_raw
        analyzer.PROCESSED_DIR = self._orig_analyzer_proc
        analyzer.DB_PATH = self._orig_analyzer_proc / "analytics.db"
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.proc, ignore_errors=True)

    def test_full_pipeline_data_flow(self):
        scraper.collect_snapshot_sync()
        raw_files = list(self.tmp.glob("*.jsonl"))
        assert len(raw_files) >= 1
        analyzer.process_raw_files_sync()
        assert analyzer.DB_PATH.exists()
        import sqlite3
        conn = sqlite3.connect(str(analyzer.DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM analytics").fetchone()[0]
        conn.close()
        assert count >= 1, f"Esperado >=1 fila en analytics.db, obtenido {count}"

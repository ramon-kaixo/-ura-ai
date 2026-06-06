"""Tests para search_engine.py — FTS5 sobre analytics.db"""
import sys
import tempfile
import sqlite3
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.search_engine import search, get_suggestions, rebuild_index, DB_PATH, FTS_TABLE


class TestSearchEngine:
    def setup_method(self):
        self._orig_db = DB_PATH
        self.tmp = Path(tempfile.mkdtemp())
        self.db_path = self.tmp / "analytics.db"
        import core.search_engine as se
        se.DB_PATH = self.db_path
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, source TEXT,
                metric_name TEXT, metric_value REAL, moving_avg REAL, records_count INTEGER
            )
        """)
        conn.execute("INSERT INTO analytics (ts, source, metric_name, metric_value, moving_avg, records_count) VALUES ('T1','test','latency_ms',5.0,5.0,1)")
        conn.execute("INSERT INTO analytics (ts, source, metric_name, metric_value, moving_avg, records_count) VALUES ('T2','test','btc_usd',60000,60000,1)")
        conn.commit()
        conn.close()

    def teardown_method(self):
        import core.search_engine as se
        se.DB_PATH = self._orig_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rebuild_returns_count(self):
        c = rebuild_index()
        assert c == 2

    def test_search_finds_latency(self):
        rebuild_index()
        results = search("latency")
        assert len(results) >= 1
        assert results[0]["metric_name"] == "latency_ms"

    def test_search_btc(self):
        rebuild_index()
        results = search("btc")
        assert len(results) >= 1
        assert "btc" in results[0]["metric_name"]

    def test_suggestions(self):
        rebuild_index()
        sug = get_suggestions("btc")
        assert len(sug) >= 1
        assert "btc_usd" in sug

    def test_empty_query_returns_empty(self):
        rebuild_index()
        results = search("nonexistent_xyz_123")
        assert results == []

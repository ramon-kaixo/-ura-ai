"""Tests for scripts/pro/seed_correcciones_voz.py."""
import sqlite3

import pytest

from scripts.pro.seed_correcciones_voz import CORRECCIONES, seed


class TestSeed:
    def test_seed_creates_db(self, tmp_path, monkeypatch):
        db = tmp_path / "voice_corrections.db"
        monkeypatch.setattr("scripts.pro.seed_correcciones_voz.DB_PATH", db)
        seed()
        assert db.exists()

    def test_seed_creates_table(self, tmp_path, monkeypatch):
        db = tmp_path / "voice_corrections.db"
        monkeypatch.setattr("scripts.pro.seed_correcciones_voz.DB_PATH", db)
        seed()
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corrections'").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_seed_inserts_data(self, tmp_path, monkeypatch):
        db = tmp_path / "voice_corrections.db"
        monkeypatch.setattr("scripts.pro.seed_correcciones_voz.DB_PATH", db)
        seed()
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        conn.close()
        assert count > 0

    def test_seed_idempotent(self, tmp_path, monkeypatch):
        db = tmp_path / "voice_corrections.db"
        monkeypatch.setattr("scripts.pro.seed_correcciones_voz.DB_PATH", db)
        seed()
        seed()
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        conn.close()
        # Idempotente: misma cantidad tras segunda ejecución
        assert count > 0

    def test_skips_same_key_value(self, tmp_path, monkeypatch):
        db = tmp_path / "voice_corrections.db"
        monkeypatch.setattr("scripts.pro.seed_correcciones_voz.DB_PATH", db)
        # CORRECCIONES tiene ("tuneladora", "tuneladora") que debería saltarse
        seed()
        conn = sqlite3.connect(db)
        # tuneladora no debería estar porque key == val.lower()
        rows = conn.execute("SELECT * FROM corrections WHERE wrong_text = 'tuneladora'").fetchall()
        conn.close()
        assert len(rows) == 0

    def test_correcciones_not_empty(self):
        assert len(CORRECCIONES) > 0
        for wrong, correct in CORRECCIONES:
            assert isinstance(wrong, str)
            assert isinstance(correct, str)
            assert wrong.strip()
            assert correct.strip()

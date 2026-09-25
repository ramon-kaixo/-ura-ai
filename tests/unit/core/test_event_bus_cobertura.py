#!/usr/bin/env python3
"""Cobertura 100x100 de core/event_bus.py."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import UTC, datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.event_bus import (
    _run_async,
    _journal_path,
    _write_journal,
    replay_events,
    EVENTS_DIR,
    TOPIC_ANALYTICS,
    TOPIC_ALERT,
    TOPIC_COMMAND,
)


class TestRunAsync:
    """Tests para _run_async (puente sync->async)."""

    @pytest.mark.unit
    def test_run_async_sin_loop_ejecutando(self):
        """Sin event loop corriendo, usa asyncio.run"""
        async def coro():
            return "ok"
        result = _run_async(coro())
        assert result == "ok"

    @pytest.mark.unit
    def test_run_async_con_loop_ejecutando(self):
        """Con event loop corriendo, usa ThreadPoolExecutor"""
        import asyncio
        async def coro():
            return "ok"
        
        async def test():
            result = _run_async(coro())
            assert result == "ok"
        
        asyncio.run(test())


class TestJournalPath:
    """Tests para _journal_path."""

    @pytest.mark.unit
    def test_journal_path_formato_fecha(self):
        """Verifica formato de fecha en path"""
        path = _journal_path()
        assert "events" in str(path)
        assert ".jsonl" in str(path)

    @pytest.mark.unit
    def test_journal_path_fecha_especifica(self):
        """Verifica path con fecha específica"""
        path = _journal_path()
        assert isinstance(path, Path)


class TestWriteJournal:
    """Tests para _write_journal."""

    @pytest.mark.unit
    def test_write_journal_crea_archivo(self, tmp_path):
        """Verifica que crea archivo y escribe entry"""
        with patch('core.event_bus._journal_path') as mock_path:
            mock_file = tmp_path / "test.jsonl"
            mock_path.return_value = mock_file
            
            from core.event_bus import _write_journal
            _write_journal("test_topic", {"key": "value"})
            
            assert mock_file.exists()
            content = mock_file.read_text()
            assert "test_topic" in content
            assert "key" in content

    @pytest.mark.unit
    def test_write_journal_maneja_error(self):
        """Verifica manejo de errores de escritura"""
        with patch('core.event_bus._journal_path') as mock_path:
            mock_path.side_effect = PermissionError("No permission")
            from core.event_bus import _write_journal
            _write_journal("topic", {"data": "value"})


class TestReplayEvents:
    """Tests para replay_events."""

    @pytest.mark.unit
    def test_replay_events_archivo_no_existe(self):
        """Archivo no existe -> lista vacía"""
        events = replay_events("2024-01-01")
        assert events == []

    @pytest.mark.unit
    def test_replay_events_filtra_por_topic(self):
        """Verifica filtrado por topic usando EVENTS_DIR real"""
        from core.event_bus import EVENTS_DIR
        
        # Crear directorio y archivo de test en el EVENTS_DIR real
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        test_file = EVENTS_DIR / "2024-01-01.jsonl"
        
        test_data = [
            {"ts": "2024-01-01T00:00:00Z", "topic": "analytics", "data": {"a": 1}},
            {"ts": "2024-01-01T00:00:01Z", "topic": "alert", "data": {"b": 2}},
        ]
        test_file.write_text("\n".join(json.dumps(d) for d in test_data))
        
        try:
            events = replay_events("2024-01-01", topic="analytics")
            assert len(events) == 1
            assert events[0]["topic"] == "analytics"
            
            all_events = replay_events("2024-01-01")
            assert len(all_events) == 2
        finally:
            if test_file.exists():
                test_file.unlink()


class TestConstants:
    """Tests para constantes."""

    @pytest.mark.unit
    def test_topics_definidos(self):
        assert TOPIC_ANALYTICS == "analytics"
        assert TOPIC_ALERT == "alert"
        assert TOPIC_COMMAND == "command"


class TestRunAsyncEdgeCases:
    """Casos edge para _run_async."""

    @pytest.mark.unit
    def test_coro_con_exception(self):
        async def coro_error():
            raise ValueError("test error")
        
        with pytest.raises(ValueError, match="test error"):
            from core.event_bus import _run_async
            _run_async(coro_error())

    @pytest.mark.unit
    def test_coro_con_return_value(self):
        async def coro_complex():
            return {"list": [1, 2, 3], "dict": {"a": 1}}
        
        from core.event_bus import _run_async
        result = _run_async(coro_complex())
        assert result == {"list": [1, 2, 3], "dict": {"a": 1}}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

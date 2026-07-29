from __future__ import annotations

from datetime import UTC, datetime, timedelta

from motor.intelligence.memory.episodic import Episode, EpisodeStore, EpisodeStoreConfig, SessionMemory
from motor.intelligence.memory.record import MemoryRecord, MemoryType

ONE_DAY = 86400


class TestEpisode:
    def test_create_minimal(self):
        ep = Episode()
        assert ep.id != ""
        assert ep.timestamp != ""
        assert ep.ttl == ONE_DAY * 7
        assert ep.importance == 0.5

    def test_to_record(self):
        ep = Episode(session_id="s1", payload="hello", source="user")
        record = ep.to_record()
        assert record.type == MemoryType.EPISODIC
        assert record.payload == "hello"
        assert record.metadata["session_id"] == "s1"

    def test_from_record(self):
        record = MemoryRecord(
            type=MemoryType.EPISODIC,
            payload="test",
            metadata={"session_id": "s2"},
        )
        ep = Episode.from_record(record)
        assert ep.payload == "test"
        assert ep.session_id == "s2"

    def test_is_expired(self):
        future_ts = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        ep = Episode(timestamp=future_ts, ttl=1)
        assert not ep.is_expired

    def test_is_expired_true(self):
        past_ts = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        ep = Episode(timestamp=past_ts, ttl=ONE_DAY * 7)
        assert ep.is_expired

    def test_is_expired_no_ttl(self):
        ep = Episode(ttl=0)
        assert not ep.is_expired

    def test_age_seconds(self):
        ep = Episode()
        assert ep.age_seconds >= 0


class TestEpisodeStore:
    def test_store_and_get(self):
        store = EpisodeStore()
        ep = Episode(payload="hello")
        eid = store.store(ep)
        assert eid != ""
        retrieved = store.get(eid)
        assert retrieved is not None
        assert retrieved.payload == "hello"

    def test_get_nonexistent(self):
        store = EpisodeStore()
        assert store.get("nonexistent") is None

    def test_store_assigns_id(self):
        store = EpisodeStore()
        ep = Episode()
        eid = store.store(ep)
        assert ep.id == eid

    def test_store_assigns_timestamp(self):
        store = EpisodeStore()
        ep = Episode(timestamp="")
        store.store(ep)
        assert ep.timestamp != ""

    def test_delete(self):
        store = EpisodeStore()
        eid = store.store(Episode())
        assert store.delete(eid) is True
        assert store.get(eid) is None

    def test_delete_nonexistent(self):
        store = EpisodeStore()
        assert store.delete("nope") is False

    def test_count_empty(self):
        store = EpisodeStore()
        assert store.count() == 0

    def test_count_after_store(self):
        store = EpisodeStore()
        store.store(Episode(session_id="s1"))
        store.store(Episode(session_id="s1"))
        store.store(Episode(session_id="s2"))
        assert store.count() == 3
        assert store.count("s1") == 2
        assert store.count("s2") == 1

    def test_delete_expired(self):
        store = EpisodeStore()
        past_ts = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        store.store(Episode(timestamp=past_ts, ttl=ONE_DAY * 7))
        store.store(Episode(payload="fresh"))
        deleted = store.delete_expired()
        assert deleted >= 1
        assert store.count() == 1

    def test_clear_session(self):
        store = EpisodeStore()
        store.store(Episode(session_id="s1"))
        store.store(Episode(session_id="s1"))
        store.store(Episode(session_id="s2"))
        assert store.clear_session("s1") == 2
        assert store.count() == 1

    def test_clear_all(self):
        store = EpisodeStore()
        store.store(Episode())
        store.store(Episode())
        assert store.clear_all() == 2
        assert store.count() == 0

    def test_get_by_session(self):
        store = EpisodeStore()
        store.store(Episode(session_id="s1", payload="first"))
        store.store(Episode(session_id="s1", payload="second"))
        store.store(Episode(session_id="s2", payload="other"))
        results = store.get_by_session("s1")
        assert len(results) == 2
        assert results[0].payload == "second"  # newest first

    def test_get_by_session_limit(self):
        store = EpisodeStore()
        for i in range(10):
            store.store(Episode(session_id="s1", payload=f"e{i}"))
        assert len(store.get_by_session("s1", limit=3)) == 3

    def test_get_by_session_offset(self):
        store = EpisodeStore()
        for i in range(10):
            store.store(Episode(session_id="s1", payload=f"e{i}"))
        page1 = store.get_by_session("s1", limit=3, offset=0)
        page2 = store.get_by_session("s1", limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        # timestamps diff means order may vary, just verify pagination works
        assert page1[0].id != page2[0].id

    def test_get_by_time_range(self):
        store = EpisodeStore()
        now = datetime.now(UTC)
        ep1 = Episode(timestamp=(now - timedelta(hours=2)).isoformat())
        ep2 = Episode(timestamp=(now - timedelta(hours=1)).isoformat())
        ep3 = Episode(timestamp=(now + timedelta(hours=1)).isoformat())
        store.store(ep1)
        store.store(ep2)
        store.store(ep3)
        start = (now - timedelta(hours=3)).isoformat()
        end = now.isoformat()
        results = store.get_by_time_range(start, end)
        assert len(results) == 2  # ep1 and ep2

    def test_get_recent(self):
        store = EpisodeStore()
        for i in range(20):
            store.store(Episode(payload=f"e{i}"))
        recent = store.get_recent(k=5)
        assert len(recent) == 5

    def test_expired_not_returned(self):
        store = EpisodeStore()
        past_ts = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        eid = store.store(Episode(timestamp=past_ts, ttl=ONE_DAY * 7))
        assert store.get(eid) is None  # expired, not returned

    def test_trim(self):
        config = EpisodeStoreConfig(max_episodes=5, default_ttl=ONE_DAY * 7)
        store = EpisodeStore(config)
        for i in range(10):
            store.store(Episode(payload=f"e{i}"))
        assert store.count() <= 5

    def test_thread_safety(self):
        import concurrent.futures

        store = EpisodeStore()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [exe.submit(store.store, Episode(payload=f"t{i}")) for i in range(100)]
            concurrent.futures.wait(futures)
        assert store.count() == 100

    def test_serialization_roundtrip(self):
        ep = Episode(
            session_id="s_test",
            payload="test content",
            source="user",
            importance=0.8,
            confidence=0.9,
            tags=["tag1", "tag2"],
            references=["ref1"],
            ttl=3600,
            metadata={"key": "value"},
        )
        record = ep.to_record()
        ep2 = Episode.from_record(record)
        assert ep2.payload == ep.payload
        assert ep2.importance == ep.importance
        assert ep2.tags == ep.tags
        assert ep2.metadata["key"] == "value"


class TestSessionMemory:
    def test_create_session(self):
        sm = SessionMemory()
        sid = sm.create_session()
        assert sid != ""
        assert sm.session_count() == 1

    def test_create_session_with_id(self):
        sm = SessionMemory()
        sid = sm.create_session(session_id="my_session")
        assert sid == "my_session"

    def test_add_episode(self):
        sm = SessionMemory()
        sid = sm.create_session()
        ep = sm.add_episode(sid, "hello", source="user", importance=0.9)
        assert ep.session_id == sid
        assert ep.payload == "hello"
        assert ep.importance == 0.9

    def test_get_history(self):
        sm = SessionMemory()
        sid = sm.create_session()
        sm.add_episode(sid, "first")
        sm.add_episode(sid, "second")
        history = sm.get_history(sid)
        assert len(history) == 2
        assert history[0].payload == "second"

    def test_get_history_limit(self):
        sm = SessionMemory()
        sid = sm.create_session()
        for i in range(10):
            sm.add_episode(sid, f"e{i}")
        assert len(sm.get_history(sid, limit=3)) == 3

    def test_get_recent_across_sessions(self):
        sm = SessionMemory()
        s1 = sm.create_session()
        s2 = sm.create_session()
        sm.add_episode(s1, "a")
        sm.add_episode(s2, "b")
        sm.add_episode(s1, "c")
        recent = sm.get_recent(k=2)
        assert len(recent) == 2

    def test_close_session(self):
        sm = SessionMemory()
        sid = sm.create_session()
        assert sm.close_session(sid) is True
        assert sm.session_count() == 0

    def test_close_nonexistent(self):
        sm = SessionMemory()
        assert sm.close_session("nope") is False

    def test_store_property(self):
        store = EpisodeStore()
        sm = SessionMemory(store)
        assert sm.store is store

    def test_persist_sqlite(self, tmp_path):
        db_path = str(tmp_path / "test_episodes.db")
        config = EpisodeStoreConfig(persist_path=db_path)
        store = EpisodeStore(config)
        store.store(Episode(session_id="s1", payload="persisted"))
        store.store(Episode(session_id="s1", payload="also persisted"))
        assert store.count() == 2

        # Reload from DB
        store2 = EpisodeStore(config)
        assert store2.count() == 2

    def test_session_count(self):
        sm = SessionMemory()
        sm.create_session()
        sm.create_session()
        sm.create_session()
        assert sm.session_count() == 3

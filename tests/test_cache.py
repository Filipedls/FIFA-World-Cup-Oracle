"""Disk-cache staleness / 'a game has ended' invalidation."""
from datetime import datetime, timedelta, timezone

from world_cup_oracle.config import CACHE_TTL_SECONDS
from world_cup_oracle.data import cache

NOW = datetime(2026, 6, 13, 20, 0, tzinfo=timezone.utc)


def _ds(fetched_at, fixtures):
    return {"source": "api", "_fetched_at": fetched_at.isoformat(), "fixtures": fixtures}


def test_stale_without_fetch_timestamp():
    assert cache.is_stale({"fixtures": []}, now=NOW) is True


def test_fresh_when_recent_and_no_finished_games():
    fetched = NOW - timedelta(seconds=CACHE_TTL_SECONDS // 2)
    # a fixture that kicks off in the future -> hasn't ended
    fx = [{"status": "NS", "kickoff": (NOW + timedelta(hours=2)).isoformat()}]
    assert cache.is_stale(_ds(fetched, fx), now=NOW) is False


def test_stale_after_ttl():
    fetched = NOW - timedelta(seconds=CACHE_TTL_SECONDS + 60)
    assert cache.is_stale(_ds(fetched, []), now=NOW) is True


def test_stale_when_a_game_ended_since_fetch():
    # fetched 30 min ago; a match kicked off 3h ago -> ended in the meantime
    fetched = NOW - timedelta(minutes=30)
    fx = [{"status": "NS", "kickoff": (NOW - timedelta(hours=3)).isoformat()}]
    assert cache.is_stale(_ds(fetched, fx), now=NOW) is True


def test_not_stale_for_game_already_finished_in_cache():
    fetched = NOW - timedelta(seconds=60)  # within TTL, so isolate the FT check
    # old kickoff, but cache already has it as FT -> nothing new to fetch
    fx = [{"status": "FT", "kickoff": (NOW - timedelta(hours=3)).isoformat()}]
    assert cache.is_stale(_ds(fetched, fx), now=NOW) is False


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "_CACHE_FILE", tmp_path / "dataset.json")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    saved = cache.save({"source": "api", "fixtures": []})
    assert "_fetched_at" in saved
    loaded = cache.load()
    assert loaded["source"] == "api"
    cache.invalidate()
    assert cache.load() is None

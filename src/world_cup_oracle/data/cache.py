"""Disk cache for live API datasets.

Why a disk cache: API-Football's free tier is quota-limited, so we don't want to
re-fetch on every Streamlit rerun. A cached dataset is reused until either:

  * it is older than ``CACHE_TTL_SECONDS``, or
  * a fixture's kickoff is far enough in the past that the match has almost
    certainly *ended since the cache was written* — i.e. there are fresh results
    to pull. This is the "invalidate when a game ends" behaviour.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from ..config import CACHE_DIR, CACHE_TTL_SECONDS, MATCH_DURATION_MINUTES

_CACHE_FILE = CACHE_DIR / "dataset.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def save(dataset: dict) -> dict:
    """Stamp the dataset with a fetch time and persist it. Returns the dataset."""
    dataset = {**dataset, "_fetched_at": _now().isoformat()}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(dataset))
    return dataset


def load() -> dict | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        return json.loads(_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def invalidate() -> None:
    _CACHE_FILE.unlink(missing_ok=True)


def is_stale(dataset: dict, now: datetime | None = None) -> bool:
    now = now or _now()
    fetched = dataset.get("_fetched_at")
    if not fetched:
        return True
    fetched_dt = _parse(fetched)
    if (now - fetched_dt).total_seconds() > CACHE_TTL_SECONDS:
        return True
    # any not-yet-finished fixture whose match has ended since we last fetched?
    for f in dataset.get("fixtures", []):
        if f.get("status") == "FT" or not f.get("kickoff"):
            continue
        end = _parse(f["kickoff"]) + timedelta(minutes=MATCH_DURATION_MINUTES)
        if fetched_dt < end <= now:
            return True
    return False

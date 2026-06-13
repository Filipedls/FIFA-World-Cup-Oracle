"""Pick the live API when a key is configured, otherwise the offline sample.

Live datasets are served from a disk cache (see :mod:`.cache`) and only
re-fetched when the cache is stale or a refresh is forced, to respect the
API free-tier quota.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from ..config import API_KEY_ENV, DATA_SOURCE
from . import api_football, balldontlie, cache, sample

# provider name -> get_dataset(key, as_of)
_PROVIDERS = {
    "balldontlie": balldontlie.get_dataset,
    "api_football": api_football.get_dataset,
    "api-football": api_football.get_dataset,
}


def _load_dotenv() -> None:
    """Minimal .env loader (avoids a python-dotenv dependency)."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def _stamp_sample() -> dict:
    data = sample.build_dataset()
    data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    return data


def load_dataset(force_refresh: bool = False) -> dict:
    """Return a normalised dataset and never raise.

    With no API key: the offline sample. With a key: the disk cache if still
    fresh, otherwise a fresh fetch (persisted to the cache). Any API failure
    degrades to the previous cache, then to the sample, with a recorded
    ``dataset['warning']``.
    """
    _load_dotenv()
    key = os.getenv(API_KEY_ENV)
    if not key:
        return _stamp_sample()

    fetch = _PROVIDERS.get(DATA_SOURCE)
    if fetch is None:
        data = _stamp_sample()
        data["warning"] = f"Unknown WORLD_CUP_DATA_SOURCE '{DATA_SOURCE}'; showing sample data."
        return data

    cached = cache.load()
    if not force_refresh and cached and not cache.is_stale(cached):
        return cached

    try:
        fresh = fetch(key, as_of=sample.AS_OF)
        return cache.save(fresh)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully in the UI
        if cached:
            cached["warning"] = f"Refresh failed ({exc}); showing last cached data."
            return cached
        data = _stamp_sample()
        data["warning"] = f"API request failed ({exc}); showing sample data."
        return data

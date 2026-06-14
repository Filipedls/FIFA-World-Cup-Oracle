"""Assemble a dataset: a base source (fixtures/standings/scorers) optionally
enriched with betting odds, served from a disk cache to respect API quotas.

  base source   <- WORLD_CUP_DATA_SOURCE (worldcup26 | balldontlie | api_football)
  odds overlay  <- THE_ODDS_API_KEY (optional; only when the base lacks odds)

Never raises: any failure degrades to the previous cache, then the offline
sample, with the reason recorded in ``dataset['warning']``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from ..config import API_KEY_ENV, DATA_SOURCE, ODDS_API_KEY_ENV
from ..env import load_dotenv as _load_dotenv
from . import (api_football, balldontlie, cache, sample, the_odds_api,
               worldcup26)

# keyed providers (need WORLD_CUP_API_KEY); worldcup26 is handled separately
# because it needs no key.
_KEYED_PROVIDERS = {
    "balldontlie": balldontlie.get_dataset,
    "api_football": api_football.get_dataset,
    "api-football": api_football.get_dataset,
}


def _stamp_sample(warning: str | None = None) -> dict:
    data = sample.build_dataset()
    data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    if warning:
        data["warning"] = warning
    return data


def _fetch_base() -> dict | None:
    """Fetch the base dataset, or None if a keyed provider has no key."""
    if DATA_SOURCE == "worldcup26":
        return worldcup26.get_dataset(as_of=sample.AS_OF)
    fetch = _KEYED_PROVIDERS.get(DATA_SOURCE)
    if fetch is None:
        raise ValueError(f"Unknown WORLD_CUP_DATA_SOURCE '{DATA_SOURCE}'")
    key = os.getenv(API_KEY_ENV)
    if not key:
        return None
    return fetch(key, as_of=sample.AS_OF)


def _has_odds(dataset: dict) -> bool:
    return any(f.get("odds") for f in dataset.get("fixtures", []))


def _maybe_enrich_odds(dataset: dict) -> None:
    odds_key = os.getenv(ODDS_API_KEY_ENV)
    if not odds_key or _has_odds(dataset):
        return
    try:
        n = the_odds_api.enrich(dataset, odds_key)
        dataset["odds_note"] = (f"{n} fixtures priced via The Odds API"
                                if n else "No matching odds found yet.")
    except Exception as exc:  # noqa: BLE001 - odds are optional
        dataset["odds_note"] = f"Odds unavailable ({exc}); using model probabilities."


def load_dataset(force_refresh: bool = False) -> dict:
    _load_dotenv()

    cached = cache.load()
    if not force_refresh and cached and not cache.is_stale(cached):
        return cached

    try:
        base = _fetch_base()
    except ValueError as exc:
        return _stamp_sample(warning=f"{exc}; showing sample data.")
    except Exception as exc:  # noqa: BLE001 - degrade gracefully in the UI
        if cached:
            cached["warning"] = f"Refresh failed ({exc}); showing last cached data."
            return cached
        return _stamp_sample(warning=f"Data request failed ({exc}); showing sample data.")

    if base is None:
        return _stamp_sample(
            warning=f"No {API_KEY_ENV} set for source '{DATA_SOURCE}'; showing sample data.")

    _maybe_enrich_odds(base)
    return cache.save(base)

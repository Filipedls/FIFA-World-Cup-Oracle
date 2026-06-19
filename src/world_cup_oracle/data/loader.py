"""Assemble a dataset: a base source (fixtures/standings/scorers) optionally
enriched with betting odds, served from a disk cache to respect API quotas.

  base source   <- source arg / WORLD_CUP_DATA_SOURCE (worldcup26 | balldontlie | api_football)
  odds overlay  <- odds_key arg / THE_ODDS_API_KEY (only when the base lacks odds)

Keys and source can be passed explicitly (e.g. from the app's Config page);
when omitted they fall back to the environment / .env. Never raises: any failure
degrades to the previous cache, then the offline sample, with the reason in
``dataset['warning']``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from ..config import (API_KEY_ENV, CACHE_ENABLED, DATA_SOURCE,
                      ODDS_API_KEY_ENV)
from ..env import load_dotenv as _load_dotenv
from . import (api_football, balldontlie, cache, sample, the_odds_api,
               worldcup26)

# keyed providers (need a base key); worldcup26 is handled separately (no key).
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


def _fetch_base(source: str, api_key: str | None) -> dict | None:
    """Fetch the base dataset, or None if a keyed provider has no key."""
    if source == "worldcup26":
        return worldcup26.get_dataset(as_of=sample.AS_OF)
    fetch = _KEYED_PROVIDERS.get(source)
    if fetch is None:
        raise ValueError(f"Unknown data source '{source}'")
    if not api_key:
        return None
    return fetch(api_key, as_of=sample.AS_OF)


def _has_odds(dataset: dict) -> bool:
    return any(f.get("odds") for f in dataset.get("fixtures", []))


def _maybe_enrich_odds(dataset: dict, odds_key: str | None) -> None:
    if not odds_key or _has_odds(dataset):
        return
    try:
        n = the_odds_api.enrich(dataset, odds_key)
        dataset["odds_note"] = (f"{n} fixtures priced via The Odds API"
                                if n else "No matching odds found yet.")
    except Exception as exc:  # noqa: BLE001 - odds are optional
        dataset["odds_note"] = f"Odds unavailable ({exc}); using model probabilities."


def load_dataset(force_refresh: bool = False, *, source: str | None = None,
                 api_key: str | None = None, odds_key: str | None = None) -> dict:
    _load_dotenv()
    source = (source or DATA_SOURCE).strip().lower()
    if api_key is None:
        api_key = os.getenv(API_KEY_ENV)
    if odds_key is None:
        odds_key = os.getenv(ODDS_API_KEY_ENV)

    # disk cache is opt-in via WORLD_CUP_CACHE_ENABLED (off by default)
    cached = cache.load() if CACHE_ENABLED else None
    if (not force_refresh and cached and cached.get("_source_key") == source
            and not cache.is_stale(cached)):
        return cached

    try:
        base = _fetch_base(source, api_key)
    except ValueError as exc:
        return _stamp_sample(warning=f"{exc}; showing sample data.")
    except Exception as exc:  # noqa: BLE001 - degrade gracefully in the UI
        if cached:
            cached["warning"] = f"Refresh failed ({exc}); showing last cached data."
            return cached
        return _stamp_sample(warning=f"Data request failed ({exc}); showing sample data.")

    if base is None:
        return _stamp_sample(
            warning=f"No API key set for source '{source}'; showing sample data.")

    _maybe_enrich_odds(base, odds_key)
    base["_source_key"] = source
    if CACHE_ENABLED:
        return cache.save(base)
    base["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    return base

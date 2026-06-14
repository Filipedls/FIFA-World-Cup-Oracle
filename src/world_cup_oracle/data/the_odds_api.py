"""The Odds API (the-odds-api.com) — betting odds layered onto any base source.

Free tier: 500 requests/month, regions=us, h2h (moneyline) market. We average
the implied probabilities across all returned bookmakers, then attach a decimal
{home, draw, away} price to each matching fixture (matched on the unordered pair
of team names, re-orienting if the bookmaker lists the teams the other way).
"""
from __future__ import annotations

import requests

from ..config import ODDS_API_REGIONS, ODDS_API_SPORT
from ..teams import canonical_name

BASE_URL = "https://api.the-odds-api.com/v4"
_TIMEOUT = 20


class TheOddsApiError(RuntimeError):
    pass


def _fetch_events(key: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/sports/{ODDS_API_SPORT}/odds",
        params={"apiKey": key, "regions": ODDS_API_REGIONS,
                "markets": "h2h", "oddsFormat": "decimal"},
        timeout=_TIMEOUT,
    )
    if resp.status_code == 401:
        raise TheOddsApiError("Unauthorized — check THE_ODDS_API_KEY.")
    resp.raise_for_status()
    return resp.json()


def _event_prices(event: dict) -> dict | None:
    """Average implied probs across bookmakers -> decimal {home, draw, away}
    oriented to the event's own home/away naming."""
    home = canonical_name(event.get("home_team"))
    away = canonical_name(event.get("away_team"))
    if not home or not away:
        return None
    imp = {"home": [], "draw": [], "away": []}
    for bm in event.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for oc in market.get("outcomes", []):
                price = oc.get("price")
                name = canonical_name(oc.get("name"))
                if not price:
                    continue
                if name == home:
                    imp["home"].append(1.0 / price)
                elif name == away:
                    imp["away"].append(1.0 / price)
                elif (oc.get("name") or "").lower() == "draw":
                    imp["draw"].append(1.0 / price)
    if not imp["home"] or not imp["away"]:
        return None
    avg = lambda xs: sum(xs) / len(xs)
    return {
        "home_team": home,
        "away_team": away,
        "odds": {
            "home": 1.0 / avg(imp["home"]),
            "away": 1.0 / avg(imp["away"]),
            "draw": (1.0 / avg(imp["draw"])) if imp["draw"] else None,
        },
    }


def enrich(dataset: dict, key: str) -> int:
    """Attach odds to fixtures in-place. Returns how many fixtures were priced."""
    by_pair: dict[frozenset, dict] = {}
    for event in _fetch_events(key):
        priced = _event_prices(event)
        if priced:
            by_pair[frozenset((priced["home_team"], priced["away_team"]))] = priced

    n = 0
    for fx in dataset.get("fixtures", []):
        if fx.get("odds"):
            continue
        priced = by_pair.get(frozenset((fx["home"], fx["away"])))
        if not priced:
            continue
        odds = priced["odds"]
        # re-orient if the bookmaker listed home/away the other way round
        if priced["home_team"] == fx["home"]:
            fx["odds"] = dict(odds)
        else:
            fx["odds"] = {"home": odds["away"], "away": odds["home"], "draw": odds["draw"]}
        n += 1
    return n

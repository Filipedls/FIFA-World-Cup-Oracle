"""API-Football (api-sports.io v3) client.

Pulls fixtures, match-winner odds and top scorers for the World Cup and maps
them onto the normalised dataset schema documented in :mod:`world_cup_oracle.data`.

Only a handful of endpoints are needed because standings/probabilities are all
derived locally from fixtures + odds:

    GET /fixtures?league=&season=
    GET /odds?league=&season=&bookmaker=&bet=1   (bet 1 = Match Winner)
    GET /players/topscorers?league=&season=
"""
from __future__ import annotations

import requests

from ..config import (API_BASE_URL, ODDS_BOOKMAKER_ID, WORLD_CUP_LEAGUE_ID,
                      WORLD_CUP_SEASON)
from ..teams import TEAMS

_TIMEOUT = 20


class ApiFootballError(RuntimeError):
    pass


def _get(path: str, key: str, params: dict) -> list[dict]:
    """Call an endpoint, following API-Football's paging, return the merged
    ``response`` arrays."""
    headers = {"x-apisports-key": key}
    results: list[dict] = []
    page = 1
    while True:
        # Some endpoints (e.g. /fixtures, /players/topscorers) reject a `page`
        # field outright, so only send it once we actually need page 2+.
        p = {**params, "page": page} if page > 1 else dict(params)
        resp = requests.get(f"{API_BASE_URL}{path}", headers=headers, params=p, timeout=_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            raise ApiFootballError(str(body["errors"]))
        results.extend(body.get("response", []))
        paging = body.get("paging", {})
        if paging.get("current", 1) >= paging.get("total", 1):
            break
        page += 1
    return results


def _stage_from_round(round_str: str) -> tuple[str, int | None]:
    """Map API-Football's ``league.round`` to (stage, matchday)."""
    r = (round_str or "").lower()
    if "group" in r:
        md = None
        for tok in r.replace("-", " ").split():
            if tok.isdigit():
                md = int(tok)
        return "group", md
    mapping = {
        "round of 32": "Round of 32",
        "round of 16": "Round of 16",
        "quarter": "Quarter-finals",
        "semi": "Semi-finals",
        "3rd place": "Third place",
        "final": "Final",
    }
    for needle, stage in mapping.items():
        if needle in r:
            return stage, None
    return round_str or "group", None


def _odds_index(rows: list[dict]) -> dict[int, dict]:
    """fixture id -> {home,draw,away} decimal odds from the Match Winner market."""
    out: dict[int, dict] = {}
    for row in rows:
        fid = row["fixture"]["id"]
        for bm in row.get("bookmakers", []):
            for bet in bm.get("bets", []):
                if str(bet.get("id")) != "1" and bet.get("name") != "Match Winner":
                    continue
                vals = {v["value"].lower(): float(v["odd"]) for v in bet.get("values", [])}
                if {"home", "draw", "away"} <= vals.keys():
                    out[fid] = {"home": vals["home"], "draw": vals["draw"], "away": vals["away"]}
                    break
            if fid in out:
                break
    return out


def get_dataset(key: str, as_of: str) -> dict:
    fixtures_raw = _get("/fixtures", key,
                        {"league": WORLD_CUP_LEAGUE_ID, "season": WORLD_CUP_SEASON})
    odds_raw = _get("/odds", key,
                    {"league": WORLD_CUP_LEAGUE_ID, "season": WORLD_CUP_SEASON,
                     "bookmaker": ODDS_BOOKMAKER_ID, "bet": 1})
    scorers_raw = _get("/players/topscorers", key,
                       {"league": WORLD_CUP_LEAGUE_ID, "season": WORLD_CUP_SEASON})

    odds_by_fixture = _odds_index(odds_raw)
    fixtures: list[dict] = []
    for item in fixtures_raw:
        f, league, teams_, goals = (item["fixture"], item["league"],
                                    item["teams"], item["goals"])
        stage, matchday = _stage_from_round(league.get("round", ""))
        home, away = teams_["home"]["name"], teams_["away"]["name"]
        status = f["status"]["short"]
        finished = status in {"FT", "AET", "PEN"}
        fixtures.append({
            "id": f["id"],
            "stage": stage,
            "group": TEAMS[home].group if home in TEAMS else None,
            "matchday": matchday,
            "date": (f.get("date") or "")[:10],
            "kickoff": f.get("date"),   # full ISO datetime, e.g. 2026-06-11T18:00:00+00:00
            "home": home,
            "away": away,
            "status": "FT" if finished else "NS",
            "home_goals": goals["home"] if finished else None,
            "away_goals": goals["away"] if finished else None,
            "odds": odds_by_fixture.get(f["id"]),
        })

    scorers = []
    for item in scorers_raw:
        stats = (item.get("statistics") or [{}])[0]
        scorers.append({
            "player": item["player"]["name"],
            "team": stats.get("team", {}).get("name", "?"),
            "goals": (stats.get("goals") or {}).get("total") or 0,
        })
    scorers = [s for s in scorers if s["goals"]]
    return {"source": "api", "as_of": as_of, "fixtures": fixtures, "scorers": scorers}

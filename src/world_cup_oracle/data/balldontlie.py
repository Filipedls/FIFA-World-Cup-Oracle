"""BALLDONTLIE FIFA World Cup API client (https://api.balldontlie.io/fifa).

Unlike API-Football's free tier, BALLDONTLIE's free tier *covers the 2026
season* and bundles fixtures, odds and player goals in one API. Maps onto the
normalised dataset schema (see :mod:`world_cup_oracle.data`).

Notable schema differences handled here:
  * odds are American moneylines per *vendor* (DraftKings, FanDuel, …) -> we
    convert to decimal and average the implied probabilities across vendors;
  * there is no top-scorers endpoint -> we read cumulative ``goals`` from
    ``/rosters``;
  * team names differ from our roster -> normalised via :data:`_NAME_FIXUPS`.
"""
from __future__ import annotations

import requests

from ..config import WORLD_CUP_SEASON

BASE_URL = "https://api.balldontlie.io/fifa/worldcup/v1"
_TIMEOUT = 20

# BALLDONTLIE name -> our canonical name in teams.py (only the ones that differ)
_NAME_FIXUPS = {
    "USA": "United States",
    "United States of America": "United States",
    "South Korea": "Korea Republic",
    "Turkey": "Türkiye",
    "Turkiye": "Türkiye",
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Curacao": "Curaçao",
    "Cape Verde": "Cabo Verde",
    "IR Iran": "Iran",
    "Czech Republic": "Czechia",
}


class BallDontLieError(RuntimeError):
    pass


def canonical(name: str | None) -> str | None:
    if not name:
        return None
    return _NAME_FIXUPS.get(name, name)


def _get(path: str, key: str, params: dict) -> list[dict]:
    """Call an endpoint, following cursor pagination, return merged ``data``."""
    headers = {"Authorization": key}
    results: list[dict] = []
    cursor = None
    while True:
        p = dict(params)
        if cursor is not None:
            p["cursor"] = cursor
        resp = requests.get(f"{BASE_URL}{path}", headers=headers, params=p, timeout=_TIMEOUT)
        if resp.status_code == 401:
            raise BallDontLieError("Unauthorized — check WORLD_CUP_API_KEY.")
        resp.raise_for_status()
        body = resp.json()
        results.extend(body.get("data", []))
        cursor = (body.get("meta") or {}).get("next_cursor")
        if not cursor:
            break
    return results


def _american_to_decimal(odd) -> float | None:
    if odd in (None, ""):
        return None
    o = float(odd)
    return 1.0 + (o / 100.0 if o > 0 else 100.0 / -o)


def _stage_name(stage) -> str:
    name = (stage or {}).get("name", "") if isinstance(stage, dict) else str(stage or "")
    n = name.lower()
    if "group" in n:
        return "group"
    mapping = {
        "round of 32": "Round of 32",
        "round of 16": "Round of 16",
        "quarter": "Quarter-finals",
        "semi": "Semi-finals",
        "third": "Third place",
        "final": "Final",
    }
    for needle, stage_label in mapping.items():
        if needle in n:
            return stage_label
    return name or "group"


def _group_letter(group) -> str | None:
    if not isinstance(group, dict):
        return None
    name = group.get("name")
    return name.split()[-1] if name else None


def _team_name(team_obj) -> str | None:
    if not isinstance(team_obj, dict):
        return None
    return canonical(team_obj.get("name"))


def _odds_index(rows: list[dict]) -> dict[int, dict]:
    """match_id -> decimal {home, draw, away} averaged across vendors.

    We average implied probabilities (1/decimal) across vendors, then convert
    back to a decimal price so the rest of the app de-vigs it exactly as it
    would a single bookmaker line.
    """
    acc: dict[int, dict[str, list[float]]] = {}
    for row in rows:
        mid = row.get("match_id")
        if mid is None:
            continue
        bucket = acc.setdefault(mid, {"home": [], "draw": [], "away": []})
        for outcome, field in (("home", "moneyline_home_odds"),
                               ("draw", "moneyline_draw_odds"),
                               ("away", "moneyline_away_odds")):
            dec = _american_to_decimal(row.get(field))
            if dec:
                bucket[outcome].append(1.0 / dec)
    out: dict[int, dict] = {}
    for mid, imp in acc.items():
        if not imp["home"] or not imp["away"]:
            continue
        out[mid] = {
            "home": 1.0 / (sum(imp["home"]) / len(imp["home"])),
            "away": 1.0 / (sum(imp["away"]) / len(imp["away"])),
            "draw": (1.0 / (sum(imp["draw"]) / len(imp["draw"]))) if imp["draw"] else None,
        }
    return out


def _player_name(player) -> str:
    if not isinstance(player, dict):
        return "Unknown"
    if player.get("name"):
        return player["name"]
    full = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
    return full or "Unknown"


def get_dataset(key: str, as_of: str) -> dict:
    season = WORLD_CUP_SEASON
    matches = _get("/matches", key, {"seasons[]": season, "per_page": 100})
    odds_rows = _get("/odds", key, {"seasons[]": season, "per_page": 100})
    teams_rows = _get("/teams", key, {"seasons[]": season})
    rosters = _get("/rosters", key, {"seasons[]": season, "per_page": 100})

    odds_by_match = _odds_index(odds_rows)
    id_to_name = {t["id"]: canonical(t.get("name")) for t in teams_rows if t.get("id")}

    fixtures: list[dict] = []
    for m in matches:
        home = _team_name(m.get("home_team"))
        away = _team_name(m.get("away_team"))
        if not home or not away:
            continue  # undecided knockout slot; the projected bracket fills these
        finished = m.get("status") == "completed"
        dt = m.get("datetime") or ""
        fixtures.append({
            "id": m["id"],
            "stage": _stage_name(m.get("stage")),
            "group": _group_letter(m.get("group")),
            "matchday": None,
            "date": dt[:10],
            "kickoff": dt or None,
            "home": home,
            "away": away,
            "status": "FT" if finished else "NS",
            "home_goals": m.get("home_score") if finished else None,
            "away_goals": m.get("away_score") if finished else None,
            "odds": odds_by_match.get(m["id"]),
        })

    scorers = []
    for r in rosters:
        goals = r.get("goals") or 0
        if not goals:
            continue
        scorers.append({
            "player": _player_name(r.get("player")),
            "team": id_to_name.get(r.get("team_id"), "?"),
            "goals": goals,
        })
    scorers.sort(key=lambda s: -s["goals"])
    return {"source": "balldontlie", "as_of": as_of, "fixtures": fixtures, "scorers": scorers}

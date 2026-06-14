"""worldcup26.ir client — a free, open community API for the 2026 World Cup.

No API key required. Provides all 104 games (with scores and embedded goal
scorers), teams and group tables. It does *not* provide betting odds — those are
layered on separately via :mod:`.the_odds_api` when a key is configured.

Caveats handled here:
  * it's a single-maintainer hobby server, so requests are retried on transient
    network/SSL errors;
  * goal scorers are an embedded string like ``{“J. Quiñones 9'”,”R. Jiménez 67'”}``
    (curly quotes, "name minute'") which we parse to one goal per entry;
  * knockout games carry ``null`` team names until drawn — those are skipped and
    filled in by the projected bracket instead.
"""
from __future__ import annotations

import re
import time

import requests

BASE_URL = "https://worldcup26.ir"
_TIMEOUT = 20
_RETRIES = 3

_TYPE_TO_STAGE = {
    "group": "group",
    "r32": "Round of 32",
    "r16": "Round of 16",
    "qf": "Quarter-finals",
    "sf": "Semi-finals",
    "third": "Third place",
    "final": "Final",
}

# strip braces and the various (curly/straight) double-quote characters
_STRIP_CHARS = "{}\"“”„‟"


class WorldCup26Error(RuntimeError):
    pass


def _get(path: str) -> dict:
    last = None
    for attempt in range(_RETRIES):
        try:
            resp = requests.get(f"{BASE_URL}{path}", timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:  # transient SSL/network blips
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise WorldCup26Error(f"{path} failed after {_RETRIES} tries: {last}")


def _kickoff_and_date(local_date: str) -> tuple[str | None, str]:
    """'06/11/2026 13:00' -> ('2026-06-11T13:00:00', '2026-06-11')."""
    try:
        from datetime import datetime
        dt = datetime.strptime(local_date.strip(), "%m/%d/%Y %H:%M")
        return dt.isoformat(), dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None, (local_date or "")[:10]


def _parse_scorers(raw: str | None) -> list[str]:
    """Return one player name per goal from an embedded scorers string."""
    if not raw:
        return []
    s = raw.strip()
    if s.lower() in ("null", "{}", "[]", ""):
        return []
    names: list[str] = []
    for part in s.strip("{}").split(","):
        token = part.strip().strip(_STRIP_CHARS).strip()
        if not token:
            continue
        # name is everything before the first " <digit>" (minute marker)
        name = re.split(r"\s+\d", token)[0].strip().strip(_STRIP_CHARS).strip()
        if name:
            names.append(name)
    return names


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_dataset(as_of: str) -> dict:
    from ..teams import canonical_name

    games = _get("/get/games").get("games", [])
    fixtures: list[dict] = []
    goals: dict[tuple[str, str], int] = {}

    for g in games:
        home = canonical_name(g.get("home_team_name_en"))
        away = canonical_name(g.get("away_team_name_en"))
        if not home or not away:
            continue  # undecided knockout slot
        finished = str(g.get("finished", "")).upper() == "TRUE"
        kickoff, date = _kickoff_and_date(g.get("local_date", ""))
        gtype = (g.get("type") or "group").lower()
        stage = _TYPE_TO_STAGE.get(gtype, gtype)
        fixtures.append({
            "id": _to_int(g.get("id")),
            "stage": stage,
            "group": g.get("group") if stage == "group" else None,
            "matchday": _to_int(g.get("matchday")),
            "date": date,
            "kickoff": kickoff,
            "home": home,
            "away": away,
            "status": "FT" if finished else "NS",
            "home_goals": _to_int(g.get("home_score")) if finished else None,
            "away_goals": _to_int(g.get("away_score")) if finished else None,
            "odds": None,  # enriched by the_odds_api if a key is configured
        })
        if finished:
            for player in _parse_scorers(g.get("home_scorers")):
                goals[(player, home)] = goals.get((player, home), 0) + 1
            for player in _parse_scorers(g.get("away_scorers")):
                goals[(player, away)] = goals.get((player, away), 0) + 1

    scorers = [{"player": p, "team": t, "goals": n}
               for (p, t), n in sorted(goals.items(), key=lambda kv: (-kv[1], kv[0][0]))]
    return {"source": "worldcup26", "as_of": as_of, "fixtures": fixtures, "scorers": scorers}

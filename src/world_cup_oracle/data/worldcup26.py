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

# worldcup26 'local_date' is the VENUE-local kickoff time, so it must be
# interpreted in the stadium's timezone before converting to UTC. Map the host
# city to its IANA zone (Mexico has no DST since 2022).
_CITY_TZ = {
    "seattle": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
    "san francisco bay area": "America/Los_Angeles", "vancouver": "America/Vancouver",
    "houston": "America/Chicago", "dallas": "America/Chicago",
    "kansas city": "America/Chicago", "atlanta": "America/New_York",
    "miami": "America/New_York", "boston": "America/New_York",
    "philadelphia": "America/New_York", "new york/new jersey": "America/New_York",
    "toronto": "America/Toronto", "mexico city": "America/Mexico_City",
    "guadalajara": "America/Mexico_City", "monterrey": "America/Monterrey",
}
# fallback by worldcup26 stadium id, if the /stadiums lookup is unavailable
_STADIUM_TZ_BY_ID = {
    "1": "America/Mexico_City", "2": "America/Mexico_City", "3": "America/Monterrey",
    "4": "America/Chicago", "5": "America/Chicago", "6": "America/Chicago",
    "7": "America/New_York", "8": "America/New_York", "9": "America/New_York",
    "10": "America/New_York", "11": "America/New_York", "12": "America/Toronto",
    "13": "America/Vancouver", "14": "America/Los_Angeles",
    "15": "America/Los_Angeles", "16": "America/Los_Angeles",
}


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


def _stadium_timezones() -> dict[str, str]:
    """stadium id -> IANA timezone, from the /stadiums endpoint (city), with a
    hard-coded id fallback if the lookup fails."""
    try:
        stadiums = _get("/get/stadiums").get("stadiums", [])
    except WorldCup26Error:
        return dict(_STADIUM_TZ_BY_ID)
    out: dict[str, str] = {}
    for s in stadiums:
        sid = str(s.get("id"))
        city = (s.get("city_en") or "").split("(")[0].strip().lower()
        tz = _CITY_TZ.get(city) or _STADIUM_TZ_BY_ID.get(sid)
        if tz:
            out[sid] = tz
    for sid, tz in _STADIUM_TZ_BY_ID.items():
        out.setdefault(sid, tz)
    return out


def _kickoff_and_date(local_date: str, tzname: str | None) -> tuple[str | None, str]:
    """Venue-local 'MM/DD/YYYY HH:MM' -> (UTC ISO kickoff, venue-local date).

    The time is localised in the stadium's timezone, then converted to UTC so
    the rest of the app can render it in any display timezone.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        dt = datetime.strptime(local_date.strip(), "%m/%d/%Y %H:%M")
    except (ValueError, AttributeError):
        return None, (local_date or "")[:10]
    date = dt.strftime("%Y-%m-%d")          # the calendar day at the venue
    if tzname:
        try:
            dt = dt.replace(tzinfo=ZoneInfo(tzname)).astimezone(ZoneInfo("UTC"))
        except Exception:                    # noqa: BLE001 - unknown zone -> naive
            pass
    return dt.isoformat(), date


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
    stadium_tz = _stadium_timezones()
    fixtures: list[dict] = []
    goals: dict[tuple[str, str], int] = {}

    for g in games:
        home = canonical_name(g.get("home_team_name_en"))
        away = canonical_name(g.get("away_team_name_en"))
        if not home or not away:
            continue  # undecided knockout slot
        finished = str(g.get("finished", "")).upper() == "TRUE"
        tzname = stadium_tz.get(str(g.get("stadium_id")))
        kickoff, date = _kickoff_and_date(g.get("local_date", ""), tzname)
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

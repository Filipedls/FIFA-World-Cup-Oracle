"""Tournament-wide summary statistics derived from fixtures + scorers."""
from __future__ import annotations


def _played(fixtures: list[dict]) -> list[dict]:
    return [f for f in fixtures if f["status"] == "FT"
            and f["home_goals"] is not None and f["away_goals"] is not None]


def compute_stats(fixtures: list[dict], scorers: list[dict]) -> dict:
    played = _played(fixtures)
    n_played = len(played)
    home_goals = sum(f["home_goals"] for f in played)
    away_goals = sum(f["away_goals"] for f in played)
    total_goals = home_goals + away_goals

    goalless = sum(1 for f in played if f["home_goals"] == 0 and f["away_goals"] == 0)
    # a clean sheet = a side that conceded zero; count per team-performance
    clean_sheets = sum((f["away_goals"] == 0) + (f["home_goals"] == 0) for f in played)

    highest = max(played, key=lambda f: f["home_goals"] + f["away_goals"], default=None)
    biggest = max(played, key=lambda f: abs(f["home_goals"] - f["away_goals"]), default=None)

    return {
        "matches_scheduled": len(fixtures),
        "matches_played": n_played,
        "total_goals": total_goals,
        "avg_goals": (total_goals / n_played) if n_played else 0.0,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "goalless_draws": goalless,
        "clean_sheets": clean_sheets,
        "distinct_scorers": len(scorers),
        "teams_scored": len({s["team"] for s in scorers}),
        "top_scorer": scorers[0] if scorers else None,
        "highest_scoring": _match_summary(highest),
        "biggest_win": _match_summary(biggest),
    }


def _match_summary(f: dict | None) -> dict | None:
    if not f:
        return None
    return {
        "home": f["home"], "away": f["away"],
        "home_goals": f["home_goals"], "away_goals": f["away_goals"],
        "total": f["home_goals"] + f["away_goals"],
        "margin": abs(f["home_goals"] - f["away_goals"]),
        "date": f.get("date", ""),
    }

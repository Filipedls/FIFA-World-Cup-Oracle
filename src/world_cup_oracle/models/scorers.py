"""Project each scorer's final goal tally for the tournament.

rate   = goals so far / matches their team has played so far
total  = rate x expected total matches for their team (from the simulation)

So a striker scoring at 1 goal/game whose team is expected to reach the
quarter-finals (~5 matches) projects to ~5 goals.

The raw rate is regularised toward a modest baseline (Bayesian shrinkage) so a
player with, say, 3 goals in a single match doesn't project to ~15 — early in
the tournament the denominator is tiny and unshrunk rates explode.
"""
from __future__ import annotations

# Shrinkage prior: equivalent to having already seen PRIOR_WEIGHT matches at
# PRIOR_RATE goals/game before counting the player's real games.
PRIOR_RATE = 0.45
PRIOR_WEIGHT = 1.5


def team_games_played(fixtures: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in fixtures:
        if f["status"] != "FT":
            continue
        for team in (f["home"], f["away"]):
            counts[team] = counts.get(team, 0) + 1
    return counts


def project_scorers(scorers: list[dict], fixtures: list[dict],
                    expected_games: dict[str, float]) -> list[dict]:
    played = team_games_played(fixtures)
    rows = []
    for s in scorers:
        team = s["team"]
        gp = played.get(team, 0)
        raw_rate = s["goals"] / gp if gp else 0.0
        # the projection uses a rate shrunk toward PRIOR_RATE so tiny
        # denominators (e.g. 2 goals in 1 game) don't explode the forecast
        shrunk_rate = (s["goals"] + PRIOR_RATE * PRIOR_WEIGHT) / (gp + PRIOR_WEIGHT)
        exp_games = expected_games.get(team, 3.0)
        projected = shrunk_rate * exp_games
        rows.append({
            "Player": s["player"],
            "Team": team,
            "Goals": s["goals"],
            "Team games": gp,
            "Goals/game": round(raw_rate, 2),
            "Proj. team games": round(exp_games, 1),
            "Projected goals": round(projected, 1),
        })
    rows.sort(key=lambda r: (-r["Projected goals"], -r["Goals"], r["Player"]))
    return rows

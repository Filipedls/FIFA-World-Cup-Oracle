"""Data-driven team power ratings.

Each team's rating is a 0–1 "win-equivalent" strength, blended from three
sources per group match:

  * finished match -> the actual result (win 1.0 / draw 0.5 / loss 0.0)
  * unplayed match with odds -> market expectation P(win) + ½·P(draw)
  * otherwise -> no signal

These are averaged together with the hand-set prior from ``teams.py`` (which
also covers teams with no data yet), so ratings start at the prior and move
toward what the market and results say as the tournament unfolds.
"""
from __future__ import annotations

from collections import defaultdict

from ..teams import power_of
from .odds import implied_from_decimal

# How many "phantom matches" of the prior to mix in. Higher = stickier prior.
PRIOR_WEIGHT = 1.5


def _result_signal(home_goals: int, away_goals: int) -> tuple[float, float]:
    if home_goals > away_goals:
        return 1.0, 0.0
    if home_goals < away_goals:
        return 0.0, 1.0
    return 0.5, 0.5


def compute_ratings(fixtures: list[dict], prior_weight: float = PRIOR_WEIGHT) -> dict[str, float]:
    signals: dict[str, list[float]] = defaultdict(list)
    teams: set[str] = set()

    for f in fixtures:
        if f.get("stage") != "group":
            continue
        home, away = f.get("home"), f.get("away")
        if not home or not away:
            continue
        teams.update((home, away))
        if f["status"] == "FT" and f["home_goals"] is not None:
            sh, sa = _result_signal(f["home_goals"], f["away_goals"])
            signals[home].append(sh)
            signals[away].append(sa)
        elif f.get("odds"):
            p = implied_from_decimal(f["odds"])
            signals[home].append(p.home + 0.5 * p.draw)
            signals[away].append(p.away + 0.5 * p.draw)

    ratings: dict[str, float] = {}
    for team in teams:
        prior = power_of(team)
        s = signals.get(team, [])
        ratings[team] = (prior_weight * prior + sum(s)) / (prior_weight + len(s))
    return ratings


def power_func(ratings: dict[str, float]):
    """Return a ``name -> power`` callable backed by ratings, falling back to the
    static prior for any team not present."""
    return lambda name: ratings.get(name, power_of(name))

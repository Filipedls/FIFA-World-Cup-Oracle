"""Monte Carlo simulation of the whole tournament.

Group matches are driven by the bookmaker-implied probabilities (the numbers
shown in the matches table); their scorelines — needed for goal-difference
tiebreakers — come from a Poisson model seeded by the same power ratings.
Knockout ties use the power-rating model (the future opponents are unknown to
the bookmakers). Outputs, per team:

  * P(reach each stage)  -> STAGE_LABELS
  * expected number of matches played  -> used to project total goals
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import (DEFAULT_SIMULATIONS, KNOCKOUT_SCALE, SIM_SEED,
                      STAGE_LABELS, THIRD_PLACE_QUALIFIERS)
from . import bracket
from .odds import implied_from_decimal, poisson_lambdas, probs_from_power
from .ratings import compute_ratings
from .standings import fixture_groups, group_members


@dataclass
class SimulationResult:
    stage_probs: dict[str, dict[str, float]]   # team -> {stage label: prob}
    expected_games: dict[str, float]           # team -> expected matches played
    n_sims: int
    # most-frequent occupant of each bracket slot across all simulations,
    # keyed like project_qualifiers: ("W", "A") / ("R", "B") / ("T", k)
    most_likely_slots: dict[tuple, str]

    def champion_odds(self) -> list[tuple[str, float]]:
        return sorted(((t, p["Winner"]) for t, p in self.stage_probs.items()),
                      key=lambda kv: -kv[1])

    def most_likely_qualifiers(self) -> dict[tuple, str]:
        return self.most_likely_slots


def _match_outcome_probs(fx: dict, pw) -> tuple[float, float, float]:
    if fx.get("odds"):
        p = implied_from_decimal(fx["odds"])
        return p.home, p.draw, p.away
    p = probs_from_power(pw(fx["home"]), pw(fx["away"]))
    return p.home, p.draw, p.away


def _sample_scoreline(outcome: np.ndarray, lam_h: float, lam_a: float, rng) -> tuple[np.ndarray, np.ndarray]:
    """Sample (home_goals, away_goals) consistent with a sampled outcome code
    (0=home win, 1=draw, 2=away win)."""
    n = outcome.shape[0]
    hg = rng.poisson(lam_h, n)
    ag = rng.poisson(lam_a, n)
    home_win, draw, away_win = outcome == 0, outcome == 1, outcome == 2
    # force consistency with the drawn outcome
    bad = home_win & (hg <= ag)
    hg[bad] = ag[bad] + 1
    bad = away_win & (ag <= hg)
    ag[bad] = hg[bad] + 1
    hg[draw] = ag[draw]
    return hg, ag


def run(fixtures: list[dict], n_sims: int = DEFAULT_SIMULATIONS) -> SimulationResult:
    rng = np.random.default_rng(SIM_SEED)
    # team universe + group membership are derived from the data, so the sim
    # works regardless of the source's naming or which teams qualified.
    groups = {g: group_members(fixtures, g) for g in fixture_groups(fixtures)}
    teams = sorted({t for members in groups.values() for t in members}
                   | {f[side] for f in fixtures for side in ("home", "away") if f.get(side)})
    idx = {t: i for i, t in enumerate(teams)}
    # data-driven strength (odds + results + prior); falls back to 0.5
    ratings = compute_ratings(fixtures)
    pw = lambda t: ratings.get(t, 0.5)  # noqa: E731
    power = np.array([pw(t) for t in teams])
    n_teams = len(teams)
    group_letters = list(groups)

    # --- group stage: accumulate points / goal diff / goals for, per team -----
    pts = np.zeros((n_teams, n_sims))
    gd = np.zeros((n_teams, n_sims))
    gf = np.zeros((n_teams, n_sims))

    group_fx = [f for f in fixtures if f["stage"] == "group"]
    for fx in group_fx:
        h, a = idx[fx["home"]], idx[fx["away"]]
        if fx["status"] == "FT":
            hg = np.full(n_sims, fx["home_goals"])
            ag = np.full(n_sims, fx["away_goals"])
        else:
            ph, pd, pa = _match_outcome_probs(fx, pw)
            outcome = rng.choice(3, size=n_sims, p=[ph, pd, pa])
            lam_h, lam_a = poisson_lambdas(pw(fx["home"]), pw(fx["away"]))
            hg, ag = _sample_scoreline(outcome, lam_h, lam_a, rng)
        pts[h] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
        pts[a] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        gd[h] += hg - ag; gd[a] += ag - hg
        gf[h] += hg; gf[a] += ag

    # ranking key (bigger = better); tiny noise breaks exact ties per sim
    noise = rng.random((n_teams, n_sims)) * 1e-3
    rank_key = pts * 1e6 + gd * 1e3 + gf + noise

    # winners / runners-up / thirds per group (arrays of team idx, shape (n_sims,))
    winners: dict[str, np.ndarray] = {}
    runners: dict[str, np.ndarray] = {}
    n_groups = len(group_letters)
    third_idx = np.empty((n_groups, n_sims), dtype=int)
    third_key = np.empty((n_groups, n_sims))
    for gi, g in enumerate(group_letters):
        members = np.array([idx[t] for t in groups[g]])
        keys = rank_key[members]                      # (n_in_group, n_sims)
        order = np.argsort(-keys, axis=0)             # best -> worst
        winners[g] = members[order[0]]
        runners[g] = members[order[1]]
        third_local = order[2]
        third_idx[gi] = members[third_local]
        third_key[gi] = keys[third_local, np.arange(n_sims)]

    # best N third-placed teams across the groups, per sim
    third_order = np.argsort(-third_key, axis=0)      # (n_groups, n_sims)
    qualifying_thirds = [third_idx[third_order[k], np.arange(n_sims)]
                         for k in range(THIRD_PLACE_QUALIFIERS)]

    def resolve(slot) -> np.ndarray:
        kind, ref = slot
        if kind == "W":
            return winners[ref]
        if kind == "R":
            return runners[ref]
        return qualifying_thirds[ref]

    # --- knockouts ------------------------------------------------------------
    # reached[stage_label] is a boolean (n_teams, n_sims): did the team play in
    # / advance past that stage.
    qualified = np.zeros((n_teams, n_sims), dtype=bool)
    slots = [resolve(s) for match in bracket.R32_MATCHES for s in match]
    for slot_team in slots:
        qualified[slot_team, np.arange(n_sims)] = True

    reach = {STAGE_LABELS[0]: qualified.copy()}     # "Advance"
    games = qualified.astype(float).copy()          # plays one match per round reached

    # current participants as flat list of (n_sims,) arrays, one per slot
    current = slots
    for r, name in enumerate(bracket.ROUND_NAMES):
        next_round: list[np.ndarray] = []
        winners_mask = np.zeros((n_teams, n_sims), dtype=bool)
        for m in range(bracket.ROUND_SIZES[r]):
            a_team, b_team = current[2 * m], current[2 * m + 1]
            pa = power[a_team]
            pb = power[b_team]
            p_a_wins = _two_way(pa, pb)
            a_wins = rng.random(n_sims) < p_a_wins
            win_team = np.where(a_wins, a_team, b_team)
            next_round.append(win_team)
            winners_mask[win_team, np.arange(n_sims)] = True
        # winners of round r reach the next stage (R16, QF, SF, Final, Winner)
        next_label = STAGE_LABELS[r + 1]
        reach[next_label] = winners_mask
        # reaching a stage below "Winner" means playing one more match
        if next_label != "Winner":
            games += winners_mask.astype(float)
        current = next_round

    # --- aggregate ------------------------------------------------------------
    stage_probs: dict[str, dict[str, float]] = {}
    expected_games: dict[str, float] = {}
    for t in teams:
        i = idx[t]
        stage_probs[t] = {label: float(reach[label][i].mean()) for label in STAGE_LABELS}
        # 3 group games are always played; add expected knockout games
        expected_games[t] = 3.0 + float(games[i].mean())

    team_group = {t: g for g, members in groups.items() for t in members}
    ml_slots = _most_likely_slots(group_letters, winners, runners,
                                  qualifying_thirds, teams, n_teams, team_group)
    return SimulationResult(stage_probs, expected_games, n_sims, ml_slots)


def _most_likely_slots(group_letters, winners, runners, qualifying_thirds,
                       teams, n_teams, team_group) -> dict[tuple, str]:
    """Pick each bracket slot's most-frequent occupant across simulations: the
    modal group winner, modal runner-up, and the 8 most-frequent third-place
    qualifiers, then route them through the official confederation-aware layout."""
    winners_by_group: dict[str, str] = {}
    runners_by_group: dict[str, str] = {}
    chosen: set[str] = set()
    for g in group_letters:
        w_team = teams[int(np.bincount(winners[g], minlength=n_teams).argmax())]
        winners_by_group[g] = w_team
        for r_idx in np.argsort(-np.bincount(runners[g], minlength=n_teams)):
            if teams[int(r_idx)] != w_team:
                runners_by_group[g] = teams[int(r_idx)]
                break
        chosen.update({winners_by_group[g], runners_by_group.get(g)})

    third_counts = np.zeros(n_teams)
    for arr in qualifying_thirds:
        third_counts += np.bincount(arr, minlength=n_teams)
    thirds: list[tuple] = []
    for i in np.argsort(-third_counts):
        team = teams[int(i)]
        if team in chosen or team not in team_group:
            continue
        thirds.append((team, team_group[team], float(third_counts[int(i)])))
        if len(thirds) >= THIRD_PLACE_QUALIFIERS:
            break
    return bracket.build_slot_teams(winners_by_group, runners_by_group, thirds)


def _two_way(power_a: np.ndarray, power_b: np.ndarray) -> np.ndarray:
    """Probability team A beats team B in a knockout (no draws); vectorised twin
    of :func:`odds.knockout_win_prob` (same logistic + KNOCKOUT_SCALE)."""
    return 1.0 / (1.0 + np.exp(-KNOCKOUT_SCALE * (power_a - power_b)))

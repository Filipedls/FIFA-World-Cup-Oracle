"""Convert bookmaker odds to fair (vig-free) win/draw/loss probabilities, and
relate them to the power-rating goal model used by the simulation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import GOAL_BASE, GOAL_POWER_SCALE, KNOCKOUT_SCALE


@dataclass(frozen=True)
class MatchProbs:
    home: float
    draw: float
    away: float

    def as_dict(self) -> dict[str, float]:
        return {"home": self.home, "draw": self.draw, "away": self.away}


def implied_from_decimal(odds: dict[str, float]) -> MatchProbs:
    """Decimal odds -> normalised (vig-removed) probabilities.

    Implied probability of a decimal price is 1/price; bookmaker margins make
    these sum to >1, so we divide by the total ("multiplicative" de-vig).
    """
    raw_home = 1.0 / odds["home"]
    raw_away = 1.0 / odds["away"]
    raw_draw = 1.0 / odds["draw"] if odds.get("draw") else 0.0
    total = raw_home + raw_draw + raw_away
    if total <= 0:
        return MatchProbs(1 / 3, 1 / 3, 1 / 3)
    return MatchProbs(raw_home / total, raw_draw / total, raw_away / total)


def poisson_lambdas(power_home: float, power_away: float,
                    home_advantage: float = 0.10) -> tuple[float, float]:
    """Expected goals for each team from their power ratings.

    A rating edge multiplies expected goals up/down exponentially; the home
    side (or, in neutral knockouts, the nominal "home" slot) gets a small bump.
    """
    diff = (power_home + home_advantage) - power_away
    lam_home = GOAL_BASE * math.exp(GOAL_POWER_SCALE * diff)
    lam_away = GOAL_BASE * math.exp(-GOAL_POWER_SCALE * diff)
    return lam_home, lam_away


def probs_from_power(power_home: float, power_away: float,
                     home_advantage: float = 0.10, max_goals: int = 10) -> MatchProbs:
    """Win/draw/loss probabilities implied by the Poisson goal model.

    Used to display probabilities for fixtures with no bookmaker odds and to
    sanity-check the market numbers.
    """
    lam_h, lam_a = poisson_lambdas(power_home, power_away, home_advantage)
    ph = _poisson_pmf(lam_h, max_goals)
    pa = _poisson_pmf(lam_a, max_goals)
    home = draw = away = 0.0
    for gh in range(max_goals + 1):
        for ga in range(max_goals + 1):
            p = ph[gh] * pa[ga]
            if gh > ga:
                home += p
            elif gh == ga:
                draw += p
            else:
                away += p
    total = home + draw + away
    return MatchProbs(home / total, draw / total, away / total)


def _poisson_pmf(lam: float, max_k: int) -> list[float]:
    out = []
    for k in range(max_k + 1):
        out.append(math.exp(-lam) * lam**k / math.factorial(k))
    return out


def knockout_win_prob(power_a: float, power_b: float) -> float:
    """Probability team A beats team B in a knockout tie (no draw): a logistic
    on the power-rating gap. Matches the model used by the simulation."""
    return 1.0 / (1.0 + math.exp(-KNOCKOUT_SCALE * (power_a - power_b)))


def odds_from_power(power_home: float, power_away: float,
                    margin: float = 0.06, home_advantage: float = 0.10) -> dict[str, float]:
    """Inverse of :func:`implied_from_decimal`: build plausible bookmaker
    decimal odds (with a margin baked in) from power ratings. Used only by the
    offline sample-data generator.
    """
    probs = probs_from_power(power_home, power_away, home_advantage)
    scale = 1.0 + margin
    return {
        "home": round(scale / max(probs.home, 1e-3), 2),
        "draw": round(scale / max(probs.draw, 1e-3), 2),
        "away": round(scale / max(probs.away, 1e-3), 2),
    }

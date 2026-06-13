"""Odds <-> probability conversions."""
import pytest

from world_cup_oracle.models.odds import (implied_from_decimal, odds_from_power,
                                          probs_from_power)


def test_implied_probs_sum_to_one_and_remove_vig():
    probs = implied_from_decimal({"home": 2.0, "draw": 4.0, "away": 4.0})
    assert probs.home + probs.draw + probs.away == pytest.approx(1.0)
    # raw implied (0.5 + 0.25 + 0.25 = 1.0 here) -> favourite still strongest
    assert probs.home > probs.away


def test_stronger_team_has_higher_win_probability():
    p = probs_from_power(0.85, 0.35)
    assert p.home > p.away
    assert p.home + p.draw + p.away == pytest.approx(1.0, abs=1e-6)


def test_odds_from_power_roundtrip_keeps_favourite():
    odds = odds_from_power(0.80, 0.40)
    # shorter (smaller) price on the stronger home side
    assert odds["home"] < odds["away"]
    probs = implied_from_decimal(odds)
    assert probs.home > probs.away

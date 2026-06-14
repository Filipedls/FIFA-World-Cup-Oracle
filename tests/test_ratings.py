"""Data-driven team ratings."""
import pytest

from world_cup_oracle.models.ratings import compute_ratings, power_func
from world_cup_oracle.teams import power_of


def _g(home, away, status="NS", hg=None, ag=None, odds=None):
    return {"stage": "group", "group": "A", "home": home, "away": away,
            "status": status, "home_goals": hg, "away_goals": ag, "odds": odds}


def test_no_signal_falls_back_to_prior():
    # no odds, no results -> rating equals the hand-set prior
    r = compute_ratings([_g("Brazil", "Haiti")])
    assert r["Brazil"] == pytest.approx(power_of("Brazil"))
    assert r["Haiti"] == pytest.approx(power_of("Haiti"))


def test_finished_win_lifts_rating_above_loser():
    fixtures = [_g("Haiti", "Brazil", status="FT", hg=3, ag=0)]
    r = compute_ratings(fixtures)
    # a 3-0 win drags Haiti's rating up toward its winning result...
    assert r["Haiti"] > power_of("Haiti")
    assert r["Brazil"] < power_of("Brazil")
    assert r["Haiti"] > r["Brazil"]


def test_odds_move_rating_toward_market():
    # strong home favourite by the market -> rating rises vs its prior
    fixtures = [_g("Haiti", "Brazil", odds={"home": 1.2, "draw": 6.0, "away": 12.0})]
    r = compute_ratings(fixtures)
    assert r["Haiti"] > power_of("Haiti")


def test_power_func_falls_back_for_unknown_team():
    p = power_func({"Brazil": 0.9})
    assert p("Brazil") == 0.9
    assert p("Some Unknown FC") == power_of("Some Unknown FC")  # default 0.5

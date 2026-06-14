"""Tournament summary statistics."""
from world_cup_oracle.models.stats import compute_stats


def _ft(home, away, hg, ag):
    return {"id": 1, "stage": "group", "group": "A", "date": "2026-06-11",
            "home": home, "away": away, "status": "FT",
            "home_goals": hg, "away_goals": ag, "odds": None}


def _ns(home, away):
    return {**_ft(home, away, 0, 0), "status": "NS",
            "home_goals": None, "away_goals": None}


def test_core_counts_and_average():
    fixtures = [_ft("A", "B", 3, 1), _ft("C", "D", 0, 0), _ns("E", "F")]
    scorers = [{"player": "X", "team": "A", "goals": 3},
               {"player": "Y", "team": "B", "goals": 1}]
    s = compute_stats(fixtures, scorers)

    assert s["matches_scheduled"] == 3
    assert s["matches_played"] == 2          # NS excluded
    assert s["total_goals"] == 4             # 3+1+0+0
    assert s["avg_goals"] == 2.0
    assert s["home_goals"] == 3 and s["away_goals"] == 1
    assert s["goalless_draws"] == 1
    # 3-1 -> nobody kept a clean sheet; 0-0 -> both teams did
    assert s["clean_sheets"] == 2
    assert s["distinct_scorers"] == 2
    assert s["teams_scored"] == 2
    assert s["top_scorer"]["player"] == "X"


def test_highest_scoring_and_biggest_win():
    fixtures = [_ft("A", "B", 3, 2), _ft("C", "D", 5, 0)]
    s = compute_stats(fixtures, [])
    assert (s["highest_scoring"]["total"]) == 5          # both total 5; first max wins
    assert s["biggest_win"]["margin"] == 5
    assert (s["biggest_win"]["home"], s["biggest_win"]["away"]) == ("C", "D")


def test_empty_when_nothing_played():
    s = compute_stats([_ns("A", "B")], [])
    assert s["matches_played"] == 0
    assert s["avg_goals"] == 0.0
    assert s["top_scorer"] is None
    assert s["highest_scoring"] is None

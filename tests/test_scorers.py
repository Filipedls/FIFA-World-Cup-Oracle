"""Scorer goal projection (with shrinkage)."""
from world_cup_oracle.models.scorers import project_scorers, team_games_played


def _ft(home, away, hg, ag):
    return {"id": 1, "stage": "group", "group": "A", "matchday": 1,
            "date": "2026-06-11", "home": home, "away": away,
            "status": "FT", "home_goals": hg, "away_goals": ag, "odds": None}


def test_team_games_played_counts_only_finished():
    fixtures = [
        _ft("Spain", "Uruguay", 2, 1),
        {**_ft("Spain", "Cabo Verde", 0, 0), "status": "NS",
         "home_goals": None, "away_goals": None},
    ]
    counts = team_games_played(fixtures)
    assert counts["Spain"] == 1
    assert counts.get("Cabo Verde", 0) == 0  # their match not played


def test_projection_scales_with_expected_games():
    fixtures = [_ft("Spain", "Uruguay", 2, 0)]
    scorers = [{"player": "Striker", "team": "Spain", "goals": 2}]
    proj = project_scorers(scorers, fixtures, {"Spain": 6.0})
    row = proj[0]
    assert row["Projected goals"] > row["Goals"]  # more games to come


def test_goals_per_game_column_is_raw_not_shrunk():
    # 2 goals in 1 team game -> the displayed rate must be exactly 2.0
    fixtures = [_ft("Spain", "Uruguay", 2, 0)]
    scorers = [{"player": "Striker", "team": "Spain", "goals": 2}]
    row = project_scorers(scorers, fixtures, {"Spain": 5.0})[0]
    assert row["Goals/game"] == 2.0


def test_shrinkage_tames_tiny_denominator():
    # 3 goals in 1 game should NOT naively project to 3 * expected_games
    fixtures = [_ft("Spain", "Uruguay", 3, 0)]
    scorers = [{"player": "Hat-trick hero", "team": "Spain", "goals": 3}]
    proj = project_scorers(scorers, fixtures, {"Spain": 5.0})
    naive = 3 / 1 * 5.0  # = 15
    assert proj[0]["Projected goals"] < naive

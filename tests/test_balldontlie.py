"""BALLDONTLIE client: odds maths, name normalisation, response mapping."""
import pytest

from world_cup_oracle.data import balldontlie as bdl


def test_american_to_decimal():
    assert bdl._american_to_decimal(150) == pytest.approx(2.5)
    assert bdl._american_to_decimal(-200) == pytest.approx(1.5)
    assert bdl._american_to_decimal(None) is None


def test_canonical_name_fixups():
    assert bdl.canonical("South Korea") == "Korea Republic"
    assert bdl.canonical("USA") == "United States"
    assert bdl.canonical("Brazil") == "Brazil"  # unchanged
    assert bdl.canonical(None) is None


def test_group_and_stage_parsing():
    assert bdl._group_letter({"name": "Group D"}) == "D"
    assert bdl._stage_name({"name": "Group Stage"}) == "group"
    assert bdl._stage_name({"name": "Round of 16"}) == "Round of 16"
    assert bdl._stage_name({"name": "Final"}) == "Final"


def test_odds_index_averages_vendors():
    rows = [
        {"match_id": 9, "moneyline_home_odds": 100, "moneyline_draw_odds": 250,
         "moneyline_away_odds": 300},
        {"match_id": 9, "moneyline_home_odds": 100, "moneyline_draw_odds": 250,
         "moneyline_away_odds": 300},
    ]
    idx = bdl._odds_index(rows)
    # both vendors price home at +100 -> decimal 2.0
    assert idx[9]["home"] == pytest.approx(2.0)
    assert idx[9]["away"] == pytest.approx(4.0)


def test_get_dataset_maps_to_schema(monkeypatch):
    canned = {
        "/teams": [{"id": 1, "name": "United States"}, {"id": 2, "name": "South Korea"}],
        "/matches": [
            {"id": 100, "status": "completed", "datetime": "2026-06-12T18:00:00Z",
             "stage": {"name": "Group Stage"}, "group": {"name": "Group D"},
             "home_team": {"name": "United States"}, "away_team": {"name": "South Korea"},
             "home_score": 2, "away_score": 1},
            {"id": 101, "status": "scheduled", "datetime": "2026-07-01T18:00:00Z",
             "stage": {"name": "Round of 16"}, "group": None,
             "home_team": None, "away_team": None},  # undecided -> skipped
        ],
        "/odds": [
            {"match_id": 100, "moneyline_home_odds": 100, "moneyline_draw_odds": 250,
             "moneyline_away_odds": 300},
        ],
        "/rosters": [
            {"player": {"first_name": "Christian", "last_name": "Pulisic"},
             "team_id": 1, "goals": 3},
            {"player": {"name": "Bench Warmer"}, "team_id": 2, "goals": 0},  # filtered
        ],
    }
    monkeypatch.setattr(bdl, "_get", lambda path, key, params: canned[path])

    data = bdl.get_dataset("fake-key", as_of="2026-06-13")
    assert data["source"] == "balldontlie"

    assert len(data["fixtures"]) == 1  # the TBD knockout match is dropped
    fx = data["fixtures"][0]
    assert (fx["home"], fx["away"]) == ("United States", "Korea Republic")  # normalised
    assert fx["group"] == "D" and fx["stage"] == "group" and fx["status"] == "FT"
    assert fx["home_goals"] == 2 and fx["kickoff"] == "2026-06-12T18:00:00Z"
    assert fx["odds"]["home"] == pytest.approx(2.0)

    assert len(data["scorers"]) == 1  # zero-goal roster row filtered out
    assert data["scorers"][0] == {"player": "Christian Pulisic",
                                  "team": "United States", "goals": 3}

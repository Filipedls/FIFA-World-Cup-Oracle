"""worldcup26.ir client: scorer-string parsing and response mapping."""
from world_cup_oracle.data import worldcup26 as wc


def test_parse_scorers_handles_curly_quotes_and_minutes():
    raw = "{“J. Quiñones 9'”,”R. Jiménez 67'”}"
    assert wc._parse_scorers(raw) == ["J. Quiñones", "R. Jiménez"]


def test_parse_scorers_empty_variants():
    for raw in ("null", "{}", "", None, "[]"):
        assert wc._parse_scorers(raw) == []


def test_parse_scorers_one_entry_per_goal():
    raw = "{“A. Striker 12'”,”A. Striker 45'+2'”}"
    # same player twice -> two goals (two entries)
    assert wc._parse_scorers(raw) == ["A. Striker", "A. Striker"]


def test_kickoff_and_date():
    ko, date = wc._kickoff_and_date("06/11/2026 13:00")
    assert ko == "2026-06-11T13:00:00"
    assert date == "2026-06-11"


def test_get_dataset_maps_games(monkeypatch):
    games = {"games": [
        {"id": "1", "type": "group", "group": "D", "finished": "TRUE",
         "local_date": "06/12/2026 18:00", "matchday": "1",
         "home_team_name_en": "USA", "away_team_name_en": "South Korea",
         "home_score": "2", "away_score": "1",
         "home_scorers": "{“F. Balogun 10'”,”C. Pulisic 80'”}",
         "away_scorers": "{“Son 90'”}"},
        {"id": "2", "type": "group", "group": "D", "finished": "FALSE",
         "local_date": "06/18/2026 18:00", "matchday": "2",
         "home_team_name_en": "USA", "away_team_name_en": "Paraguay",
         "home_score": "0", "away_score": "0",
         "home_scorers": "null", "away_scorers": "null"},
        {"id": "73", "type": "r32", "group": "R32", "finished": "FALSE",
         "local_date": "06/28/2026 12:00", "matchday": None,
         "home_team_name_en": None, "away_team_name_en": None,
         "home_score": "0", "away_score": "0",
         "home_scorers": "null", "away_scorers": "null"},
    ]}
    monkeypatch.setattr(wc, "_get", lambda path: games)

    data = wc.get_dataset(as_of="2026-06-14")
    assert data["source"] == "worldcup26"
    assert len(data["fixtures"]) == 2  # knockout TBD dropped

    played = data["fixtures"][0]
    assert (played["home"], played["away"]) == ("United States", "Korea Republic")
    assert played["status"] == "FT" and played["home_goals"] == 2
    assert played["group"] == "D" and played["stage"] == "group"

    unplayed = data["fixtures"][1]
    assert unplayed["status"] == "NS" and unplayed["home_goals"] is None

    goals = {(s["player"], s["team"]): s["goals"] for s in data["scorers"]}
    assert goals[("F. Balogun", "United States")] == 1
    assert goals[("Son", "Korea Republic")] == 1

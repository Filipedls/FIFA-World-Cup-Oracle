"""The Odds API client: price averaging and orientation-correct enrichment."""
import pytest

from world_cup_oracle.data import the_odds_api as toa


def _event(home, away, home_price, draw_price, away_price):
    return {
        "home_team": home, "away_team": away,
        "bookmakers": [{"key": "draftkings", "markets": [{"key": "h2h", "outcomes": [
            {"name": home, "price": home_price},
            {"name": "Draw", "price": draw_price},
            {"name": away, "price": away_price},
        ]}]}],
    }


def test_event_prices_orients_to_event_home_away():
    priced = toa._event_prices(_event("Brazil", "Morocco", 1.5, 4.0, 6.0))
    assert priced["home_team"] == "Brazil" and priced["away_team"] == "Morocco"
    assert priced["odds"]["home"] == pytest.approx(1.5)
    assert priced["odds"]["away"] == pytest.approx(6.0)


def test_enrich_matches_and_reorients(monkeypatch):
    # bookmaker lists the game the other way round vs our fixture
    events = [_event("Korea Republic", "United States", 6.0, 4.0, 1.5),
              _event("Brazil", "Morocco", 1.4, 4.5, 7.0)]
    monkeypatch.setattr(toa, "_fetch_events", lambda key: events)

    dataset = {"fixtures": [
        {"home": "United States", "away": "Korea Republic", "odds": None},
        {"home": "Brazil", "away": "Morocco", "odds": None},
        {"home": "France", "away": "Norway", "odds": None},  # no event -> untouched
    ]}
    n = toa.enrich(dataset, key="fake")
    assert n == 2

    usa = dataset["fixtures"][0]
    # USA was the away team for the bookmaker (price 1.5) -> must land on home here
    assert usa["odds"]["home"] == pytest.approx(1.5)
    assert usa["odds"]["away"] == pytest.approx(6.0)

    bra = dataset["fixtures"][1]
    assert bra["odds"]["home"] == pytest.approx(1.4)

    assert dataset["fixtures"][2]["odds"] is None


def test_enrich_skips_fixtures_that_already_have_odds(monkeypatch):
    events = [_event("Brazil", "Morocco", 1.4, 4.5, 7.0)]
    monkeypatch.setattr(toa, "_fetch_events", lambda key: events)
    existing = {"home": 2.0, "draw": 3.0, "away": 3.5}
    dataset = {"fixtures": [{"home": "Brazil", "away": "Morocco", "odds": existing}]}
    assert toa.enrich(dataset, key="fake") == 0
    assert dataset["fixtures"][0]["odds"] is existing

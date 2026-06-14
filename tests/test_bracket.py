"""Bracket builders: standings projection, real knockouts, most-likely (MC)."""
from world_cup_oracle.data.sample import build_dataset
from world_cup_oracle.models import simulation
from world_cup_oracle.models.standings import project_qualifiers
from world_cup_oracle.viz import bracket as bv


def test_build_rounds_shape_and_favourite_champion():
    slots = project_qualifiers(build_dataset()["fixtures"])
    rounds, champion = bv.build_rounds(slots)
    assert [len(r) for r in rounds] == [16, 8, 4, 2, 1]
    assert champion != bv._TBD


def test_rounds_from_knockouts_uses_real_results():
    # a tiny 2-match "R32" that resolves to a single R16 tie
    fixtures = [
        {"id": 1, "stage": "Round of 32", "home": "Brazil", "away": "Haiti",
         "status": "FT", "home_goals": 3, "away_goals": 0},
        {"id": 2, "stage": "Round of 32", "home": "Spain", "away": "Panama",
         "status": "FT", "home_goals": 1, "away_goals": 2},  # upset!
    ]
    rounds, champion = bv.rounds_from_knockouts(fixtures)
    assert rounds[0] == [("Brazil", "Haiti"), ("Spain", "Panama")]
    # real results advance the winners (Panama upset Spain), not the favourites
    assert rounds[1] == [("Brazil", "Panama")]


def test_rounds_from_knockouts_none_when_no_fixtures():
    # sample dataset has only group fixtures -> no real R32 yet
    assert bv.rounds_from_knockouts(build_dataset()["fixtures"]) is None


def test_most_likely_qualifiers_are_complete_and_distinct():
    sim = simulation.run(build_dataset()["fixtures"], n_sims=2000)
    slots = sim.most_likely_qualifiers()
    # 12 winners + 12 runners + 8 thirds = 32 distinct teams
    assert len(slots) == 32
    assert len(set(slots.values())) == 32

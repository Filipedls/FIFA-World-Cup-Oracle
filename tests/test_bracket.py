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


def test_official_r32_layout_slot_counts():
    slots = [s for match in bv.bk.R32_MATCHES for s in match]
    winners = {s[1] for s in slots if s[0] == "W"}
    runners = {s[1] for s in slots if s[0] == "R"}
    thirds = sorted(s[1] for s in slots if s[0] == "T")
    assert winners == set("ABCDEFGHIJKL")      # all 12 group winners
    assert runners == set("ABCDEFGHIJKL")      # all 12 runners-up
    assert thirds == list(range(8))            # 8 third-place slots


def test_assign_thirds_respects_official_eligibility():
    from world_cup_oracle.models import bracket as bk
    from world_cup_oracle.teams import GROUPS
    winners = {g: GROUPS[g][0] for g in GROUPS}
    groups8 = list("ABCDEFGH")
    thirds = [(GROUPS[g][2], g, 1.0) for g in groups8]   # (team, group, strength)
    assign = bk.assign_thirds(thirds, winners)
    assert len(assign) == 8
    team_group = {t: g for (t, g, _) in thirds}
    for slot, team in assign.items():
        assert team_group[team] in bk.THIRD_SLOTS[slot]["eligible"]


def test_assign_thirds_avoids_confederation_clash_when_possible():
    from world_cup_oracle.models import bracket as bk
    # slot 7 (winner K) and slot 4 (winner D); make their winners CONMEBOL,
    # and offer a CONMEBOL third (group D, eligible only for slots 0,1,7) — it
    # should land in slot 1 (winner I) if that winner is non-CONMEBOL.
    winners = {"K": "Brazil", "I": "Spain", "D": "Argentina",
               "E": "Germany", "A": "France", "L": "England",
               "G": "Belgium", "B": "Netherlands"}
    # one CONMEBOL third from group D (eligible slots: 1, 4, 7), others neutral
    thirds = [("Uruguay", "D", 5.0), ("Ghana", "E", 4.0), ("Egypt", "F", 3.0),
              ("Iran", "H", 2.0), ("Qatar", "C", 1.0), ("Japan", "G", 0.9),
              ("Tunisia", "I", 0.8), ("Jordan", "J", 0.7)]
    assign = bk.assign_thirds(thirds, winners)
    slot_of = {team: k for k, team in assign.items()}
    # group D is eligible only for slots {0,1,7}; slot 7's winner (Brazil) is
    # CONMEBOL like Uruguay, so a clash-free assignment uses slot 0 or 1.
    assert slot_of["Uruguay"] in (0, 1)


def test_most_likely_qualifiers_are_complete_and_distinct():
    sim = simulation.run(build_dataset()["fixtures"], n_sims=2000)
    slots = sim.most_likely_qualifiers()
    # 12 winners + 12 runners + 8 thirds = 32 distinct teams
    assert len(slots) == 32
    assert len(set(slots.values())) == 32

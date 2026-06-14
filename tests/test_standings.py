"""Group standings computation."""
from world_cup_oracle.models.standings import (compute_group, expected_standings,
                                               project_qualifiers_expected)
from world_cup_oracle.teams import GROUPS


def _fx(home, away, hg, ag, group="A"):
    return {"id": 1, "stage": "group", "group": group, "matchday": 1,
            "date": "2026-06-11", "home": home, "away": away,
            "status": "FT", "home_goals": hg, "away_goals": ag, "odds": None}


def test_points_win_draw_loss_and_ordering():
    a, b, c, d = GROUPS["A"]
    fixtures = [
        _fx(a, b, 2, 0),   # a beats b
        _fx(c, d, 1, 1),   # c draws d
        _fx(a, c, 3, 1),   # a beats c
    ]
    rows = compute_group(fixtures, "A")
    by_team = {r.team: r for r in rows}

    assert by_team[a].points == 6 and by_team[a].won == 2
    assert by_team[b].points == 0 and by_team[b].lost == 1
    assert by_team[c].points == 1 and by_team[c].drawn == 1
    assert by_team[a].gf == 5 and by_team[a].ga == 1 and by_team[a].gd == 4
    # leader is the team with most points
    assert rows[0].team == a


def test_goal_difference_breaks_points_tie():
    a, b, c, d = GROUPS["B"]
    fixtures = [
        _fx(a, c, 5, 0, group="B"),  # a: +5
        _fx(b, d, 1, 0, group="B"),  # b: +1, same points as a (both 3)
    ]
    rows = compute_group(fixtures, "B")
    assert rows[0].team == a  # better goal difference ranks first


def test_expected_standings_blends_real_results_and_odds():
    a, b, c, d = GROUPS["A"]
    fixtures = [
        # a thrashed b for real
        {"stage": "group", "group": "A", "home": a, "away": b, "status": "FT",
         "home_goals": 3, "away_goals": 0, "odds": None},
        # a is a strong market favourite vs c (not played yet)
        {"stage": "group", "group": "A", "home": a, "away": c, "status": "NS",
         "home_goals": None, "away_goals": None,
         "odds": {"home": 1.2, "draw": 6.0, "away": 12.0}},
    ]
    tables = expected_standings(fixtures)
    pts = {t: p for (t, p, gd, gf) in tables["A"]}
    assert tables["A"][0][0] == a            # a leads the group
    assert pts[a] > pts[b] and pts[a] > pts[c]
    assert pts[a] > 3                          # 3 real + expected points from odds


def test_project_qualifiers_expected_full_and_distinct():
    from world_cup_oracle.data.sample import build_dataset
    slots = project_qualifiers_expected(build_dataset()["fixtures"])
    assert sum(1 for k in slots if k[0] == "W") == 12
    assert len(set(slots.values())) == 32


def test_form_string_is_chronological_recent_last():
    a, b, c, d = GROUPS["C"]
    fixtures = [
        _fx(a, b, 1, 0, group="C"),  # W
        _fx(c, a, 2, 0, group="C"),  # a loses -> L
    ]
    rows = compute_group(fixtures, "C")
    brazil = next(r for r in rows if r.team == a)
    assert brazil.form == ["W", "L"]  # chronological, most recent last

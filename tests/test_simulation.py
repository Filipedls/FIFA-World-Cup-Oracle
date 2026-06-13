"""Monte Carlo tournament simulation invariants."""
import pytest

from world_cup_oracle.config import STAGE_LABELS
from world_cup_oracle.data.sample import build_dataset
from world_cup_oracle.models import simulation


@pytest.fixture(scope="module")
def sim():
    data = build_dataset()
    return simulation.run(data["fixtures"], n_sims=3000)


def test_winner_probabilities_sum_to_one(sim):
    total = sum(p["Winner"] for p in sim.stage_probs.values())
    assert total == pytest.approx(1.0, abs=1e-6)


def test_exactly_32_teams_advance_on_average(sim):
    advance_label = STAGE_LABELS[0]
    total = sum(p[advance_label] for p in sim.stage_probs.values())
    assert total == pytest.approx(32.0, abs=1e-6)


def test_stage_probabilities_are_monotonically_non_increasing(sim):
    # P(advance) >= P(R16) >= ... >= P(Winner) for every team
    for team, probs in sim.stage_probs.items():
        seq = [probs[label] for label in STAGE_LABELS]
        assert all(seq[i] >= seq[i + 1] - 1e-9 for i in range(len(seq) - 1)), team


def test_expected_games_within_format_bounds(sim):
    # group stage is 3 games; champion plays 3 + 5 knockout = 8 at most
    for team, games in sim.expected_games.items():
        assert 3.0 <= games <= 8.0, (team, games)


def test_stronger_team_more_likely_to_win_group(sim):
    # Spain (power 0.87) should out-favour its group-mate Saudi Arabia
    assert sim.stage_probs["Spain"]["Winner"] > sim.stage_probs["Saudi Arabia"]["Winner"]

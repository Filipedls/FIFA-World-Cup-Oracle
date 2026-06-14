"""End-to-end smoke test: the Streamlit script runs without raising."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from world_cup_oracle.data.sample import build_dataset
from world_cup_oracle.models.standings import project_qualifiers
from world_cup_oracle.viz import bracket as bracket_viz

APP = str(Path(__file__).resolve().parents[1] / "src" / "world_cup_oracle" / "app.py")


def test_bracket_has_hover_probabilities():
    slots = project_qualifiers(build_dataset()["fixtures"])
    rounds, champion = bracket_viz.build_rounds(slots)
    fig = bracket_viz.figure(rounds, champion)
    hover = next(t for t in fig.data if getattr(t, "hovertext", None))
    assert len(hover.hovertext) == 31           # 16+8+4+2+1 matches
    assert any("to advance" in h for h in hover.hovertext)


def test_app_runs_without_exceptions():
    at = AppTest.from_file(APP, default_timeout=180)
    # keep the smoke test fast: fewer simulations
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def test_app_renders_core_widgets():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert at.title[0].value.startswith("🏆")
    assert len(at.tabs) == 6            # Stats / Groups / Bracket / Matches / Scorers / Advancement
    assert len(at.dataframe) >= 12      # 12 group tables at minimum

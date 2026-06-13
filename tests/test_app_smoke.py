"""End-to-end smoke test: the Streamlit script runs without raising."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "src" / "world_cup_oracle" / "app.py")


def test_app_runs_without_exceptions():
    at = AppTest.from_file(APP, default_timeout=180)
    # keep the smoke test fast: fewer simulations
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]


def test_app_renders_core_widgets():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert at.title[0].value.startswith("🏆")
    assert len(at.tabs) == 5            # Groups / Bracket / Matches / Scorers / Advancement
    assert len(at.dataframe) >= 12      # 12 group tables at minimum

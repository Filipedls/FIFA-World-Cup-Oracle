"""FIFA World Cup 2026 Oracle — Streamlit app.

Run with:  streamlit run src/world_cup_oracle/app.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Make the package importable when launched via `streamlit run <path>`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from world_cup_oracle.config import DEFAULT_SIMULATIONS, STAGE_LABELS
from world_cup_oracle.data import cache
from world_cup_oracle.data.loader import load_dataset
from world_cup_oracle.models import simulation
from world_cup_oracle.models.odds import implied_from_decimal, probs_from_power
from world_cup_oracle.models.scorers import project_scorers
from world_cup_oracle.models.standings import (compute_all_groups,
                                               project_qualifiers)
from world_cup_oracle.teams import power_of
from world_cup_oracle.viz import bracket as bracket_viz
from world_cup_oracle.viz.standings import standings_dataframe, style_standings

st.set_page_config(page_title="World Cup 2026 Oracle", page_icon="🏆", layout="wide")


@st.cache_data(ttl=300, show_spinner="Loading World Cup data…")
def get_data() -> dict:
    return load_dataset()


@st.cache_data(show_spinner="Running tournament simulation…")
def get_simulation(fixtures: list[dict], n_sims: int) -> simulation.SimulationResult:
    return simulation.run(fixtures, n_sims=n_sims)


def match_probs(fx: dict):
    if fx.get("odds"):
        return implied_from_decimal(fx["odds"]), "market"
    return probs_from_power(power_of(fx["home"]), power_of(fx["away"])), "model"


def _fmt_kickoff(fx: dict) -> str:
    ko = fx.get("kickoff")
    if not ko:
        return fx.get("date", "")
    try:
        dt = datetime.fromisoformat(ko)
        return dt.strftime("%a %d %b · %H:%M")
    except ValueError:
        return fx.get("date", "")


def _fmt_fetched(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return ts


# ---------------------------------------------------------------------------
data = get_data()
fixtures = data["fixtures"]

header_l, header_r = st.columns([4, 1])
with header_l:
    st.title("🏆 FIFA World Cup 2026 Oracle")
with header_r:
    if st.button("🔄 Refresh data", use_container_width=True,
                 help="Force a re-fetch from the API and clear caches."):
        cache.invalidate()
        st.cache_data.clear()
        st.rerun()

st.caption(
    f"Data source: **{data['source']}** · as of **{data.get('as_of', '—')}** · "
    f"updated **{_fmt_fetched(data.get('_fetched_at'))}** · Canada · Mexico · USA"
)
if data.get("warning"):
    st.warning(data["warning"])
if data["source"] == "sample":
    st.info(
        "Running on the built-in **sample dataset** (no API key found). Set "
        "`WORLD_CUP_API_KEY` in a `.env` file to pull live fixtures, odds and "
        "scorers from API-Football.",
        icon="ℹ️",
    )

with st.sidebar:
    st.header("Simulation")
    n_sims = st.select_slider(
        "Number of simulations",
        options=[2_000, 5_000, 10_000, 25_000, 50_000],
        value=DEFAULT_SIMULATIONS,
        help="More simulations = smoother probabilities, slower to compute.",
    )
    st.caption(
        "Advancement probabilities come from a Monte Carlo simulation: group "
        "matches use the bookmaker-implied odds, knockout ties use power ratings."
    )

sim = get_simulation(fixtures, n_sims)

tab_groups, tab_bracket, tab_matches, tab_scorers, tab_probs = st.tabs(
    ["📊 Groups", "🗺️ Bracket", "🎲 Matches & Odds", "⚽ Scorers", "🔮 Advancement"]
)

# --- Groups -----------------------------------------------------------------
with tab_groups:
    st.subheader("Group standings")
    st.caption("🟩 top 2 advance · 🟫 3rd place (best 8 across groups advance)")
    tables = compute_all_groups(fixtures)
    cols = st.columns(3)
    for i, (group, rows) in enumerate(tables.items()):
        with cols[i % 3]:
            st.markdown(f"**Group {group}**")
            df = standings_dataframe(rows)
            st.dataframe(style_standings(df), use_container_width=True)

# --- Bracket ----------------------------------------------------------------
with tab_bracket:
    st.subheader("Knockout bracket")
    st.caption(
        "Projected from current standings; the **favourite advances** each round "
        "(bold = favourite). Per-stage probabilities are on the Advancement tab."
    )
    slot_teams = project_qualifiers(fixtures)
    st.plotly_chart(bracket_viz.figure(slot_teams), use_container_width=True)

# --- Matches & odds ---------------------------------------------------------
with tab_matches:
    st.subheader("All matches & win probabilities")
    stages = ["All"] + sorted({f["stage"] for f in fixtures})
    c1, c2 = st.columns([1, 1])
    stage_sel = c1.selectbox("Stage", stages)
    groups_avail = sorted({f["group"] for f in fixtures if f.get("group")})
    group_sel = c2.selectbox("Group", ["All"] + groups_avail)

    rows = []
    for f in sorted(fixtures, key=lambda x: (x["date"], x["id"])):
        if stage_sel != "All" and f["stage"] != stage_sel:
            continue
        if group_sel != "All" and f.get("group") != group_sel:
            continue
        probs, src = match_probs(f)
        score = (f"{f['home_goals']}–{f['away_goals']}"
                 if f["status"] == "FT" else "")
        rows.append({
            "Kickoff": _fmt_kickoff(f),
            "Stage": f["stage"],
            "Group": f.get("group") or "",
            "Team A (home)": f["home"],
            "Team B (away)": f["away"],
            "Score": score,
            "P(A win)": round(probs.home * 100, 1),
            "P(draw)": round(probs.draw * 100, 1),
            "P(B win)": round(probs.away * 100, 1),
            "Prob source": src,
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config={
            "P(A win)": st.column_config.ProgressColumn(
                "P(A win)", format="%.0f%%", min_value=0, max_value=100),
            "P(draw)": st.column_config.NumberColumn("P(draw)", format="%.0f%%"),
            "P(B win)": st.column_config.ProgressColumn(
                "P(B win)", format="%.0f%%", min_value=0, max_value=100),
        },
    )
    st.caption("`market` = vig-removed bookmaker odds · `model` = Poisson power model (no odds yet)")

# --- Scorers ----------------------------------------------------------------
with tab_scorers:
    st.subheader("Goalscorers & projected final tally")
    if not data["scorers"]:
        st.info("No goals recorded yet.")
    else:
        proj = project_scorers(data["scorers"], fixtures, sim.expected_games)
        df = pd.DataFrame(proj)
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={
                "Projected goals": st.column_config.NumberColumn(
                    "Projected goals", format="%.1f ⚽"),
            },
        )
        st.caption(
            "**Projected goals** = regularised goals/game × the team's expected "
            "total matches from the simulation. The rate is shrunk toward a "
            "baseline so tiny early-tournament samples don't explode."
        )

# --- Advancement probabilities ----------------------------------------------
with tab_probs:
    st.subheader("Probability of reaching each stage")
    team_group = {r.team: g for g, rs in compute_all_groups(fixtures).items() for r in rs}
    rows = []
    for team, probs in sim.stage_probs.items():
        row = {"Team": team, "Group": team_group.get(team, "")}
        row.update({label: round(probs[label] * 100, 1) for label in STAGE_LABELS})
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("Winner", ascending=False)
    pct_cols = {label: st.column_config.NumberColumn(label, format="%.1f%%")
                for label in STAGE_LABELS}
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=pct_cols)

    st.markdown("#### Title favourites")
    champ = pd.DataFrame([(t, round(p * 100, 1)) for t, p in sim.champion_odds()],
                         columns=["Team", "P(Winner) %"]).head(15)
    champ = champ.set_index("Team")
    st.bar_chart(champ, horizontal=True)
    st.caption(f"Based on {sim.n_sims:,} simulated tournaments.")

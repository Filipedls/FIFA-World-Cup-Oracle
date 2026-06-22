"""FIFA World Cup 2026 Oracle — Streamlit app.

Run with:  streamlit run src/world_cup_oracle/app.py
"""
from __future__ import annotations

import os
import sys
import zoneinfo
from datetime import datetime
from pathlib import Path

# Make the package importable when launched via `streamlit run <path>`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from world_cup_oracle import timeutil
from world_cup_oracle.config import (API_KEY_ENV, CACHE_ENABLED, DATA_SOURCE,
                                     DEFAULT_SIMULATIONS, DEFAULT_TIMEZONE,
                                     ODDS_API_KEY_ENV, STAGE_LABELS)
from world_cup_oracle.data import cache
from world_cup_oracle.data.loader import load_dataset
from world_cup_oracle.models import simulation
from world_cup_oracle.models.odds import implied_from_decimal, probs_from_power
from world_cup_oracle.models.ratings import compute_ratings, power_func
from world_cup_oracle.models.scorers import project_scorers
from world_cup_oracle.models.standings import (compute_all_groups,
                                               expected_standings,
                                               project_qualifiers,
                                               project_qualifiers_expected)
from world_cup_oracle.models.stats import compute_stats
from world_cup_oracle.viz import bracket as bracket_viz
from world_cup_oracle.viz.standings import (expected_standings_dataframe,
                                            standings_dataframe, style_standings)

st.set_page_config(page_title="World Cup 2026 Oracle", page_icon="🏆", layout="wide")


def _default_cfg() -> dict:
    """Initial API config — defaults come from the environment / .env."""
    return {
        "source": (DATA_SOURCE or "worldcup26"),
        "api_key": os.getenv(API_KEY_ENV, "") or "",
        "odds_key": os.getenv(ODDS_API_KEY_ENV, "") or "",
    }


def _load_with_cfg(cfg: dict) -> dict:
    return load_dataset(source=cfg["source"],
                        api_key=cfg["api_key"] or None,
                        odds_key=cfg["odds_key"] or None)


def _reload_data() -> None:
    """Drop the in-session dataset + disk cache so the next run re-fetches."""
    cache.invalidate()
    st.session_state.pop("dataset", None)
    st.rerun()


@st.cache_data(show_spinner=False)
def get_simulation(fixtures: list[dict], n_sims: int) -> simulation.SimulationResult:
    return simulation.run(fixtures, n_sims=n_sims)


def match_probs(fx: dict, power):
    if fx.get("odds"):
        return implied_from_decimal(fx["odds"]), "market"
    return probs_from_power(power(fx["home"]), power(fx["away"])), "model"


def _fmt_fetched(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return ts


# --- config + data, both held in session state ------------------------------
if "cfg" not in st.session_state:
    st.session_state.cfg = _default_cfg()           # defaults from .env / env
st.session_state.setdefault("tz", DEFAULT_TIMEZONE)  # display timezone (kickoffs)
if "dataset" not in st.session_state:               # the in-session data "cache"
    with st.spinner("Loading World Cup data…"):
        st.session_state.dataset = _load_with_cfg(st.session_state.cfg)

data = st.session_state.dataset
fixtures = data["fixtures"]
# data-driven team strength (bookmaker odds + results + prior), used by the
# bracket favourite/hover and the model-based match probabilities.
ratings = compute_ratings(fixtures)
power = power_func(ratings)

header_l, header_r = st.columns([4, 1])
with header_l:
    st.title("🏆 FIFA World Cup 2026 Oracle")
with header_r:
    if st.button("🔄 Refresh data", width='stretch',
                 help="Force a re-fetch from the API and clear caches."):
        _reload_data()

st.caption(
    f"Data source: **{data['source']}** · as of **{data.get('as_of', '—')}** · "
    f"updated **{_fmt_fetched(data.get('_fetched_at'))}** · Canada · Mexico · USA"
)
if data.get("warning"):
    st.warning(data["warning"])
if data.get("odds_note"):
    st.caption(f"💰 {data['odds_note']}")
if data["source"] == "sample":
    st.info(
        "Running on the built-in **sample dataset**. Open the **⚙️ Config** tab "
        "to choose a data source and add API keys (or set them in a `.env` file).",
        icon="ℹ️",
    )

with st.sidebar:
    st.header("Simulation")
    n_sims = st.select_slider(
        "Number of simulations",
        options=[2_000, 5_000, 10_000, 25_000, 50_000, 100_000, 500_000],
        value=DEFAULT_SIMULATIONS,
        help="More simulations = smoother probabilities, slower to compute.",
    )
    st.caption(
        "Drives the 🔮 **Advancement** probabilities and ⚽ **scorer projections** "
        "— not the per-match odds. Group matches use the bookmaker-implied odds, "
        "knockout ties use power ratings. More runs = smoother (changes are small "
        "once converged)."
    )

with st.spinner(f"🎲 Running {n_sims:,} tournament simulations…"):
    sim = get_simulation(fixtures, n_sims)

(tab_stats, tab_groups, tab_bracket, tab_matches, tab_scorers, tab_probs,
 tab_config) = st.tabs(
    ["📈 Stats", "📊 Groups", "🗺️ Bracket", "🎲 Matches & Odds", "⚽ Scorers",
     "🔮 Advancement", "⚙️ Config"]
)

# --- Tournament stats -------------------------------------------------------
with tab_stats:
    st.subheader("Tournament at a glance")
    stats = compute_stats(fixtures, data["scorers"])
    top = stats["top_scorer"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matches played", f"{stats['matches_played']}",
              help=f"of {stats['matches_scheduled']} scheduled")
    c2.metric("Goals scored", f"{stats['total_goals']}")
    c3.metric("Avg goals / match", f"{stats['avg_goals']:.2f}")
    c4.metric("Top scorer",
              f"{top['player']}" if top else "—",
              help=f"{top['team']}" if top else None,
              delta=f"{top['goals']} goals" if top else None,
              delta_color="off")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Players who scored", f"{stats['distinct_scorers']}")
    c6.metric("Teams who scored", f"{stats['teams_scored']}")
    c7.metric("Clean sheets", f"{stats['clean_sheets']}")
    c8.metric("Goalless draws", f"{stats['goalless_draws']}")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("**Goals: home vs away**")
        if stats["total_goals"]:
            ha = pd.DataFrame(
                {"Goals": [stats["home_goals"], stats["away_goals"]]},
                index=["Home", "Away"])
            st.bar_chart(ha, horizontal=True)
        else:
            st.caption("No goals yet.")
    with right:
        hs, bw = stats["highest_scoring"], stats["biggest_win"]
        if hs:
            st.markdown("**Highest-scoring match**")
            st.write(f"{hs['home']} {hs['home_goals']}–{hs['away_goals']} "
                     f"{hs['away']}  ·  {hs['total']} goals  ·  {hs['date']}")
        if bw:
            st.markdown("**Biggest win**")
            st.write(f"{bw['home']} {bw['home_goals']}–{bw['away_goals']} "
                     f"{bw['away']}  ·  +{bw['margin']}  ·  {bw['date']}")

    st.caption(
        "Disciplinary stats (yellow/red cards) aren't provided by the free "
        "worldcup26 source — they'd need a paid provider (balldontlie / api_football)."
    )

# --- Groups -----------------------------------------------------------------
with tab_groups:
    st.subheader("Group standings")
    predicted = st.toggle(
        "Predicted final standings (from odds)",
        help="Finished games count their real result; unplayed games add "
             "expected points from the match odds (Pts/GD/GF are expected values).",
    )
    st.caption("🟩 top 2 advance · 🟫 3rd place (best 8 across groups advance)")

    cols = st.columns(2)
    if predicted:
        tables = expected_standings(fixtures, power)
        fmt = {"Pts": "{:.1f}", "GD": "{:+.1f}", "GF": "{:.1f}"}
        for i, (group, rows) in enumerate(tables.items()):
            with cols[i % 2]:
                st.markdown(f"**Group {group}**")
                df = expected_standings_dataframe(rows)
                st.dataframe(style_standings(df).format(fmt), width='stretch')
    else:
        tables = compute_all_groups(fixtures)
        for i, (group, rows) in enumerate(tables.items()):
            with cols[i % 2]:
                st.markdown(f"**Group {group}**")
                df = standings_dataframe(rows)
                st.dataframe(style_standings(df), width='stretch')

# --- Bracket ----------------------------------------------------------------
with tab_bracket:
    st.subheader("Knockout bracket")
    st.caption(
        "Round-of-32 pairings follow FIFA's **official 2026 bracket**; the eight "
        "third-placed teams are slotted by their official eligibility sets, "
        "minimising same-confederation clashes."
    )
    SRC_STANDINGS = "Current standings"
    SRC_ODDS = "Odds-projected final standings"
    SRC_MONTECARLO = "Monte Carlo (most-likely)"
    SRC_REAL = "Real knockout fixtures"
    source = st.radio(
        "Round of 32 source", [SRC_ODDS, SRC_STANDINGS, SRC_MONTECARLO, SRC_REAL],
        horizontal=True,
        help="Who fills the Round of 32. Later rounds advance the favourite "
             "(or the real result, for actual fixtures).",
    )

    if source == SRC_ODDS:
        rounds, champion = bracket_viz.build_rounds(
            project_qualifiers_expected(fixtures, power), power)
        note = ("Projected final tables: finished games use the real score, "
                "unplayed games use expected points from the odds.")
    elif source == SRC_MONTECARLO:
        rounds, champion = bracket_viz.build_rounds(sim.most_likely_qualifiers(), power)
        note = (f"Each slot is the team most often qualifying there across "
                f"{sim.n_sims:,} simulations.")
    elif source == SRC_REAL:
        built = bracket_viz.rounds_from_knockouts(fixtures, power)
        if built is None:
            st.info(
                "The data source hasn't published Round-of-32 fixtures yet "
                "(knockout teams are still TBD). Falling back to current standings.",
                icon="🗓️",
            )
            rounds, champion = bracket_viz.build_rounds(project_qualifiers(fixtures), power)
            note = "Projected from current standings (real fixtures not available yet)."
        else:
            rounds, champion = built
            note = "Real draw + results from the data source; favourite fills unplayed ties."
    else:
        rounds, champion = bracket_viz.build_rounds(project_qualifiers(fixtures), power)
        note = "If the groups finished as they stand now: top 2 + the 8 best third-placed."

    st.caption(
        f"{note} Later rounds: **favourite advances** (bold). "
        "**Hover any match** for each team's chance of winning that tie."
    )
    st.plotly_chart(bracket_viz.figure(rounds, champion, power), width='stretch')

# --- Matches & odds ---------------------------------------------------------
with tab_matches:
    st.subheader("All matches & win probabilities")
    stages = ["All"] + sorted({f["stage"] for f in fixtures})
    c1, c2 = st.columns([1, 1])
    stage_sel = c1.selectbox("Stage", stages)
    groups_avail = sorted({f["group"] for f in fixtures if f.get("group")})
    group_sel = c2.selectbox("Group", ["All"] + groups_avail)

    tz = st.session_state["tz"]
    rows = []
    for f in sorted(fixtures, key=lambda x: (x.get("kickoff") or x["date"], x["id"])):
        if stage_sel != "All" and f["stage"] != stage_sel:
            continue
        if group_sel != "All" and f.get("group") != group_sel:
            continue
        probs, src = match_probs(f, power)
        score = (f"{f['home_goals']}–{f['away_goals']}"
                 if f["status"] == "FT" else "")
        ko = timeutil.to_timezone(f.get("kickoff"), tz)
        rows.append({
            # real datetime (naive wall-clock in the display tz) so the column
            # sorts chronologically instead of alphabetically by weekday
            "Kickoff": ko.replace(tzinfo=None) if ko else None,
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
        df, width='stretch', hide_index=True,
        column_config={
            "Kickoff": st.column_config.DatetimeColumn(
                "Kickoff", format="ddd DD MMM · HH:mm"),
            "P(A win)": st.column_config.ProgressColumn(
                "P(A win)", format="%.0f%%", min_value=0, max_value=100),
            "P(draw)": st.column_config.NumberColumn("P(draw)", format="%.0f%%"),
            "P(B win)": st.column_config.ProgressColumn(
                "P(B win)", format="%.0f%%", min_value=0, max_value=100),
        },
    )
    st.caption(
        f"Kickoff times in **{tz}** · `market` = vig-removed bookmaker odds · "
        "`model` = Poisson power model (no odds yet)"
    )

# --- Scorers ----------------------------------------------------------------
with tab_scorers:
    st.subheader("Goalscorers & projected final tally")
    if not data["scorers"]:
        st.info("No goals recorded yet.")
    else:
        proj = project_scorers(data["scorers"], fixtures, sim.expected_games)
        df = pd.DataFrame(proj)
        st.dataframe(
            df, width='stretch', hide_index=True,
            column_config={
                "Projected goals": st.column_config.NumberColumn(
                    "Projected goals", format="%.1f ⚽"),
            },
        )
        st.caption(
            "**Goals/game** is the raw rate (goals ÷ team matches played). "
            "**Projected goals** multiplies the team's expected total matches by "
            "a *shrunk* rate (regularised toward a baseline) so tiny early samples "
            "— e.g. 2 goals in 1 game — don't explode the forecast."
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
    st.dataframe(df, width='stretch', hide_index=True, column_config=pct_cols)

    st.markdown("#### Title favourites")
    champ = pd.DataFrame([(t, round(p * 100, 1)) for t, p in sim.champion_odds()],
                         columns=["Team", "P(Winner) %"]).head(15)
    champ = champ.set_index("Team")
    st.bar_chart(champ, horizontal=True)
    st.caption(f"Based on {sim.n_sims:,} simulated tournaments.")

# --- Config -----------------------------------------------------------------
with tab_config:
    st.subheader("Data source & API keys")
    st.caption(
        "Stored in this browser **session** only (never written to disk). "
        "Defaults are loaded from a `.env` file if present. Saving re-fetches the data."
    )
    cfg = st.session_state.cfg
    _SOURCES = ["worldcup26", "balldontlie", "api_football"]
    src_help = ("worldcup26 — free, no key · balldontlie — needs a paid key · "
                "api_football — needs a key (free tier excludes 2026)")

    with st.form("config_form"):
        cur = cfg["source"].replace("-", "_")
        source_sel = st.selectbox(
            "Base data source (fixtures / standings / scorers)", _SOURCES,
            index=_SOURCES.index(cur) if cur in _SOURCES else 0, help=src_help)
        api_key_in = st.text_input(
            "Base source API key (WORLD_CUP_API_KEY)", value=cfg["api_key"],
            type="password", help="Only needed for balldontlie / api_football.")
        odds_key_in = st.text_input(
            "The Odds API key (THE_ODDS_API_KEY)", value=cfg["odds_key"],
            type="password", help="Optional. Adds real betting odds on top of the base source.")
        saved = st.form_submit_button("💾 Save & reload", type="primary")

    if saved:
        st.session_state.cfg = {
            "source": source_sel,
            "api_key": api_key_in.strip(),
            "odds_key": odds_key_in.strip(),
        }
        _reload_data()

    if st.button("↩️ Reset to .env defaults"):
        st.session_state.cfg = _default_cfg()
        _reload_data()

    st.divider()
    st.markdown("**Display**")
    _zones = sorted(zoneinfo.available_timezones())
    if st.session_state["tz"] not in _zones:
        _zones.insert(0, st.session_state["tz"])
    st.selectbox(
        "Timezone (kickoff times)", _zones, key="tz",
        index=_zones.index(st.session_state["tz"]),
        help="All match kickoff times are shown in this timezone. Applies instantly.",
    )

    st.divider()
    st.markdown("**Current session status**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Active source", data["source"])
    c2.metric("Base key", "set ✓" if cfg["api_key"] else "—")
    c3.metric("Odds key", "set ✓" if cfg["odds_key"] else "—")
    st.caption(
        f"Last fetched: **{_fmt_fetched(data.get('_fetched_at'))}** · "
        f"{data.get('odds_note', 'no odds overlay')}"
    )
    cache_state = "enabled" if CACHE_ENABLED else "disabled"
    st.caption(
        f"💾 Disk cache: **{cache_state}** (set `WORLD_CUP_CACHE_ENABLED=true` in "
        "`.env` to enable across sessions; data is always held for this session)."
    )
    if data.get("warning"):
        st.warning(data["warning"])

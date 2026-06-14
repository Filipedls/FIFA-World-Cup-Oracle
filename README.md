# 🏆 FIFA World Cup 2026 Oracle

A Streamlit app for following the 2026 World Cup (Canada · Mexico · USA) and
forecasting it with a Monte Carlo simulation.

## Features

- **📊 Groups** — live group standings (P W D L GF GA GD Pts Form), FIFA-style,
  with qualification zones colour-coded (top 2 + best-8 third-placed).
- **🗺️ Bracket** — knockout bracket drawn as a flowchart with connector lines,
  projected from the current standings.
- **🎲 Matches & Odds** — every fixture with kickoff time and win/draw/win
  probabilities. These come from **vig-removed bookmaker odds** (API-Football)
  where available, and fall back to a Poisson power model for fixtures with no
  market yet.
- **⚽ Scorers** — every goalscorer with their tally, plus a **projected final
  total** (regularised goals/game × their team's expected number of matches).
- **🔮 Advancement** — each team's probability of escaping the group and
  reaching every knockout stage, from a Monte Carlo simulation of the whole
  tournament (group matches driven by the market odds, knockouts by power
  ratings). Includes a title-favourites chart.
- **🔄 Caching & refresh** — API responses are cached to disk so the free-tier
  quota isn't burned on every page view. The cache auto-invalidates when a
  fixture's kickoff time has passed (a game has likely ended since the last
  fetch), and a **Refresh** button forces a re-fetch on demand.

## Running

```bash
poetry install
poetry run streamlit run src/world_cup_oracle/app.py
```

With **no API key** the app runs on a built-in, deterministic **sample dataset**
(a believable mid-group-stage snapshot) so everything works offline.

### Live data

Data is assembled in two layers (`data/loader.py`): a **base source** for
fixtures/standings/scorers, optionally enriched with a **betting-odds overlay**.

**Base source** — `WORLD_CUP_DATA_SOURCE`:

| Source | 2026 on free tier? | Key | Notes |
|---|---|---|---|
| **`worldcup26`** (default) | ✅ free, **no key** | none | community API; flaky uptime — retried & cached |
| `balldontlie` | ❌ free tier is `/teams` only | paid | bundles odds too |
| `api_football` | ❌ free tier is 2022–2024 | yes | — |

**Odds overlay** (optional) — set `THE_ODDS_API_KEY` from
<https://the-odds-api.com/> (free tier 500 req/mo) to attach real bookmaker
odds to every matching fixture. Without it, win probabilities come from the
Poisson power model.

So the default **fully-free** setup needs no key at all; add a free Odds API key
to get real betting odds:

```
WORLD_CUP_DATA_SOURCE=worldcup26
# THE_ODDS_API_KEY=your_odds_api_key
```

Any failure (key, plan, network, flaky server) degrades gracefully: last good
cache first, then the offline sample, always with a visible note.

## Tests

```bash
poetry run pytest
```

## How it's wired

```
src/world_cup_oracle/
  config.py            # API + tournament-format + simulation + cache constants
  teams.py             # the 12 groups, team codes and power ratings
  env.py               # load .env before config reads it
  data/
    loader.py          # base source + odds overlay + cache (never raises)
    worldcup26.py      # base source: free, no key (default)
    balldontlie.py     # base source: paid key
    api_football.py    # base source: key, 2022-2024 free
    the_odds_api.py    # odds overlay (THE_ODDS_API_KEY)
    sample.py          # offline dataset generator
    cache.py           # disk cache + "a game has ended" invalidation
  models/
    odds.py            # decimal odds <-> probabilities, Poisson goal model
    standings.py       # group tables + projected qualifiers
    bracket.py         # Round-of-32 seeding layout
    simulation.py      # Monte Carlo: P(reach stage) + expected games
    scorers.py         # projected final goal tallies
  viz/
    standings.py       # styled group tables
    bracket.py         # Plotly bracket flowchart
  app.py               # Streamlit UI (tabs + refresh)
```

> **Note on accuracy:** the sample groups resolve a few play-off placeholders to
> plausible qualifiers, and the offline bracket uses a fixed, clash-free
> approximation of FIFA's third-place combination table. Live API data replaces
> both. Power ratings are illustrative seeds, easy to tune in `teams.py`.

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

Copy `.env.example` to `.env`, pick a provider and drop in a matching key:

```
WORLD_CUP_DATA_SOURCE=balldontlie   # or: api_football
WORLD_CUP_API_KEY=your_key_here
```

Two providers are supported (`data/loader.py` dispatches on `WORLD_CUP_DATA_SOURCE`):

| Source | Free tier covers 2026? | Odds? | Register |
|---|---|---|---|
| **`balldontlie`** (default) | ✅ yes | ✅ yes | <https://app.balldontlie.io/> (FIFA API) |
| `api_football` | ❌ free tier is 2022–2024 only | paid plans | <https://www.api-football.com/> |

The app pulls fixtures, odds and goalscorers live; any API error (bad key, a
season your plan can't access, a network blip) degrades gracefully back to the
cached or sample data with a visible warning. The key must belong to the chosen
provider.

## Tests

```bash
poetry run pytest
```

## How it's wired

```
src/world_cup_oracle/
  config.py            # API + tournament-format + simulation + cache constants
  teams.py             # the 12 groups, team codes and power ratings
  data/
    loader.py          # dispatch on WORLD_CUP_DATA_SOURCE; else sample (never raises)
    balldontlie.py     # live client (default) -> normalised dataset
    api_football.py    # live client (alternative) -> normalised dataset
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

"""Global configuration for the World Cup Oracle app."""
from __future__ import annotations

import os
from pathlib import Path

from .env import load_dotenv

# Load .env before reading any settings below so file values take effect.
load_dotenv()

# --- API-Football (api-sports.io) -------------------------------------------
# Get a free key at https://www.api-football.com/ (or via RapidAPI) and set it
# in the environment (a .env file is loaded automatically by data.loader):
#
#   WORLD_CUP_API_KEY=your_key_here
#
# When no key is present the app transparently falls back to a generated
# offline sample dataset so everything still runs end-to-end.
API_KEY_ENV = "WORLD_CUP_API_KEY"
API_BASE_URL = "https://v3.football.api-sports.io"

# Which provider to pull fixtures/standings/scorers from:
#   worldcup26   - free, no key (default)
#   balldontlie  - needs a (paid) key in WORLD_CUP_API_KEY
#   api_football - needs a key in WORLD_CUP_API_KEY (free tier excludes 2026)
DATA_SOURCE = os.getenv("WORLD_CUP_DATA_SOURCE", "worldcup26").strip().lower()

# Optional betting odds, layered on top of the base source. Get a free key
# (500 req/mo) at https://the-odds-api.com/. Without it, win probabilities come
# from the Poisson power model instead of the market.
ODDS_API_KEY_ENV = "THE_ODDS_API_KEY"
ODDS_API_SPORT = os.getenv("WORLD_CUP_ODDS_SPORT", "soccer_fifa_world_cup")
ODDS_API_REGIONS = os.getenv("WORLD_CUP_ODDS_REGIONS", "us")

# League id 1 = "World Cup" in API-Football; season 2026 = the 2026 edition.
WORLD_CUP_LEAGUE_ID = int(os.getenv("WORLD_CUP_LEAGUE_ID", "1"))
WORLD_CUP_SEASON = int(os.getenv("WORLD_CUP_SEASON", "2026"))

# Bookmaker id used when pulling odds (8 = Bet365 on API-Football). Configurable
# because not every bookmaker covers every fixture.
ODDS_BOOKMAKER_ID = int(os.getenv("WORLD_CUP_BOOKMAKER_ID", "8"))

# --- Caching -----------------------------------------------------------------
# Live API responses are cached to disk to spare the free-tier quota. The cache
# is considered stale after CACHE_TTL_SECONDS, OR as soon as a fixture's kickoff
# is far enough in the past that the match has almost certainly finished since
# the cache was written (so results/standings refresh promptly).
CACHE_DIR = Path(os.getenv("WORLD_CUP_CACHE_DIR", str(Path(__file__).resolve().parents[2] / ".cache")))
CACHE_TTL_SECONDS = int(os.getenv("WORLD_CUP_CACHE_TTL", "600"))
MATCH_DURATION_MINUTES = 115  # 90' + stoppage; beyond this a kickoff has "ended"

# --- Tournament format -------------------------------------------------------
# 48 teams, 12 groups of 4. Top 2 of each group + 8 best third-placed teams
# advance to a Round of 32, then a straight knockout to the Final.
GROUP_NAMES = list("ABCDEFGHIJKL")
TEAMS_PER_GROUP = 4
THIRD_PLACE_QUALIFIERS = 8  # best third-placed teams that reach the Round of 32

KNOCKOUT_ROUNDS = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]
# Human-friendly "reached this stage" labels used for advancement probabilities.
STAGE_LABELS = [
    "Advance (top 2 / best 3rd)",
    "Round of 16",
    "Quarter-finals",
    "Semi-finals",
    "Final",
    "Winner",
]

# --- Simulation --------------------------------------------------------------
DEFAULT_SIMULATIONS = 50_000
# Poisson goal model: expected goals for an evenly-matched team, and how
# strongly a power-rating gap skews the expected goals.
GOAL_BASE = 1.30
GOAL_POWER_SCALE = 1.60
SIM_SEED = 2026
# Logistic steepness for a knockout (no-draw) tie from the power-rating gap.
KNOCKOUT_SCALE = 4.0

"""Data access layer.

A *dataset* is a plain dict with this normalised shape, produced either by the
live API-Football client (:mod:`.api_football`) or the offline generator
(:mod:`.sample`), and consumed everywhere else::

    {
        "source": "api" | "sample",
        "as_of": "YYYY-MM-DD",            # logical "today"
        "fixtures": [Fixture, ...],
        "scorers":  [{"player", "team", "goals"}, ...],
    }

    Fixture = {
        "id": int,
        "stage": "group" | "Round of 32" | "Round of 16" | ...,
        "group": "A".."L" | None,
        "matchday": int | None,
        "date": "YYYY-MM-DD",
        "home": team_name, "away": team_name,
        "status": "FT" | "NS",            # finished / not started
        "home_goals": int | None, "away_goals": int | None,
        "odds": {"home": float, "draw": float, "away": float} | None,
    }

Team metadata and group composition live in :mod:`world_cup_oracle.teams`.
"""

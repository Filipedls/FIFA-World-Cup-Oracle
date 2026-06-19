"""The 2026 FIFA World Cup teams, groups and (illustrative) power ratings.

The group composition follows the final draw made on 5 December 2025 in
Washington, D.C. A handful of slots that were still inter-continental / UEFA
play-off placeholders at the time of the draw are resolved here to a plausible
qualifier purely so the *offline sample dataset* is realistic — when an API key
is configured the real teams and results come straight from API-Football and
this table is only used as a fallback for power ratings.

``power`` is a 0..1 strength rating: ~0.85 = title favourite, ~0.25 = minnow.
It seeds the offline odds/score generator and is also used by the simulation
for any matchup the bookmaker odds do not (yet) cover, e.g. future knockout
ties between teams that have not been drawn against each other.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Team:
    name: str
    code: str          # 3-letter code, handy for compact bracket labels
    group: str
    power: float


# group -> list of (name, code, power)
_GROUPS: dict[str, list[tuple[str, str, float]]] = {
    "A": [("Mexico", "MEX", 0.62), ("South Africa", "RSA", 0.40), ("Korea Republic", "KOR", 0.55), ("Denmark", "DEN", 0.66)],
    "B": [("Canada", "CAN", 0.58), ("Qatar", "QAT", 0.42), ("Switzerland", "SUI", 0.64), ("Italy", "ITA", 0.74)],
    "C": [("Brazil", "BRA", 0.86), ("Morocco", "MAR", 0.66), ("Haiti", "HAI", 0.30), ("Scotland", "SCO", 0.52)],
    "D": [("United States", "USA", 0.63), ("Paraguay", "PAR", 0.50), ("Australia", "AUS", 0.52), ("Türkiye", "TUR", 0.62)],
    "E": [("Germany", "GER", 0.80), ("Curaçao", "CUW", 0.34), ("Côte d'Ivoire", "CIV", 0.60), ("Ecuador", "ECU", 0.58)],
    "F": [("Netherlands", "NED", 0.79), ("Japan", "JPN", 0.62), ("Tunisia", "TUN", 0.48), ("Sweden", "SWE", 0.58)],
    "G": [("Belgium", "BEL", 0.76), ("Egypt", "EGY", 0.56), ("Iran", "IRN", 0.54), ("New Zealand", "NZL", 0.36)],
    "H": [("Spain", "ESP", 0.87), ("Cabo Verde", "CPV", 0.36), ("Uruguay", "URU", 0.72), ("Saudi Arabia", "KSA", 0.44)],
    "I": [("France", "FRA", 0.85), ("Norway", "NOR", 0.64), ("Senegal", "SEN", 0.66), ("Iraq", "IRQ", 0.40)],
    "J": [("Argentina", "ARG", 0.88), ("Algeria", "ALG", 0.54), ("Austria", "AUT", 0.60), ("Jordan", "JOR", 0.42)],
    "K": [("Portugal", "POR", 0.82), ("Colombia", "COL", 0.68), ("Uzbekistan", "UZB", 0.44), ("Costa Rica", "CRC", 0.46)],
    "L": [("England", "ENG", 0.84), ("Croatia", "CRO", 0.70), ("Ghana", "GHA", 0.54), ("Panama", "PAN", 0.42)],
}


def all_teams() -> dict[str, Team]:
    teams: dict[str, Team] = {}
    for group, members in _GROUPS.items():
        for name, code, power in members:
            teams[name] = Team(name=name, code=code, group=group, power=power)
    return teams


def groups() -> dict[str, list[str]]:
    return {g: [name for name, _, _ in members] for g, members in _GROUPS.items()}


TEAMS: dict[str, Team] = all_teams()
GROUPS: dict[str, list[str]] = groups()

# Neutral rating for teams we have no prior on (e.g. a live API returns a team
# under a name not in this table, or a play-off qualifier we didn't anticipate).
DEFAULT_POWER = 0.50

# Map common provider spellings to our canonical names so power ratings and
# group membership line up across data sources.
_NAME_ALIASES = {
    "USA": "United States",
    "United States of America": "United States",
    "South Korea": "Korea Republic",
    "Korea, Republic of": "Korea Republic",
    "Turkey": "Türkiye",
    "Turkiye": "Türkiye",
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Curacao": "Curaçao",
    "Cape Verde": "Cabo Verde",
    "Cape Verde Islands": "Cabo Verde",
    "IR Iran": "Iran",
    "Czech Republic": "Czechia",
}


def canonical_name(name: str | None) -> str | None:
    """Normalise a team name to our canonical spelling (pass-through if known)."""
    if not name:
        return name
    return _NAME_ALIASES.get(name.strip(), name.strip())


def power_of(name: str) -> float:
    """Power rating for a team name, falling back to a neutral default so the
    models never crash on an unrecognised team."""
    team = TEAMS.get(name)
    return team.power if team else DEFAULT_POWER


# Confederation per (canonical) team name — used for confederation-aware bracket
# seeding. Covers the roster above plus likely qualifiers from the real draw.
_CONFEDERATION = {
    "UEFA": ["Denmark", "Switzerland", "Italy", "Scotland", "Germany", "Netherlands",
             "Sweden", "Belgium", "Spain", "France", "Norway", "Austria", "Portugal",
             "England", "Croatia", "Bosnia and Herzegovina", "Czechia", "Ukraine",
             "Poland", "Albania", "Romania", "Slovakia", "Türkiye", "Wales",
             "Northern Ireland", "Republic of Ireland", "North Macedonia", "Serbia"],
    "CONMEBOL": ["Brazil", "Argentina", "Uruguay", "Colombia", "Ecuador", "Paraguay",
                 "Peru", "Chile", "Bolivia", "Venezuela"],
    "CONCACAF": ["Mexico", "Canada", "United States", "Costa Rica", "Panama", "Haiti",
                 "Curaçao", "Jamaica", "Honduras"],
    "CAF": ["South Africa", "Morocco", "Côte d'Ivoire", "Tunisia", "Egypt", "Senegal",
            "Algeria", "Ghana", "Cabo Verde", "Cameroon", "Nigeria", "Mali",
            "Democratic Republic of the Congo"],
    "AFC": ["Korea Republic", "Qatar", "Australia", "Japan", "Iran", "Saudi Arabia",
            "Iraq", "Jordan", "Uzbekistan"],
    "OFC": ["New Zealand"],
}
_TEAM_CONFEDERATION: dict[str, str] = {
    team: conf for conf, members in _CONFEDERATION.items() for team in members
}


def confederation_of(name: str | None) -> str:
    """Confederation for a team name ('?' if unknown — treated as no clash)."""
    return _TEAM_CONFEDERATION.get(name, "?") if name else "?"

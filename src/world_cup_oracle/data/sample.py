"""Offline sample-dataset generator.

Produces a believable mid-group-stage snapshot of the 2026 World Cup so the app
runs end-to-end with no API key. Matches whose date is on/before ``as_of`` are
played out with the Poisson goal model and given final scores + goal scorers;
later matches are left as fixtures. Everything is deterministic (seeded).
"""
from __future__ import annotations

from ..config import GROUP_NAMES
from ..models.odds import odds_from_power, poisson_lambdas
from ..teams import GROUPS, TEAMS

# Logical "today" — the tournament opened on 2026-06-11.
AS_OF = "2026-06-13"

# Round-robin matchday pairings for a 4-team group (indices into the group list).
_MATCHDAY_PAIRINGS = [
    [(0, 1), (2, 3)],   # matchday 1
    [(0, 2), (3, 1)],   # matchday 2
    [(3, 0), (1, 2)],   # matchday 3
]

# A few recognisable names so the scorers table reads nicely; any other goals
# are attributed to generic "<TEAM> forwards". Purely cosmetic sample flavour.
_STAR_PLAYERS: dict[str, list[str]] = {
    "Brazil": ["Vinícius Jr", "Rodrygo", "Raphinha"],
    "Argentina": ["Lionel Messi", "Julián Álvarez", "Lautaro Martínez"],
    "France": ["Kylian Mbappé", "Ousmane Dembélé", "Bradley Barcola"],
    "Spain": ["Lamine Yamal", "Nico Williams", "Álvaro Morata"],
    "England": ["Harry Kane", "Bukayo Saka", "Jude Bellingham"],
    "Portugal": ["Cristiano Ronaldo", "Bruno Fernandes", "Rafael Leão"],
    "Germany": ["Florian Wirtz", "Kai Havertz", "Jamal Musiala"],
    "Netherlands": ["Cody Gakpo", "Memphis Depay", "Xavi Simons"],
    "Belgium": ["Romelu Lukaku", "Kevin De Bruyne", "Jérémy Doku"],
    "Norway": ["Erling Haaland", "Alexander Sørloth", "Martin Ødegaard"],
    "Uruguay": ["Darwin Núñez", "Federico Valverde", "Facundo Pellistri"],
    "Croatia": ["Andrej Kramarić", "Luka Modrić", "Ante Budimir"],
}


# kickoff slots (local-ish), cycled so matches don't all start at once
_KICKOFF_HOURS = ["15:00", "18:00", "21:00", "12:00"]


def _date_for(group_idx: int, matchday: int) -> str:
    # MD1 spread over Jun 11-14, MD2 over Jun 16-19, MD3 over Jun 21-24.
    base = [11, 16, 21][matchday]
    day = base + (group_idx // 3)
    return f"2026-06-{day:02d}"


def _kickoff_for(date: str, slot: int) -> str:
    return f"{date}T{_KICKOFF_HOURS[slot % len(_KICKOFF_HOURS)]}:00+00:00"


def build_dataset(seed: int = 7) -> dict:
    import numpy as np

    rng = np.random.default_rng(seed)
    fixtures: list[dict] = []
    goals: dict[tuple[str, str], int] = {}  # (player, team) -> goals
    fid = 1

    for gi, group in enumerate(GROUP_NAMES):
        members = GROUPS[group]
        for md, pairings in enumerate(_MATCHDAY_PAIRINGS):
            date = _date_for(gi, md)
            for slot, (hi, ai) in enumerate(pairings):
                home, away = members[hi], members[ai]
                odds = odds_from_power(TEAMS[home].power, TEAMS[away].power)
                played = date <= AS_OF
                fixture = {
                    "id": fid,
                    "stage": "group",
                    "group": group,
                    "matchday": md + 1,
                    "date": date,
                    "kickoff": _kickoff_for(date, gi + slot),
                    "home": home,
                    "away": away,
                    "status": "FT" if played else "NS",
                    "home_goals": None,
                    "away_goals": None,
                    "odds": odds,
                }
                if played:
                    lam_h, lam_a = poisson_lambdas(TEAMS[home].power, TEAMS[away].power)
                    hg = int(rng.poisson(lam_h))
                    ag = int(rng.poisson(lam_a))
                    fixture["home_goals"] = hg
                    fixture["away_goals"] = ag
                    _attribute_goals(home, hg, goals, rng)
                    _attribute_goals(away, ag, goals, rng)
                fixtures.append(fixture)
                fid += 1

    scorers = [
        {"player": player, "team": team, "goals": n}
        for (player, team), n in sorted(goals.items(), key=lambda kv: (-kv[1], kv[0][0]))
    ]
    return {"source": "sample", "as_of": AS_OF, "fixtures": fixtures, "scorers": scorers}


def _attribute_goals(team: str, n_goals: int, goals: dict, rng) -> None:
    if n_goals <= 0:
        return
    roster = _STAR_PLAYERS.get(team, [f"{team} forward", f"{team} midfielder"])
    # Weight earlier (star) names more heavily.
    weights = [len(roster) - i for i in range(len(roster))]
    weights = [w / sum(weights) for w in weights]
    for _ in range(n_goals):
        player = roster[int(rng.choice(len(roster), p=weights))]
        goals[(player, team)] = goals.get((player, team), 0) + 1

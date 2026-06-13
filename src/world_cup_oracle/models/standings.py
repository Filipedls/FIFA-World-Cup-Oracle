"""Compute group standings (P W D L GF GA GD Pts Form) from played fixtures."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import GROUP_NAMES
from ..teams import GROUPS


def fixture_groups(fixtures: list[dict]) -> list[str]:
    """Group letters present in the fixtures (falls back to the static A–L)."""
    found = sorted({f["group"] for f in fixtures
                    if f.get("group") and f["stage"] == "group"})
    return found or GROUP_NAMES


def group_members(fixtures: list[dict], group: str) -> list[str]:
    """All teams appearing in a group's fixtures, in first-seen order. Derived
    from the data so it works whatever names the source uses; falls back to the
    static roster when a group has no fixtures yet."""
    members: list[str] = []
    for f in fixtures:
        if f.get("group") != group or f["stage"] != "group":
            continue
        for team in (f["home"], f["away"]):
            if team and team not in members:
                members.append(team)
    return members or list(GROUPS.get(group, []))


@dataclass
class TeamRow:
    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0
    form: list[str] = field(default_factory=list)  # chronological W/D/L

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn

    def as_dict(self) -> dict:
        return {
            "Team": self.team, "P": self.played, "W": self.won, "D": self.drawn,
            "L": self.lost, "GF": self.gf, "GA": self.ga, "GD": self.gd,
            "Pts": self.points, "Form": "".join(self.form[-5:]),
        }


def _sort_key(row: TeamRow):
    # FIFA group ranking: points, then goal difference, then goals scored.
    return (-row.points, -row.gd, -row.gf, row.team)


def group_finished_fixtures(fixtures: list[dict], group: str) -> list[dict]:
    rows = [f for f in fixtures
            if f.get("group") == group and f["stage"] == "group" and f["status"] == "FT"]
    return sorted(rows, key=lambda f: (f["date"], f["id"]))


def compute_group(fixtures: list[dict], group: str) -> list[TeamRow]:
    rows = {team: TeamRow(team) for team in group_members(fixtures, group)}
    for f in group_finished_fixtures(fixtures, group):
        h, a = rows[f["home"]], rows[f["away"]]
        hg, ag = f["home_goals"], f["away_goals"]
        for r, gf, ga in ((h, hg, ag), (a, ag, hg)):
            r.played += 1
            r.gf += gf
            r.ga += ga
        if hg > ag:
            h.won += 1; a.lost += 1; h.form.append("W"); a.form.append("L")
        elif hg < ag:
            a.won += 1; h.lost += 1; a.form.append("W"); h.form.append("L")
        else:
            h.drawn += 1; a.drawn += 1; h.form.append("D"); a.form.append("D")
    return sorted(rows.values(), key=_sort_key)


def compute_all_groups(fixtures: list[dict]) -> dict[str, list[TeamRow]]:
    return {g: compute_group(fixtures, g) for g in fixture_groups(fixtures)}


def project_qualifiers(fixtures: list[dict]) -> dict[tuple, str]:
    """Resolve each bracket slot key to the team currently filling it, based on
    the live standings (1st/2nd of each group + the 8 best third-placed teams).
    Used to draw a projected bracket before the knockouts are decided.
    """
    tables = compute_all_groups(fixtures)
    out: dict[tuple, str] = {}
    thirds: list[TeamRow] = []
    for g, rows in tables.items():
        out[("W", g)] = rows[0].team
        out[("R", g)] = rows[1].team
        thirds.append(rows[2])
    thirds.sort(key=_sort_key)
    for k, row in enumerate(thirds[:8]):
        out[("T", k)] = row.team
    return out

"""Official 2026 FIFA World Cup knockout bracket layout (48-team format).

The Round-of-32 winner/runner pairings and the third-place *eligibility sets*
follow FIFA's published bracket (matches 73–88), and the match order below is
arranged so that pairing consecutive matches reproduces the official Round-of-16
(89–96), quarter-final (97–100) and semi-final (101–102) adjacency.

Slot sources:
    ("W", "A")  -> winner of group A
    ("R", "B")  -> runner-up of group B
    ("T", k)    -> the third-placed team assigned to third-slot k

Third-place assignment: FIFA uses a fixed combination table that maps the eight
qualifying third-placed teams to slots depending on *which* groups produced them.
Rather than hard-code all 495 combinations, :func:`assign_thirds` does a
constrained matching that respects each slot's official eligibility set and then
minimises same-confederation Round-of-32 clashes — a faithful, lighter
approximation.
"""
from __future__ import annotations

from ..teams import confederation_of


def _clash(confed_a: str, confed_b: str) -> bool:
    """Same confederation (unknowns never clash)."""
    return confed_a == confed_b and confed_a != "?"

# Third-slot k -> (group whose WINNER occupies the other side, eligible 3rd groups)
THIRD_SLOTS = [
    {"winner": "E", "eligible": set("ABCDF")},   # match 74
    {"winner": "I", "eligible": set("CDFGH")},   # match 77
    {"winner": "A", "eligible": set("CEFHI")},   # match 79
    {"winner": "L", "eligible": set("EHIJK")},   # match 80
    {"winner": "D", "eligible": set("BEFIJ")},   # match 81
    {"winner": "G", "eligible": set("AEHIJ")},   # match 82
    {"winner": "B", "eligible": set("EFGIJ")},   # match 85
    {"winner": "K", "eligible": set("DEIJL")},   # match 87
]

# Round of 32 in TREE ORDER (consecutive pairs feed the same Round-of-16 match).
R32_MATCHES: list[tuple[tuple, tuple]] = [
    (("W", "E"), ("T", 0)),   # 74  ┐ R16 M89
    (("W", "I"), ("T", 1)),   # 77  ┘
    (("R", "A"), ("R", "B")),  # 73  ┐ R16 M90
    (("W", "F"), ("R", "C")),  # 75  ┘
    (("R", "K"), ("R", "L")),  # 83  ┐ R16 M93
    (("W", "H"), ("R", "J")),  # 84  ┘
    (("W", "D"), ("T", 4)),   # 81  ┐ R16 M94
    (("W", "G"), ("T", 5)),   # 82  ┘
    (("W", "C"), ("R", "F")),  # 76  ┐ R16 M91
    (("R", "E"), ("R", "I")),  # 78  ┘
    (("W", "A"), ("T", 2)),   # 79  ┐ R16 M92
    (("W", "L"), ("T", 3)),   # 80  ┘
    (("W", "J"), ("R", "H")),  # 86  ┐ R16 M95
    (("R", "D"), ("R", "G")),  # 88  ┘
    (("W", "B"), ("T", 6)),   # 85  ┐ R16 M96
    (("W", "K"), ("T", 7)),   # 87  ┘
]

ROUND_SIZES = [16, 8, 4, 2, 1]
ROUND_NAMES = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]


def slot_label(slot: tuple) -> str:
    kind, ref = slot
    if kind == "W":
        return f"1{ref}"
    if kind == "R":
        return f"2{ref}"
    return "3rd"


def assign_thirds(thirds: list[tuple], winner_team_by_group: dict[str, str],
                  confed_of=confederation_of) -> dict[int, str]:
    """Map qualifying third-placed teams to third-slots.

    ``thirds`` is a list of (team, group, strength). Returns {slot_index: team}.
    Hard constraint: a third may only fill a slot whose official eligibility set
    contains its group. Soft objective: minimise same-confederation clashes with
    the group winner the slot faces. Strength orders the search (stronger thirds
    placed first) for a stable, sensible result.
    """
    thirds = sorted(thirds, key=lambda e: -e[2])
    slot_confed = {}
    for k, s in enumerate(THIRD_SLOTS):
        w = winner_team_by_group.get(s["winner"])
        slot_confed[k] = confed_of(w) if w else None

    best = {"cost": None, "assign": None}
    assign: dict[int, str] = {}
    used: set[int] = set()

    def backtrack(i: int, cost: int) -> None:
        if best["cost"] == 0:
            return
        if best["cost"] is not None and cost >= best["cost"]:
            return
        if i == len(thirds):
            best["cost"], best["assign"] = cost, dict(assign)
            return
        team, group, _ = thirds[i]
        cands = [k for k in range(len(THIRD_SLOTS))
                 if k not in used and group in THIRD_SLOTS[k]["eligible"]]
        cands.sort(key=lambda k: _clash(confed_of(team), slot_confed[k]))  # non-clash first
        for k in cands:
            clash = 1 if _clash(confed_of(team), slot_confed[k]) else 0
            used.add(k); assign[k] = team
            backtrack(i + 1, cost + clash)
            used.discard(k); del assign[k]

    backtrack(0, 0)
    if best["assign"] is not None and len(best["assign"]) == len(thirds):
        return best["assign"]
    return _assign_relaxed(thirds, slot_confed, confed_of)


def _assign_relaxed(thirds, slot_confed, confed_of) -> dict[int, str]:
    """Fallback when eligibility can't be perfectly satisfied: ignore eligibility,
    just avoid facing your own group's winner and prefer confederation-distinct."""
    assign, used = {}, set()
    for team, group, _ in thirds:
        cands = [k for k in range(len(THIRD_SLOTS))
                 if k not in used and THIRD_SLOTS[k]["winner"] != group]
        cands = cands or [k for k in range(len(THIRD_SLOTS)) if k not in used]
        if not cands:
            break
        cands.sort(key=lambda k: _clash(confed_of(team), slot_confed[k]))
        assign[cands[0]] = team
        used.add(cands[0])
    return assign


def build_slot_teams(winners_by_group: dict[str, str], runners_by_group: dict[str, str],
                     qualifying_thirds: list[tuple], confed_of=confederation_of) -> dict[tuple, str]:
    """Full slot→team mapping for the bracket: winners, runners, and the
    confederation-aware third-place assignment."""
    slots: dict[tuple, str] = {}
    for g, t in winners_by_group.items():
        slots[("W", g)] = t
    for g, t in runners_by_group.items():
        slots[("R", g)] = t
    for k, team in assign_thirds(qualifying_thirds, winners_by_group, confed_of).items():
        slots[("T", k)] = team
    return slots

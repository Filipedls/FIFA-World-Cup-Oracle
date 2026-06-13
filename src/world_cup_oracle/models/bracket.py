"""Knockout bracket layout for the 48-team format.

The Round of 32 is seeded from group finishing positions. Slot sources:
    ("W", "A")  -> winner of group A
    ("R", "B")  -> runner-up of group B
    ("T", k)    -> the k-th best (0 = best) of the qualifying third-placed teams

Note: FIFA assigns the eight qualifying third-placed teams to specific slots via
a published combination table that depends on *which* groups produce them. This
layout uses a fixed, same-group-clash-free approximation so the offline bracket
is complete and drawable; when the live API exposes the real Round of 32
fixtures the app uses those directly instead.
"""
from __future__ import annotations

# 16 Round-of-32 matches as (top slot, bottom slot). Match i feeds Round-of-16
# match i // 2, and so on up the tree.
R32_MATCHES: list[tuple[tuple, tuple]] = [
    (("W", "A"), ("R", "B")),
    (("W", "C"), ("R", "D")),
    (("W", "E"), ("R", "F")),
    (("W", "G"), ("R", "H")),
    (("W", "I"), ("R", "J")),
    (("W", "K"), ("R", "L")),
    (("W", "B"), ("T", 0)),
    (("W", "D"), ("T", 1)),
    (("W", "F"), ("T", 2)),
    (("W", "H"), ("T", 3)),
    (("W", "J"), ("T", 4)),
    (("W", "L"), ("T", 5)),
    (("R", "A"), ("R", "C")),
    (("R", "E"), ("R", "G")),
    (("R", "I"), ("T", 6)),
    (("R", "K"), ("T", 7)),
]

ROUND_SIZES = [16, 8, 4, 2, 1]  # matches per knockout round
ROUND_NAMES = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]


def slot_label(slot: tuple) -> str:
    kind, ref = slot
    if kind == "W":
        return f"1{ref}"      # winner of group
    if kind == "R":
        return f"2{ref}"      # runner-up
    return f"3#{ref + 1}"     # ranked third-placed qualifier

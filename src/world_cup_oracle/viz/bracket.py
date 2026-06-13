"""Knockout bracket as a Plotly flowchart with connector lines between ties.

Given the projected Round-of-32 line-up (from live standings) it advances the
stronger team each round to draw a complete, readable bracket. This is a
deterministic "chalk" projection — the per-stage *probabilities* live in the
simulation tab; this view is about structure and matchups.
"""
from __future__ import annotations

import plotly.graph_objects as go

from ..models import bracket as bk
from ..teams import TEAMS

_BOX_HALF_W = 1.25
_BOX_HALF_H = 0.42
_ROUND_DX = 3.4
_TBD = "TBD"


def _power(team: str) -> float:
    return TEAMS[team].power if team in TEAMS else 0.0


def _favourite(a: str, b: str) -> str:
    if a == _TBD:
        return b
    if b == _TBD:
        return a
    return a if _power(a) >= _power(b) else b


def build_rounds(slot_teams: dict[tuple, str]) -> list[list[tuple[str, str]]]:
    """Return matchups per round: rounds[r] is a list of (top, bottom) teams.

    Round 0 comes from the bracket seeding; later rounds advance the favourite.
    """
    r32 = [(slot_teams.get(top, _TBD), slot_teams.get(bot, _TBD))
           for top, bot in bk.R32_MATCHES]
    rounds = [r32]
    winners = [_favourite(a, b) for a, b in r32]
    while len(winners) > 1:
        nxt = [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]
        rounds.append(nxt)
        winners = [_favourite(a, b) for a, b in nxt]
    return rounds  # 5 rounds: R32, R16, QF, SF, Final


def figure(slot_teams: dict[tuple, str]) -> go.Figure:
    rounds = build_rounds(slot_teams)
    n_leaf = len(rounds[0])

    # y position of each match per round
    ypos: list[list[float]] = [[float(n_leaf - 1 - m) for m in range(n_leaf)]]
    for r in range(1, len(rounds)):
        prev = ypos[-1]
        ypos.append([(prev[2 * m] + prev[2 * m + 1]) / 2 for m in range(len(rounds[r]))])

    fig = go.Figure()

    # connector lines (child -> parent) drawn first so boxes sit on top
    for r in range(len(rounds) - 1):
        x_child = r * _ROUND_DX
        x_parent = (r + 1) * _ROUND_DX
        mid = (x_child + _BOX_HALF_W + x_parent - _BOX_HALF_W) / 2
        for m in range(len(rounds[r])):
            y_c = ypos[r][m]
            y_p = ypos[r + 1][m // 2]
            xs = [x_child + _BOX_HALF_W, mid, mid, x_parent - _BOX_HALF_W]
            ys = [y_c, y_c, y_p, y_p]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                                     line=dict(color="#888", width=1),
                                     hoverinfo="skip", showlegend=False))

    # match boxes + winner box
    for r, matches in enumerate(rounds):
        x = r * _ROUND_DX
        for m, (top, bottom) in enumerate(matches):
            y = ypos[r][m]
            fav = _favourite(top, bottom)
            _add_match_box(fig, x, y, top, bottom, fav)

    champ = _favourite(*rounds[-1][0])
    x_champ = len(rounds) * _ROUND_DX
    y_champ = ypos[-1][0]
    fig.add_shape(type="rect", x0=x_champ - _BOX_HALF_W, x1=x_champ + _BOX_HALF_W,
                  y0=y_champ - _BOX_HALF_H, y1=y_champ + _BOX_HALF_H,
                  line=dict(color="#d4af37", width=2), fillcolor="#3a2f00")
    fig.add_annotation(x=x_champ, y=y_champ, text=f"🏆 {champ}", showarrow=False,
                       font=dict(color="#ffd700", size=13))

    # round headers
    for r, name in enumerate(bk.ROUND_NAMES):
        fig.add_annotation(x=r * _ROUND_DX, y=n_leaf + 0.2, text=f"<b>{name}</b>",
                           showarrow=False, font=dict(size=12, color="#bbb"))
    fig.add_annotation(x=x_champ, y=n_leaf + 0.2, text="<b>Champion</b>",
                       showarrow=False, font=dict(size=12, color="#bbb"))

    fig.update_xaxes(visible=False, range=[-_BOX_HALF_W - 0.3, x_champ + _BOX_HALF_W + 0.3])
    fig.update_yaxes(visible=False, range=[-1, n_leaf + 1])
    fig.update_layout(height=max(620, n_leaf * 42), margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      showlegend=False)
    return fig


def _add_match_box(fig, x, y, top, bottom, favourite) -> None:
    fig.add_shape(type="rect", x0=x - _BOX_HALF_W, x1=x + _BOX_HALF_W,
                  y0=y - _BOX_HALF_H, y1=y + _BOX_HALF_H,
                  line=dict(color="#555", width=1), fillcolor="#161b22")
    for label, dy in ((top, _BOX_HALF_H / 2), (bottom, -_BOX_HALF_H / 2)):
        bold = label == favourite and label != _TBD
        text = f"<b>{label}</b>" if bold else label
        color = "#fff" if bold else "#9aa"
        fig.add_annotation(x=x, y=y + dy, text=text, showarrow=False,
                           font=dict(size=11, color=color))

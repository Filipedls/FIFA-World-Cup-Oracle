"""Knockout bracket as a Plotly flowchart with connector lines between ties.

A bracket is a ``(rounds, champion)`` pair, where ``rounds[r]`` is the list of
``(top, bottom)`` matchups in round r (R32 → Final) and ``champion`` is the team
that wins the final. The team shown advancing from each match is whichever side
appears in the next round, so bolding is correct no matter how the bracket was
built. Three builders produce that pair:

  * :func:`build_rounds`          - from a slot→team mapping, favourite advances
  * :func:`rounds_from_knockouts` - from the source's real knockout fixtures
                                    (real result advances; favourite fills gaps)

Per-tie hover probabilities use the power-rating model (:func:`knockout_win_prob`).
"""
from __future__ import annotations

import plotly.graph_objects as go

from ..models import bracket as bk
from ..models.odds import knockout_win_prob
from ..teams import power_of as _default_power

_BOX_HALF_W = 1.25
_BOX_HALF_H = 0.42
_ROUND_DX = 3.4
_TBD = "TBD"


def _favourite(a: str, b: str, power) -> str:
    if a == _TBD:
        return b
    if b == _TBD:
        return a
    return a if power(a) >= power(b) else b


def build_rounds(slot_teams: dict[tuple, str], power=_default_power) -> tuple[list, str]:
    """Seed the Round of 32 from a slot→team mapping; advance the favourite each
    round. Returns (rounds, champion). ``power`` is a name→rating callable."""
    r32 = [(slot_teams.get(top, _TBD), slot_teams.get(bot, _TBD))
           for top, bot in bk.R32_MATCHES]
    return _grow(r32, lambda t, b: _favourite(t, b, power))


def rounds_from_knockouts(fixtures: list[dict], power=_default_power) -> tuple[list, str] | None:
    """Build the bracket from the source's real knockout fixtures. Each tie is
    won by the real result when the match is finished, otherwise by the
    favourite. Returns None if no Round-of-32 fixtures with teams exist yet."""
    ko = [f for f in fixtures
          if f.get("stage") in bk.ROUND_NAMES and f.get("home") and f.get("away")]
    r32 = sorted((f for f in ko if f["stage"] == "Round of 32"),
                 key=lambda f: (f.get("id") or 0))
    if not r32:
        return None
    result_by_pair = {
        frozenset((f["home"], f["away"])): f for f in ko
        if f["status"] == "FT" and f["home_goals"] is not None
    }

    def advance(top: str, bottom: str) -> str:
        f = result_by_pair.get(frozenset((top, bottom)))
        if f and f["home_goals"] != f["away_goals"]:
            return f["home"] if f["home_goals"] > f["away_goals"] else f["away"]
        return _favourite(top, bottom, power)

    return _grow([(f["home"], f["away"]) for f in r32], advance)


def _grow(r32: list[tuple[str, str]], advance) -> tuple[list, str]:
    rounds = [r32]
    winners = [advance(t, b) for t, b in r32]
    while len(winners) > 1:
        nxt = [(winners[i], winners[i + 1]) for i in range(0, len(winners) - 1, 2)]
        rounds.append(nxt)
        winners = [advance(t, b) for t, b in nxt]
    return rounds, (winners[0] if winners else _TBD)


def _advancer(rounds: list, champion: str, r: int, m: int) -> str:
    """The team that progresses from match (r, m) — i.e. the one that appears in
    the next round (or the champion, for the final)."""
    if r < len(rounds) - 1:
        return rounds[r + 1][m // 2][m % 2]
    return champion


def figure(rounds: list, champion: str, power=_default_power) -> go.Figure:
    n_leaf = len(rounds[0])

    ypos: list[list[float]] = [[float(n_leaf - 1 - m) for m in range(n_leaf)]]
    for r in range(1, len(rounds)):
        prev = ypos[-1]
        ypos.append([(prev[2 * m] + prev[2 * m + 1]) / 2 for m in range(len(rounds[r]))])

    fig = go.Figure()

    # connector lines (child -> parent) first, so boxes sit on top
    for r in range(len(rounds) - 1):
        x_child, x_parent = r * _ROUND_DX, (r + 1) * _ROUND_DX
        mid = (x_child + _BOX_HALF_W + x_parent - _BOX_HALF_W) / 2
        for m in range(len(rounds[r])):
            y_c, y_p = ypos[r][m], ypos[r + 1][m // 2]
            fig.add_trace(go.Scatter(
                x=[x_child + _BOX_HALF_W, mid, mid, x_parent - _BOX_HALF_W],
                y=[y_c, y_c, y_p, y_p], mode="lines",
                line=dict(color="#888", width=1), hoverinfo="skip", showlegend=False))

    hover_x, hover_y, hover_text = [], [], []
    for r, matches in enumerate(rounds):
        x = r * _ROUND_DX
        for m, (top, bottom) in enumerate(matches):
            y = ypos[r][m]
            _add_match_box(fig, x, y, top, bottom, _advancer(rounds, champion, r, m))
            hover_x.append(x)
            hover_y.append(y)
            hover_text.append(_match_hover(bk.ROUND_NAMES[r], top, bottom, power))

    x_champ = len(rounds) * _ROUND_DX
    y_champ = ypos[-1][0]
    fig.add_shape(type="rect", x0=x_champ - _BOX_HALF_W, x1=x_champ + _BOX_HALF_W,
                  y0=y_champ - _BOX_HALF_H, y1=y_champ + _BOX_HALF_H,
                  line=dict(color="#d4af37", width=2), fillcolor="#3a2f00")
    fig.add_annotation(x=x_champ, y=y_champ, text=f"🏆 {champion}", showarrow=False,
                       font=dict(color="#ffd700", size=13))

    fig.add_trace(go.Scatter(
        x=hover_x, y=hover_y, mode="markers", showlegend=False,
        marker=dict(size=46, color="rgba(0,0,0,0)"),
        hoverinfo="text", hovertext=hover_text))

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


def _match_hover(round_name: str, top: str, bottom: str, power) -> str:
    if _TBD in (top, bottom):
        return f"<b>{round_name}</b><br>{top}  vs  {bottom}<br><i>teams not yet decided</i>"
    p_top = knockout_win_prob(power(top), power(bottom))
    return (f"<b>{round_name}</b><br>"
            f"{top}: {p_top:.0%} to advance<br>"
            f"{bottom}: {1 - p_top:.0%} to advance")


def _add_match_box(fig, x, y, top, bottom, advancer) -> None:
    fig.add_shape(type="rect", x0=x - _BOX_HALF_W, x1=x + _BOX_HALF_W,
                  y0=y - _BOX_HALF_H, y1=y + _BOX_HALF_H,
                  line=dict(color="#555", width=1), fillcolor="#161b22")
    for label, dy in ((top, _BOX_HALF_H / 2), (bottom, -_BOX_HALF_H / 2)):
        bold = label == advancer and label != _TBD
        text = f"<b>{label}</b>" if bold else label
        fig.add_annotation(x=x, y=y + dy, text=text, showarrow=False,
                           font=dict(size=11, color="#fff" if bold else "#9aa"))

"""Render group standings as styled tables, FIFA-site style."""
from __future__ import annotations

import pandas as pd

from ..models.standings import TeamRow

# qualification zone colours by finishing position (0-indexed)
_QUALIFY = "#1b5e20"   # top 2: through
_PLAYOFF = "#5d4037"   # 3rd: maybe (best 8 thirds advance)


# display order: Pts promoted to the second column (after Team)
_COLUMN_ORDER = ["Team", "Pts", "P", "W", "D", "L", "GF", "GA", "GD", "Form"]


def standings_dataframe(rows: list[TeamRow]) -> pd.DataFrame:
    df = pd.DataFrame([r.as_dict() for r in rows])[_COLUMN_ORDER]
    df.index = range(1, len(df) + 1)
    df.index.name = "#"
    return df


def expected_standings_dataframe(rows: list[tuple]) -> pd.DataFrame:
    """Projected final table from ``expected_standings`` rows:
    (team, exp_points, exp_gd, exp_gf)."""
    df = pd.DataFrame(
        [{"Team": t, "Pts": round(pts, 1), "GD": round(gd, 1), "GF": round(gf, 1)}
         for (t, pts, gd, gf) in rows])
    df.index = range(1, len(df) + 1)
    df.index.name = "#"
    return df


def style_standings(df: pd.DataFrame):
    """Return a pandas Styler colouring qualification zones."""
    def row_style(row):
        pos = row.name
        if pos <= 2:
            return [f"background-color: {_QUALIFY}; color: white"] * len(row)
        if pos == 3:
            return [f"background-color: {_PLAYOFF}; color: white"] * len(row)
        return [""] * len(row)

    return df.style.apply(row_style, axis=1)

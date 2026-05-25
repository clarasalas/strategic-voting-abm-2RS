"""
fr_elections.py
---------------
Plot poll-vs-result support distributions for French presidential elections.

Each figure shows horizontal stacked-bar distributions for:
  • Pre-electoral poll  (Round 1)
  • Actual result       (Round 1)
  • Actual result       (Round 2)  — only when data is available

Data sources
------------
    FR-electoral_data.csv       party-level poll and result shares by year

Outputs
-------
    fr{year}_support.png        one file per election year (with --save)

Usage
-----
    python fr_elections.py                    # all years
    python fr_elections.py --years 2007 2022  # specific years
    python fr_elections.py --save             # save PNG files
"""

import argparse

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle

# ── Constants ─────────────────────────────────────────────────────────────────

DATA_FILE = "FR-electoral_data.csv"

COLUMN_RENAME = {
    "pre electoral support ": "poll_r1",
    "electoral support (round 1)": "result_r1",
    "electoral support (round 2)": "result_r2",
}


# ── Data loading & cleaning ────────────────────────────────────────────────────


def load_data(filepath: str = DATA_FILE) -> pd.DataFrame:
    """Load the CSV, normalise column names, and parse French-locale decimals."""
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    df = df.rename(columns=COLUMN_RENAME)

    for col in ("poll_r1", "result_r1", "result_r2"):
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.replace(",", ".", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalise stray values > 1  (e.g. "41,45" should be 0.4145)
    for col in ("poll_r1", "result_r1", "result_r2"):
        mask = df[col] > 1
        df.loc[mask, col] = df.loc[mask, col] / 100

    return df


# ── Color map ─────────────────────────────────────────────────────────────────


def build_color_map(df: pd.DataFrame) -> dict:
    """
    Assign a Spectral color to every party based on its ideological ranking.
    Built once from the full dataset so colors are consistent across years.
    """
    parties = (
        df[["party", "ranking"]]
        .drop_duplicates("party")
        .sort_values("ranking")
        .reset_index(drop=True)
    )
    n = len(parties)
    cmap = plt.colormaps["Spectral"]
    norm = Normalize(vmin=0, vmax=max(n - 1, 1))

    return {
        row["party"]: "#{:02x}{:02x}{:02x}".format(
            *[int(c * 255) for c in cmap(norm(i))[:3]]
        )
        for i, row in parties.iterrows()
    }


# ── Drawing helpers ───────────────────────────────────────────────────────────


def _luminance(hex_color: str) -> float:
    """Relative luminance — used to pick a legible label colour."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def draw_stacked_bar(
    ax: plt.Axes,
    row_data: pd.DataFrame,
    color_map: dict,
    padding: float = 0.005,
) -> None:
    """
    Draw a single horizontal stacked bar on *ax*.

    Parameters
    ----------
    ax:        Matplotlib axes to draw on.
    row_data:  DataFrame with columns ``party``, ``ranking``, ``share``
               (already normalised to sum to 1).
    color_map: Mapping from party name to hex color string.
    padding:   Small horizontal margin on each side of the bar.
    """
    rows = row_data.sort_values("ranking").reset_index(drop=True)

    BAR_Y, BAR_H = 0.25, 0.55
    THRESHOLD_WIDE = 0.045
    THRESHOLD_NARROW = 0.018

    cursor = 0.0
    for _, row in rows.iterrows():
        party = row["party"]
        w = row["share"]
        color = color_map.get(party, "#aaaaaa")
        label_color = "white" if _luminance(color) < 0.45 else "#111"

        ax.add_patch(
            Rectangle(
                (cursor, BAR_Y),
                w,
                BAR_H,
                facecolor=color,
                alpha=0.75,
                edgecolor="#333",
                linewidth=0.6,
                zorder=2,
            )
        )

        cx, cy = cursor + w / 2, BAR_Y + BAR_H / 2
        if w >= THRESHOLD_WIDE:
            ax.text(
                cx, cy + 0.07, party,
                ha="center", va="center", fontsize=11, fontweight="bold",
                color=label_color, zorder=3,
            )
            ax.text(
                cx, cy - 0.09, f"{w * 100:.1f}%",
                ha="center", va="center", fontsize=7,
                color=label_color, zorder=3,
            )
        elif w >= THRESHOLD_NARROW:
            ax.text(
                cx, cy, party,
                ha="center", va="center", fontsize=7.5, fontweight="bold",
                color=label_color, rotation=90, zorder=3,
            )

        cursor += w

    ax.set_xlim(-padding, 1 + padding)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


# ── Per-year figure ───────────────────────────────────────────────────────────


def _prepare_bar(year_df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Extract and normalise shares for one bar (poll_r1 / result_r1 / result_r2)."""
    data = (
        year_df[["party", "ranking", col]]
        .dropna(subset=[col])
        .rename(columns={col: "share"})
        .copy()
    )
    total = data["share"].sum()
    if total > 0:
        data["share"] /= total
    return data


def make_figure(
    year_df: pd.DataFrame,
    color_map: dict,
    year: int,
    save: bool = False,
) -> None:
    """Build and display (and optionally save) the figure for one election year."""
    has_r2 = year_df["result_r2"].notna().any()
    n_rows = 3 if has_r2 else 2

    fig, axes = plt.subplots(n_rows, 1, figsize=(14, n_rows * 2.1 + 0.5))
    if n_rows == 1:
        axes = [axes]

    fig.patch.set_facecolor("white")
    fig.suptitle(
        f"French presidential election – {year}",
        fontsize=16, fontweight="bold", y=1.01,
    )

    # Poll – Round 1
    draw_stacked_bar(axes[0], _prepare_bar(year_df, "poll_r1"), color_map)
    axes[0].set_title(
        "Pre-electoral poll (Round 1)",
        fontsize=11, fontweight="bold", loc="left", pad=3,
    )

    # Result – Round 1
    draw_stacked_bar(axes[1], _prepare_bar(year_df, "result_r1"), color_map)
    axes[1].set_title(
        "Electoral result (Round 1)",
        fontsize=11, fontweight="bold", loc="left", pad=3,
    )

    # Result – Round 2 (when available)
    if has_r2:
        draw_stacked_bar(axes[2], _prepare_bar(year_df, "result_r2"), color_map)
        axes[2].set_title(
            "Electoral result (Round 2)",
            fontsize=11, fontweight="bold", loc="left", pad=3,
        )

    plt.tight_layout(pad=0.5)

    if save:
        fname = f"fr{year}_support.png"
        fig.savefig(fname, dpi=200, bbox_inches="tight")
        print(f"Saved {fname}")

    plt.show()


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot French presidential election poll vs. results."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="Election years to plot (default: all years in the CSV).",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save each figure as a PNG file.",
    )
    args = parser.parse_args()

    df = load_data()
    color_map = build_color_map(df)
    years = sorted(args.years or df["year"].unique())

    for year in years:
        year_df = df[df["year"] == year].copy()
        if year_df.empty:
            print(f"No data for {year}, skipping.")
            continue
        make_figure(year_df, color_map, year, save=args.save)


if __name__ == "__main__":
    main()

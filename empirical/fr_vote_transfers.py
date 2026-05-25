"""
French presidential elections – Second-round vote transfers
===========================================================
Reads FR-vote_transfers.csv and produces one static alluvial (Sankey)
diagram per election year.

Design principles
-----------------
• Abstention / blank / null excluded; flows renormalised to 100 %
  across the two second-round finalists for each origin party.
• Origin parties coloured with the Spectral colormap in ideological order.
• Flows inherit their origin's colour (variable transparency).
• Node positions are fully fixed:
    left  → origin_order, top-to-bottom
    right → destination_order, centred vertically
• Layout minimises crossings: within each left node flows are stacked
  by destination_order; within each right node incoming flows are stacked
  by origin_order.
• Pure matplotlib — no browser, no interactivity.
• Exports PNG and PDF.

Usage
-----
    python fr_vote_transfers.py                    # all years
    python fr_vote_transfers.py --years 2002 2022  # specific years
    python fr_vote_transfers.py --no-save          # display only
"""

import argparse
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize

# ── Constants ─────────────────────────────────────────────────────────────────

DATA_FILE = "FR-vote_transfers.csv"

ABSTENTION_KEYS = {"abst", "blanc", "nul", "null", "blank", "abstention"}

# ── Data loading & cleaning ────────────────────────────────────────────────────


def load_data(filepath: str = DATA_FILE) -> pd.DataFrame:
    """Load the CSV and normalise French-locale decimal separators."""
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    numeric_cols = (
        "origin_round1_share",
        "raw_flow",
        "flow_value",
        "destination_final_share",
    )
    for col in numeric_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.replace(",", ".", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalise stray values > 1  (e.g. "41,45" should be 0.4145)
    for col in numeric_cols:
        mask = df[col] > 1
        df.loc[mask, col] = df.loc[mask, col] / 100

    return df


# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_abstention(label: str) -> bool:
    """Return True if *label* represents abstention / blank / null."""
    low = str(label).lower()
    return any(k in low for k in ABSTENTION_KEYS)


def _alluvial_band(
    ax,
    x_l: float, y_l_bot: float, y_l_top: float,
    x_r: float, y_r_bot: float, y_r_top: float,
    color, alpha: float = 0.58, n: int = 400,
) -> None:
    """
    Fill a smooth S-curve band connecting two vertical segments.

    Top and bottom edges are cubic Bézier curves with horizontal tangents
    at both ends:
        y(t) = ya·(1−t)²·(1+2t) + yb·t²·(3−2t)   ← Hermite blend
        x(t) = (1−t)³·x_l + 3(1−t)t·x_mid + t³·x_r  ← S-shape in x
    Both edges share the same x(t), so the band is one filled polygon.
    """
    cx = (x_l + x_r) / 2.0
    t = np.linspace(0.0, 1.0, n)

    def bz_x(t):
        return (1 - t) ** 3 * x_l + 3 * (1 - t) * t * cx + t ** 3 * x_r

    def bz_y(ya, yb, t):
        return ya * (1 - t) ** 2 * (1 + 2 * t) + yb * t ** 2 * (3 - 2 * t)

    top_x = bz_x(t)
    top_y = bz_y(y_l_top, y_r_top, t)
    bot_y = bz_y(y_l_bot, y_r_bot, t)

    xs = np.concatenate([top_x, top_x[::-1], [top_x[0]]])
    ys = np.concatenate([top_y, bot_y[::-1], [top_y[0]]])
    ax.fill(xs, ys, color=color, alpha=alpha, linewidth=0, zorder=2)


# ── Main plotting function ────────────────────────────────────────────────────


def plot_transfer_sankey(
    df: pd.DataFrame,
    year: int,
    output_prefix: str,
    save: bool = True,
) -> None:
    """
    Build and export a static alluvial diagram of second-round vote transfers.

    Parameters
    ----------
    df:             Full DataFrame (all election years).
    year:           Election year to plot (e.g. 2002, 2022).
    output_prefix:  File-path prefix; '.png' and '.pdf' are appended.
    save:           Whether to write files to disk.
    """

    # ── 1. Slice to this year ─────────────────────────────────────────────
    raw = df[df["election_year"] == year].copy()
    if raw.empty:
        print(f"[ERROR] No rows for election_year={year}.")
        return

    # ── 2. Extract destination metadata BEFORE removing abstention rows ───
    finalist_rows = raw[~raw["destination"].apply(_is_abstention)]
    dest_meta = (
        finalist_rows[["destination", "destination_order",
                       "destination_final_share"]]
        .drop_duplicates("destination")
        .sort_values("destination_order")
        .set_index("destination")
    )

    # ── 3. Remove abstention rows ─────────────────────────────────────────
    data = raw[~raw["destination"].apply(_is_abstention)].copy()

    # ── 4. Sort origins (ideological) and destinations (display order) ────
    origins = (
        data[["origin_party", "origin_candidate",
              "origin_order", "origin_round1_share"]]
        .drop_duplicates(subset=["origin_party", "origin_candidate"])
        .sort_values("origin_order")
        .reset_index(drop=True)
    )
    destinations = dest_meta.reset_index()
    n_origins = len(origins)
    n_dest = len(destinations)

    # ── 5. Renormalise flows among second-round voters only ───────────────
    #
    # For each origin party:
    #   transfer_share = raw_flow / Σ raw_flow  (finalists only)
    #   flow_value     = origin_round1_share × transfer_share
    #
    renorm_rows = []
    for (party, cand), grp in data.groupby(
            ["origin_party", "origin_candidate"], sort=False):
        r1 = grp["origin_round1_share"].iloc[0]
        total_raw = grp["raw_flow"].sum()
        if total_raw == 0:
            continue
        for _, row in grp.iterrows():
            t_share = row["raw_flow"] / total_raw
            renorm_rows.append({
                "origin_party":    party,
                "origin_candidate": cand,
                "origin_order":    row["origin_order"],
                "r1_share":        r1,
                "destination":     row["destination"],
                "dest_order":      row["destination_order"],
                "raw_flow":        row["raw_flow"],
                "transfer_share":  t_share,
                "flow_value":      r1 * t_share,
            })
    flows_df = pd.DataFrame(renorm_rows)

    total_r1 = origins["origin_round1_share"].sum()

    # ── 6. Spectral colormap — one colour per origin, ideological order ───
    cmap = plt.colormaps["Spectral"]
    norm_col = Normalize(vmin=0, vmax=max(n_origins - 1, 1))

    origin_color: dict = {}   # (party, candidate) → RGBA
    party_color: dict = {}    # party string        → RGBA
    for i, row in origins.iterrows():
        key = (row["origin_party"], row["origin_candidate"])
        rgba = cmap(norm_col(i))
        origin_color[key] = rgba
        party_color[row["origin_party"]] = rgba

    # ── 7. Layout geometry ────────────────────────────────────────────────
    TOTAL_H = 1.0
    NODE_GAP = max(0.007, min(0.030, 0.20 / max(n_origins - 1, 1)))  # adaptive
    RIGHT_GAP = 0.09
    NODE_HALF = 0.013
    X_LEFT = 0.22
    X_RIGHT = 0.76

    left_avail = TOTAL_H - (n_origins - 1) * NODE_GAP
    SCALE = left_avail / total_r1

    # ── 8. Left node positions (top → bottom, ideological order) ─────────
    left_nodes: dict = {}
    y = TOTAL_H
    for _, row in origins.iterrows():
        key = (row["origin_party"], row["origin_candidate"])
        h = row["origin_round1_share"] * SCALE
        left_nodes[key] = dict(
            party=row["origin_party"],
            candidate=row["origin_candidate"],
            r1_share=row["origin_round1_share"],
            y_top=y,
            y_bot=y - h,
            height=h,
        )
        y -= h + NODE_GAP

    # ── 9. Right node positions (centred, same height scale) ──────────────
    dest_flow_totals = flows_df.groupby("destination")["flow_value"].sum()
    right_bar_total = total_r1 * SCALE
    right_gap_total = (n_dest - 1) * RIGHT_GAP
    right_span = right_bar_total + right_gap_total
    right_y_start = TOTAL_H / 2.0 + right_span / 2.0

    right_nodes: dict = {}
    y = right_y_start
    for _, row in destinations.iterrows():
        dest = row["destination"]
        h = dest_flow_totals.get(dest, 0.0) * SCALE
        right_nodes[dest] = dict(y_top=y, y_bot=y - h, height=h)
        y -= h + RIGHT_GAP

    # ── 10. Flow-band attachment positions ────────────────────────────────
    #
    # Left side:  within each origin node, bands ordered by dest_order
    #             → flow to the top-ranked finalist exits from the top.
    # Right side: within each finalist node, bands ordered by origin_order
    #             → most left-wing origin arrives at the top.
    #
    # Iterating outer=destinations, inner=origins satisfies both rules.
    #
    left_fill = {key: nd["y_top"] for key, nd in left_nodes.items()}
    right_fill = {dest: nd["y_top"] for dest, nd in right_nodes.items()}

    flow_bands = []
    for dest_row in destinations.itertuples():
        dest = dest_row.destination
        dest_data = (
            flows_df[flows_df["destination"] == dest]
            .sort_values("origin_order")
        )
        for _, frow in dest_data.iterrows():
            key = (frow["origin_party"], frow["origin_candidate"])
            fh = frow["flow_value"] * SCALE

            if fh < 1e-10:  # skip genuinely zero flows (e.g. PS→FN 2002)
                continue

            ly_top = left_fill[key]
            ly_bot = ly_top - fh
            ry_top = right_fill[dest]
            ry_bot = ry_top - fh
            left_fill[key] = ly_bot
            right_fill[dest] = ry_bot

            flow_bands.append(dict(
                key=key,
                destination=dest,
                flow_value=frow["flow_value"],
                transfer_share=frow["transfer_share"],
                raw_flow=frow["raw_flow"],
                color=origin_color[key],
                ly_bot=ly_bot, ly_top=ly_top,
                ry_bot=ry_bot, ry_top=ry_top,
            ))

    # ── 11. Figure ────────────────────────────────────────────────────────
    fig_h = max(7.0, min(12.0, 3.5 + n_origins * 0.55))
    fig = plt.figure(figsize=(14, fig_h), facecolor="white")
    ax = fig.add_axes([0.01, 0.03, 0.98, 0.88])
    ax.set_facecolor("white")
    ax.axis("off")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(-0.06, 1.06)

    # ── 12. Draw flow bands ───────────────────────────────────────────────
    ALPHA_MIN = 0.22
    ALPHA_MAX = 0.62
    TINY_CUTOFF = 0.004

    for f in flow_bands:
        alpha = ALPHA_MIN if f["flow_value"] < TINY_CUTOFF else ALPHA_MAX
        _alluvial_band(
            ax,
            x_l=X_LEFT + NODE_HALF, y_l_bot=f["ly_bot"], y_l_top=f["ly_top"],
            x_r=X_RIGHT - NODE_HALF, y_r_bot=f["ry_bot"], y_r_top=f["ry_top"],
            color=f["color"], alpha=alpha,
        )

    # ── 13. Left node rectangles + labels ────────────────────────────────
    for key, nd in left_nodes.items():
        color = origin_color[key]
        ax.add_patch(mpatches.Rectangle(
            (X_LEFT - NODE_HALF, nd["y_bot"]),
            2 * NODE_HALF, nd["height"],
            facecolor=color, edgecolor="white", linewidth=0.8, zorder=4,
        ))
        label = (f"{nd['party']}  {nd['candidate']}  "
                 f"{nd['r1_share'] * 100:.1f}%")
        ax.text(
            X_LEFT - NODE_HALF - 0.016,
            nd["y_bot"] + nd["height"] / 2,
            label,
            ha="right", va="center",
            fontsize=8.8, fontweight="bold", color="#111111",
        )

    # ── 14. Right node rectangles + labels ───────────────────────────────
    party_to_cand = {row["origin_party"]: row["origin_candidate"]
                     for _, row in origins.iterrows()}

    for _, dest_row in destinations.iterrows():
        dest = dest_row["destination"]
        nd = right_nodes[dest]
        dest_color = party_color.get(dest, "#555555")
        final_pct = dest_meta.loc[dest, "destination_final_share"] * 100

        ax.add_patch(mpatches.Rectangle(
            (X_RIGHT - NODE_HALF, nd["y_bot"]),
            2 * NODE_HALF, nd["height"],
            facecolor=dest_color, edgecolor="white", linewidth=0.8, zorder=4,
        ))
        cand = party_to_cand.get(dest, "")
        label = f"{dest}  {cand}  {final_pct:.1f}%"
        ax.text(
            X_RIGHT + NODE_HALF + 0.016,
            nd["y_bot"] + nd["height"] / 2,
            label,
            ha="left", va="center",
            fontsize=10, fontweight="bold", color="#111111",
        )

    # ── 15. Ideological-order annotation ─────────────────────────────────
    ax.text(
        X_LEFT - NODE_HALF - 0.016, 1.025,
        "Ideological order\ntop = left,  bottom = right",
        ha="right", va="bottom",
        fontsize=7.2, color="#777777", style="italic", linespacing=1.4,
    )

    # ── 16. Title and subtitle ────────────────────────────────────────────
    fig.text(
        0.5, 0.995,
        f"Second-round vote transfers, {year}",
        ha="center", va="top",
        fontsize=15, fontweight="bold", color="#111111",
    )
    fig.text(
        0.5, 0.958,
        ("Flows are normalised among voters who chose one of the two "
         "second-round finalists.  First-round parties are ordered ideologically."),
        ha="center", va="top",
        fontsize=8.5, color="#333333", style="italic",
    )

    # ── 17. Export ────────────────────────────────────────────────────────
    if save:
        for ext in ("png", "pdf"):
            path = f"{output_prefix}.{ext}"
            try:
                fig.savefig(path, dpi=200, bbox_inches="tight",
                            facecolor="white")
                print(f"[OK]  {ext.upper()} saved → {path}")
            except Exception as exc:
                print(f"[WARN] {ext.upper()} failed: {exc}")

    plt.show()
    plt.close(fig)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot French presidential election second-round vote transfers."
    )
    parser.add_argument(
        "--years", nargs="+", type=int, default=None,
        help="Election years to plot (default: all years in the CSV).",
    )
    parser.add_argument(
        "--no-save", dest="save", action="store_false",
        help="Display figures without saving PNG/PDF files.",
    )
    args = parser.parse_args()

    df = load_data()

    _required = {
        "election_year", "origin_party", "origin_candidate",
        "origin_order", "origin_round1_share",
        "destination", "destination_order", "raw_flow",
        "flow_value", "destination_final_share",
    }
    missing = _required - set(df.columns)
    if missing:
        print(f"[ERROR] Missing columns in '{DATA_FILE}': {missing}")
        sys.exit(1)

    years = sorted(args.years or df["election_year"].unique())

    for year in years:
        plot_transfer_sankey(
            df,
            year=year,
            output_prefix=f"fr{year}_transfers",
            save=args.save,
        )


if __name__ == "__main__":
    main()

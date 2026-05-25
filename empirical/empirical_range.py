"""
empirical_range.py
------------------
Produces a single figure comparing poll-to-result ΔCENP across French
presidential elections, with model mean and p05–p95 range overlaid.

Reads:
    FR-electoral_data.csv              empirical election data
                                       (columns: election_year, party,
                                       ideological_order, pre_electoral_share,
                                       electoral_share_R1, electoral_share_R2)
    saltelli_results_K6.csv            }
    saltelli_results_K8.csv            } Saltelli output (for model range)
    saltelli_results_K9.csv            }

If Saltelli CSVs are not found, the model range band is omitted gracefully.

Output:
    empirical_range_cenp.png
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family":      "serif",
    "font.size":        9,
    "axes.titlesize":   10,
    "axes.titleweight": "bold",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.grid":        True,
    "grid.color":       "#e0e0e0",
    "grid.linewidth":   0.5,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
})

SPECTRAL = plt.cm.Spectral


# =========================================================================== #
#  MEASURE HELPERS                                                             #
# =========================================================================== #


def enp(shares) -> float:
    s = np.asarray(shares, dtype=float)
    s = s / s.sum()
    return 1.0 / (s ** 2).sum()


def cenp(shares, K: int) -> float:
    return (K - enp(shares)) / (K - 1)


def delta_cenp(poll, result) -> float:
    K = len(poll)
    return cenp(result, K) - cenp(poll, K)


# =========================================================================== #
#  DATA LOADING                                                                #
# =========================================================================== #


def load_empirical(
        filepath: str = "FR-electoral_data.csv",
) -> pd.DataFrame:
    """
    Load empirical election data and compute ΔCENP per election year.

    Parses French-locale comma decimals and normalises any stray percentage
    values > 1 (e.g. the RN 2022 R2 entry stored as 41.45 → 0.4145).
    Only pre_electoral_share (poll) and electoral_share_R1 (result) are used
    to compute ΔCENP; the R2 column is ignored here.

    Returns a DataFrame with columns: year, delta_cenp.
    """
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    for col in ("pre_electoral_share", "electoral_share_R1"):
        df[col] = (
            df[col]
            .astype(str).str.strip()
            .str.replace(",", ".", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")
        mask = df[col] > 1
        df.loc[mask, col] = df.loc[mask, col] / 100

    rows = []
    for year, group in df.groupby("election_year"):
        group = group.dropna(subset=["pre_electoral_share", "electoral_share_R1"])
        dc = delta_cenp(
            group["pre_electoral_share"].values,
            group["electoral_share_R1"].values,
        )
        rows.append({"year": int(year), "delta_cenp": round(dc, 4)})

    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def load_model_range(saltelli_ks: tuple = (6, 8, 9)) -> dict:
    """
    Load Saltelli output CSVs and compute the model ΔCENP range.

    Returns a dict with keys mean, p05, p95, or an empty dict if no
    Saltelli files are found.
    """
    dfs = []
    for k in saltelli_ks:
        fname = f"saltelli_results_K{k}.csv"
        try:
            dfs.append(pd.read_csv(fname))
            print(f"Loaded {fname} ({len(dfs[-1])} rows)")
        except FileNotFoundError:
            print(f"{fname} not found — skipping")

    if not dfs:
        print("No Saltelli files found — model range band will be omitted.")
        return {}

    sal_vals = pd.concat(dfs, ignore_index=True)["delta_cenp"].dropna()
    result = {
        "mean": float(sal_vals.mean()),
        "p05":  float(sal_vals.quantile(0.05)),
        "p95":  float(sal_vals.quantile(0.95)),
    }
    print(f"Model ΔCENP: mean={result['mean']:.4f}, "
          f"p05={result['p05']:.4f}, p95={result['p95']:.4f}")
    return result


# =========================================================================== #
#  FIGURE                                                                      #
# =========================================================================== #


def plot_figure(
        emp_df: pd.DataFrame,
        model_range: dict,
        save_path: str = "empirical_range_cenp.png",
) -> plt.Figure:
    """
    Plot empirical ΔCENP values with model mean and p05–p95 band overlaid.

    Parameters
    ----------
    emp_df      : output of load_empirical()
    model_range : output of load_model_range(); empty dict → no band
    save_path   : output file path
    """
    years   = emp_df["year"].values
    dc_vals = emp_df["delta_cenp"].values

    fig, ax = plt.subplots(figsize=(5.8, 3.6))

    # Model range band and mean line
    if model_range:
        ax.axhspan(
            model_range["p05"], model_range["p95"],
            facecolor=SPECTRAL(0.32), alpha=0.2,
            edgecolor="none", linewidth=0, zorder=0,
            label="Model range",
        )
        ax.axhline(
            model_range["mean"],
            color=SPECTRAL(0.32), linewidth=1.2,
            linestyle="--", alpha=0.85, zorder=1,
            label="Model mean",
        )

    # Zero reference line
    ax.axhline(0, color="0.15", linewidth=0.4, zorder=1)

    # Empirical lollipops and value labels
    ax.vlines(years, 0, dc_vals, color="0.15", linewidth=0.9,
              zorder=2, label="_nolegend_")
    ax.scatter(years, dc_vals, color="0.05", s=24, zorder=3,
               label="Empirical values")

    for yr, y in zip(years, dc_vals):
        offset, va = (0.006, "bottom") if y >= 0 else (-0.006, "top")
        ax.text(yr, y + offset, f"{y:.3f}",
                ha="center", va=va, fontsize=7)

    ax.set_xticks(years)
    ax.set_ylabel(r"$\Delta C_{\mathrm{ENP}}$ (poll $\to$ result)")
    ax.set_ylim(-0.13, 0.13)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="0.88", linewidth=0.6)
    ax.grid(axis="x", visible=False)
    ax.legend(
        frameon=False, fontsize=7, loc="lower right",
        handlelength=1.8, handletextpad=0.6,
        labelspacing=0.5, markerscale=0.75,
    )

    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    print(f"Saved: {save_path}")
    return fig


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #


def main() -> None:
    emp_df      = load_empirical()
    model_range = load_model_range()

    print("\nEmpirical ΔCENP:")
    print(emp_df.to_string(index=False))

    plot_figure(emp_df, model_range)


if __name__ == "__main__":
    main()

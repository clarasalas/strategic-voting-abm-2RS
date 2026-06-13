"""
behavioral_compare.py
----------------------
Is the achievable coordination gain ΔCENP different between 2002 and 2022?

Reads the per-draw behavioral sweeps (one row per parameter draw, holding each
year's real electoral structure fixed) and tests whether the distribution of
ΔCENP differs between the two years. Each draw is summarized by its mean ΔCENP
over repeats — the same quantity plotted by behavioral_sweep_figure.py.

Two complementary tests are reported:

    Mann–Whitney U   non-parametric; no normality assumption. Effect size:
                     rank-biserial correlation and the common-language effect
                     size CLES = P(ΔCENP_2002 > ΔCENP_2022).
    Welch's t-test   difference of means with unequal variances. Effect size:
                     Cohen's d (pooled SD).

Reads
-----
    data/behavioral_sweep_2002.csv   (column: mean_delta_cenp)
    data/behavioral_sweep_2022.csv

Writes
------
    data/behavioral_compare_2002_2022.csv   tidy one-row-per-test summary

Usage
-----
    python analysis/empirical/behavioral_compare.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DATA_DIR = REPO / "data"

YEARS = (2002, 2022)
VALUE_COL = "mean_delta_cenp"


def load_delta_cenp(year: int) -> np.ndarray:
    """Per-draw mean ΔCENP for a year, dropping any missing values."""
    df = pd.read_csv(DATA_DIR / f"behavioral_sweep_{year}.csv")
    return df[VALUE_COL].to_numpy(dtype=float)


def describe(x: np.ndarray) -> dict:
    return {
        "n": x.size,
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "std": float(np.std(x, ddof=1)),
    }


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d with pooled standard deviation."""
    na, nb = a.size, b.size
    sp2 = ((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2)
    return (np.mean(a) - np.mean(b)) / np.sqrt(sp2)


def main() -> None:
    a = load_delta_cenp(YEARS[0])   # 2002
    b = load_delta_cenp(YEARS[1])   # 2022

    da, db = describe(a), describe(b)
    print("=" * 64)
    print(f"ΔCENP per-draw distributions  ({VALUE_COL})")
    print("=" * 64)
    for year, d in zip(YEARS, (da, db)):
        print(f"  {year}: n={d['n']:4d}  mean={d['mean']:+.4f}  "
              f"median={d['median']:+.4f}  sd={d['std']:.4f}")

    # Mann–Whitney U (two-sided). U reported for the first sample (2002).
    u_stat, p_mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    n1, n2 = a.size, b.size
    cles = u_stat / (n1 * n2)              # P(random 2002 draw > random 2022 draw)
    rank_biserial = 2.0 * cles - 1.0       # (U1 - U2) / (n1 n2)

    # Welch's t-test (two-sided, unequal variances).
    t_stat, p_t = stats.ttest_ind(a, b, equal_var=False)
    d = cohens_d(a, b)

    print("\n" + "-" * 64)
    print("Mann–Whitney U (non-parametric)")
    print("-" * 64)
    print(f"  U = {u_stat:.1f}   p = {p_mw:.3e}")
    print(f"  CLES P(2002 > 2022) = {cles:.3f}   rank-biserial r = {rank_biserial:+.3f}")

    print("\n" + "-" * 64)
    print("Welch's t-test (unequal variances)")
    print("-" * 64)
    print(f"  t = {t_stat:.3f}   p = {p_t:.3e}")
    print(f"  mean diff (2002 − 2022) = {da['mean'] - db['mean']:+.4f}   "
          f"Cohen's d = {d:+.3f}")

    # Tidy summary, one row per test.
    out = pd.DataFrame([
        {
            "test": "mann_whitney_u", "statistic": u_stat, "p_value": p_mw,
            "effect_size_name": "rank_biserial", "effect_size": rank_biserial,
            "cles_2002_gt_2022": cles,
            "n_2002": n1, "n_2022": n2,
            "mean_2002": da["mean"], "mean_2022": db["mean"],
        },
        {
            "test": "welch_t", "statistic": t_stat, "p_value": p_t,
            "effect_size_name": "cohens_d", "effect_size": d,
            "cles_2002_gt_2022": np.nan,
            "n_2002": n1, "n_2022": n2,
            "mean_2002": da["mean"], "mean_2022": db["mean"],
        },
    ])
    out_path = DATA_DIR / "behavioral_compare_2002_2022.csv"
    out.to_csv(out_path, index=False)
    print(f"\n[compare] wrote -> {out_path}")


if __name__ == "__main__":
    main()

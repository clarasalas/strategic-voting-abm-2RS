"""
behavioral_compare.py
----------------------
Is the achievable coordination gain ΔCENP different between 2002 and 2022?

Reads the per-draw behavioral sweeps (one row per parameter draw, holding each
year's real electoral structure fixed) and tests whether the distribution of
ΔCENP differs between the two years. Each draw is summarized by its mean ΔCENP
over repeats — the same quantity plotted by behavioral_sweep_figure.py.

Two metrics are compared:

    raw ΔCENP        the coordination gain as-is.
    relative gain    ΔCENP / (1 − CENP(s⁰)) — the fraction of the *available*
                     headroom toward full coordination that got closed. This
                     controls for initial fragmentation: the baseline poll s⁰
                     is fixed per year, so its CENP(s⁰) is a single constant per
                     year (0.572 for 2002, 0.557 for 2022) and is perfectly
                     confounded with `year` — it cannot be used as a regression
                     covariate. Normalizing by headroom is the meaningful way to
                     put the two years on a comparable starting footing.

For each metric, two complementary tests are reported:

    Mann–Whitney U   non-parametric; no normality assumption. Effect size:
                     rank-biserial correlation and the common-language effect
                     size CLES = P(metric_2002 > metric_2022).
    Welch's t-test   difference of means with unequal variances. Effect size:
                     Cohen's d (pooled SD).

Reads
-----
    data/behavioral_sweep_2002.csv   (column: mean_delta_cenp)
    data/behavioral_sweep_2022.csv
    data/behavioral_targets.csv      (column: cenp_s0, per year)

Writes
------
    data/behavioral_compare_2002_2022.csv   tidy one-row-per-(metric, test)

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


def load_baseline_cenp() -> dict:
    """Per-year baseline CENP(s⁰) from the behavioral targets table."""
    df = pd.read_csv(DATA_DIR / "behavioral_targets.csv")
    return {int(r["year"]): float(r["cenp_s0"]) for _, r in df.iterrows()}


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


def compare(a: np.ndarray, b: np.ndarray, metric: str) -> list:
    """Print and return both tests comparing 2002 (a) vs 2022 (b) for `metric`."""
    da, db = describe(a), describe(b)
    print("=" * 64)
    print(f"{metric}: per-draw distributions")
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

    print("  Mann–Whitney U : "
          f"U={u_stat:.1f}  p={p_mw:.3e}  "
          f"CLES(2002>2022)={cles:.3f}  rank-biserial r={rank_biserial:+.3f}")
    print("  Welch's t      : "
          f"t={t_stat:.3f}  p={p_t:.3e}  "
          f"mean diff(2002−2022)={da['mean'] - db['mean']:+.4f}  Cohen's d={d:+.3f}")

    return [
        {
            "metric": metric, "test": "mann_whitney_u",
            "statistic": u_stat, "p_value": p_mw,
            "effect_size_name": "rank_biserial", "effect_size": rank_biserial,
            "cles_2002_gt_2022": cles,
            "n_2002": n1, "n_2022": n2,
            "mean_2002": da["mean"], "mean_2022": db["mean"],
        },
        {
            "metric": metric, "test": "welch_t",
            "statistic": t_stat, "p_value": p_t,
            "effect_size_name": "cohens_d", "effect_size": d,
            "cles_2002_gt_2022": np.nan,
            "n_2002": n1, "n_2022": n2,
            "mean_2002": da["mean"], "mean_2022": db["mean"],
        },
    ]


def main() -> None:
    raw = {y: load_delta_cenp(y) for y in YEARS}
    cenp_s0 = load_baseline_cenp()

    # Relative gain controls for initial fragmentation: fraction of the headroom
    # (1 − CENP(s⁰)) toward full coordination that each draw closes.
    rel = {y: raw[y] / (1.0 - cenp_s0[y]) for y in YEARS}

    print("Baseline CENP(s⁰) per year (fixed across draws):")
    for y in YEARS:
        print(f"  {y}: CENP(s⁰)={cenp_s0[y]:.4f}  headroom (1−CENP)={1 - cenp_s0[y]:.4f}")
    print()

    rows = []
    rows += compare(raw[YEARS[0]], raw[YEARS[1]], "raw_delta_cenp")
    print()
    rows += compare(rel[YEARS[0]], rel[YEARS[1]], "relative_gain_headroom")

    out_path = DATA_DIR / "behavioral_compare_2002_2022.csv"
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\n[compare] wrote -> {out_path}")


if __name__ == "__main__":
    main()

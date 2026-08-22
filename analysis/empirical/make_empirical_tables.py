"""
Compact, committed result tables for the corrected empirical rerun.

Everything here is *derived* from the raw empirical outputs under ``data/``.
The raw files stay uncommitted (they are bulky and regenerate from the
runners); these summaries are what a reader actually needs, and they are small
enough to read in a diff.

Every table is deterministic: fixed row order, fixed column order, no
timestamps, no run-dependent metadata.  Re-running this script on unchanged
inputs rewrites byte-identical files.

Usage:
    python analysis/empirical/make_empirical_tables.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

# pandas' default float parser is fast but not correctly rounded: it can return
# a double one ulp from the value the text denotes, which makes regeneration
# depend on the platform.  The correctly rounded parser costs a little speed and
# buys byte-identical tables anywhere.  (Same reasoning, and the same constant,
# as behavioral_sweep.finalise_output.)
CSV_READ_KW = dict(float_precision="round_trip")


def _read(path):
    """Read an input CSV exactly, and refuse a corrupt one.

    The finiteness check is on the way IN, not only on the way out. Every
    summary here goes through a pandas aggregation, and those skip NaN by
    default -- so a NaN in the raw output would silently become a healthy
    looking mean over fewer rows, and the output guard would never fire.
    Catching it at the source is the only place it is visible.
    """
    df = pd.read_csv(path, encoding="utf-8", **CSV_READ_KW)
    num = df.select_dtypes(include=[np.number])
    if len(num.columns) and not np.isfinite(num.to_numpy()).all():
        bad = [c for c in num.columns if not np.isfinite(num[c].to_numpy()).all()]
        raise AssertionError(
            f"{Path(path).name}: NaN or non-finite value(s) in column(s) {bad}. "
            f"Refusing to build a summary table from corrupt input.")
    return df


ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = ROOT / "results" / "tables"

YEARS = (2002, 2022)
K_BY_YEAR = {2002: 15, 2022: 12}

# Specification label -> filename infix used by the runners.  ``nearest`` is the
# main replay and carries no infix.
SPECS = {
    "nearest": "",
    "prob_signal": "_prob_signal",
    "prob_prior": "_prob_prior",
    "prob_signal_mu0": "_prob_signal_mu0",
}

# Reported outcome columns, in the order they appear in every table.
METRICS = [
    "rmse", "mae",
    "top2_acc", "top3_acc", "top4_acc",
    "enp_sincere", "enp_final", "delta_enp", "delta_cenp",
    "cliff_magnitude", "cliff_ratio",
    "trigger_rate", "switching_rate", "conditional_switching_rate",
]


def _summarise(df: pd.DataFrame, key: dict, metrics=METRICS) -> list:
    """One row per metric: mean / sd / p05 / p50 / p95.

    Long rather than wide on purpose.  A row per metric stays readable in a
    diff; the wide form would be ~80 columns and unreadable.
    """
    rows = []
    for m in metrics:
        if m not in df.columns:
            continue
        s = df[m]
        rows.append({
            **key,
            "metric": m,
            "mean": s.mean(),
            "sd": s.std(),
            "p05": s.quantile(0.05),
            "p50": s.quantile(0.50),
            "p95": s.quantile(0.95),
        })
    return rows


# --------------------------------------------------------------------------- #
# 1. Empirical replay summary, by year and specification
# --------------------------------------------------------------------------- #
def replay_summary() -> pd.DataFrame:
    rows = []
    for spec, infix in SPECS.items():
        for year in YEARS:
            df = _read(DATA / f"empirical_runs{infix}_{year}.csv")
            key = {
                "specification": spec,
                "year": year,
                "K": K_BY_YEAR[year],
                "n_draws": len(df),
                "tau_absolute_min": df["tau_absolute"].min(),
                "tau_absolute_max": df["tau_absolute"].max(),
            }
            rows.extend(_summarise(df, key))
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["specification", "year", "metric"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 2. Robustness summary, by year and perturbation variant
# --------------------------------------------------------------------------- #
def robustness_summary() -> pd.DataFrame:
    rows = []
    for year in YEARS:
        df = _read(DATA / f"empirical_robustness_{year}.csv")
        for variant, g in df.groupby("variant", sort=True):
            key = {
                "variant": variant,
                "year": year,
                "K": K_BY_YEAR[year],
                "n_draws": len(g),
                "tau_absolute_min": g["tau_absolute"].min(),
                "tau_absolute_max": g["tau_absolute"].max(),
            }
            rows.extend(_summarise(g, key))
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["variant", "year", "metric"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 3. Activation / diagnostic summary
# --------------------------------------------------------------------------- #
def activation_summary() -> pd.DataFrame:
    """Fraction of draws whose trigger and switching rates clear each threshold.

    Computed here directly from the run files rather than read from the
    diagnostics sidecars, so the same definition applies to every
    specification including the main replay.
    """
    rows = []
    for spec, infix in SPECS.items():
        for year in YEARS:
            df = _read(DATA / f"empirical_runs{infix}_{year}.csv")
            row = {
                "specification": spec,
                "year": year,
                "K": K_BY_YEAR[year],
                "n_draws": len(df),
                "trigger_rate_mean": df["trigger_rate"].mean(),
                "switching_rate_mean": df["switching_rate"].mean(),
                "conditional_switching_rate_mean":
                    df["conditional_switching_rate"].mean(),
            }
            for thr in (0.01, 0.05, 0.10):
                tag = f"gt_{int(round(thr * 100))}pct"
                row[f"frac_trigger_{tag}"] = (df["trigger_rate"] > thr).mean()
                row[f"frac_switch_{tag}"] = (df["switching_rate"] > thr).mean()
            rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(["specification", "year"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 4. Behavioural-sweep quantiles versus observed ΔCENP
# --------------------------------------------------------------------------- #
def sweep_quantiles() -> pd.DataFrame:
    """Sweep ΔCENP distribution against the observed target.

    Both sides use the exogenous opening-poll baseline, ΔCENP = CENP(final) −
    CENP(s⁰).  This is *not* the replay's ΔCENP, which is measured against the
    model's own iteration-0 sincere shares.
    """
    targets = _read(DATA / "behavioral_targets.csv").set_index("year")
    qs = [0.0, 0.05, 0.25, 0.50, 0.75, 0.95, 1.0]
    rows = []
    for year in YEARS:
        df = _read(DATA / f"behavioral_sweep_{year}.csv")
        s = df["mean_delta_cenp"]
        obs = float(targets.loc[year, "delta_cenp_real"])
        row = {
            "year": year,
            "K": K_BY_YEAR[year],
            "n_draws": len(df),
            "n_repeats": int(df["n_repeats"].iloc[0]),
            "baseline": "exogenous_poll_s0",
            "observed_delta_cenp": obs,
            "cenp_s0": float(targets.loc[year, "cenp_s0"]),
            "cenp_real": float(targets.loc[year, "cenp_real"]),
        }
        for q in qs:
            row[f"sim_q{int(round(q * 100)):03d}"] = s.quantile(q)
        row["sim_mean"] = s.mean()
        row["sim_sd"] = s.std()
        row["observed_inside_range"] = bool(s.min() <= obs <= s.max())
        row["frac_draws_below_observed"] = float((s < obs).mean())
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values("year").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 5. 2002-versus-2022 effect sizes
# --------------------------------------------------------------------------- #
def year_contrast() -> pd.DataFrame:
    """Between-year contrast for each metric, per specification.

    ``cohens_d`` uses the pooled within-year standard deviation.  Metrics that
    are constant in both years (the top-k set accuracies are identically zero)
    have no defined effect size; they are reported with an explicit sentinel
    rather than NaN so the table stays finite.
    """
    rows = []
    for spec, infix in SPECS.items():
        a = _read(DATA / f"empirical_runs{infix}_2002.csv")
        b = _read(DATA / f"empirical_runs{infix}_2022.csv")
        for m in METRICS:
            sd_pooled = np.sqrt((a[m].var() + b[m].var()) / 2.0)
            defined = bool(sd_pooled > 0)
            rows.append({
                "specification": spec,
                "metric": m,
                "mean_2002": a[m].mean(),
                "mean_2022": b[m].mean(),
                "diff_2022_minus_2002": b[m].mean() - a[m].mean(),
                "sd_pooled": sd_pooled,
                "cohens_d": (b[m].mean() - a[m].mean()) / sd_pooled
                            if defined else 0.0,
                "effect_size_defined": defined,
                "n_2002": len(a),
                "n_2022": len(b),
            })
    out = pd.DataFrame(rows)
    return out.sort_values(["specification", "metric"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 6. Candidate-level fit
# --------------------------------------------------------------------------- #
def candidate_fit() -> pd.DataFrame:
    """Per-candidate simulated versus actual share, for every specification."""
    rows = []
    for spec, infix in SPECS.items():
        for year in YEARS:
            df = _read(DATA / f"empirical_candidate_shares{infix}_{year}.csv")
            for _, r in df.iterrows():
                rows.append({
                    "specification": spec,
                    "year": year,
                    "K": K_BY_YEAR[year],
                    "party": r["party"],
                    "block": r["block"],
                    "position": r["position"],
                    "actual_share": r["actual_share"],
                    "first_signal_share": r["first_signal_share"],
                    "mean_final_share": r["mean_final_share"],
                    "error_final_minus_actual":
                        r["mean_final_share"] - r["actual_share"],
                    "p05_final_share": r["p05_final_share"],
                    "p95_final_share": r["p95_final_share"],
                    "prob_top2": r["prob_top2"],
                    "prob_top3": r["prob_top3"],
                })
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["specification", "year", "party"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
TABLES = {
    "empirical_replay_summary.csv": replay_summary,
    "empirical_robustness_summary.csv": robustness_summary,
    "empirical_activation_summary.csv": activation_summary,
    "behavioral_sweep_quantiles.csv": sweep_quantiles,
    "empirical_year_contrast.csv": year_contrast,
    "empirical_candidate_fit.csv": candidate_fit,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in TABLES.items():
        df = fn()
        # Guard rails: the tables are cited, so they must not carry holes.
        assert not df.isna().any().any(), f"{name}: NaN present"
        num = df.select_dtypes(include=[np.number])
        assert np.isfinite(num.to_numpy()).all(), f"{name}: non-finite present"
        df.to_csv(OUT / name, index=False)
        print(f"wrote {name:<38} {df.shape[0]:>3} rows x {df.shape[1]:>3} cols")


if __name__ == "__main__":
    main()

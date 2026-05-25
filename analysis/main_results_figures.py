"""
main_results_figures.py
-----------------------
Generate the four main result figures.

Figures
-------
1.  c × τ̂ heatmap for trigger rate.
2.  Two-panel sweep: trigger rate and conditional switching varying c.
3.  Dynamic trajectory: ΔCENP across iterations for three width regimes.
4.  Empirical validation: poll-to-result ΔCENP across French presidential
    elections, with model mean and p05–p95 range overlaid.

Fixed baseline parameters
-------------------------
    K       =  8      even party system with central structure
    M       =  2      French two-round institutional rule
    N       =  2000   electors
    T_max   =  25     convergence ceiling
    theta   =  1.0    neutral signal, no distortion
    rho_s   =  100    moderate signal precision
    rho_pi  =  100    moderate prior precision
    alpha   =  0.0    full signal reliance (cognitive neutral baseline)
    mu      =  0.1    low expressive cost
    eps     =  0.1    uniform floor weight
    xi      =  0.0    symmetric electorate

Data sources  (Figure 4)
------------------------
    FR-electoral_data.csv              empirical election data
    saltelli_results_K{6,8,9}.csv      Saltelli output (model range)
    If Saltelli CSVs are not found, the model range band is omitted.

Run cost
--------
    Figure 1 (heatmap)    :  10×10 grid × N_REPS runs
    Figure 2 (c sweep)    :  10 c values × N_REPS runs
    Figure 3 (trajectory) :  3 regimes × N_REPS_TRAJ runs
    Figure 4 (empirical)  :  reads from disk only

Outputs
-------
    fig1_heatmap_trigger.png / _raw.csv
    fig2_trigger_condswitch_c.png / _raw.csv
    fig3_trajectory_deltacenp.png
    fig4_empirical_range_cenp.png

Usage
-----
    python main_results_figures.py

    Reduce N_REPS to 50 for a quick test run.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

import functions
from model import run_simulation

# =========================================================================== #
#  GLOBAL STYLE                                                                #
# =========================================================================== #

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linewidth": 0.5,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

SPECTRAL = plt.cm.Spectral

# =========================================================================== #
#  FIXED BASELINE                                                              #
# =========================================================================== #

K       = 8
M       = 2
N       = 2000
TMAX    = 25
THETA   = 1.0
RHO_S   = 100.0
RHO_PI  = 100.0
ALPHA   = 0.0
MU      = 0.1
EPS_F   = 0.1     # floor weight
XI      = 0.0
N_MODES = 1

# Reps per condition — reduce to 50 for a quick test run
N_REPS  = 100

# =========================================================================== #
#  HELPERS                                                                     #
# =========================================================================== #


def zone_length(K: int) -> float:
    return 2.0 / K


def tau_abs(tau_hat: float, K: int) -> float:
    return tau_hat * zone_length(K)


def enp(shares) -> float:
    s = np.asarray(shares, dtype=float)
    s = s / s.sum()
    return 1.0 / (s ** 2).sum()


def cenp(shares, K: int) -> float:
    return (K - enp(shares)) / (K - 1)


def delta_cenp(poll, result) -> float:
    K = len(poll)
    return cenp(result, K) - cenp(poll, K)


def run_batch(params_list: list, collect_history: bool = False) -> list:
    """
    Run a list of parameter dicts and return a list of result dicts.
    Each params dict must contain keys: c, tau_hat, K.
    If collect_history=True, also returns iteration-level ΔCENP trajectories.
    """
    results = []
    for i, p in enumerate(params_list):
        if i % 200 == 0:
            print(f"    run {i}/{len(params_list)}...")
        try:
            res = run_simulation(
                K=p["K"],
                n_modes=N_MODES,
                width_factor=p["c"],
                mode_position=XI,
                floor_weight=EPS_F,
                theta=THETA,
                rho=RHO_S,
                rho_pi=RHO_PI,
                n_electors=N,
                tau=tau_abs(p["tau_hat"], p["K"]),
                mu=MU,
                alpha_prior=ALPHA,
                K_runoff=M,
                max_iterations=TMAX,
                seed=i,
                verbose=False,
                collect_diagnostics=True,
            )
            out = {
                "c":          p["c"],
                "tau_hat":    p["tau_hat"],
                "K":          p["K"],
                "trigger":    res["diagnostics"]["trigger_rate_final"],
                "cond_sw":    res["diagnostics"][
                    "conditional_switching_given_triggered"],
                "delta_cenp": functions.coordination_measures(
                    np.array(res["sincere_shares"]),
                    np.array(res["final_shares"]))["delta_cenp"],
            }
            if collect_history:
                n_elec = sum(res["history"][0])
                sincere = np.array(res["history"][0]) / n_elec
                traj = [
                    functions.coordination_measures(
                        sincere, np.array(h) / n_elec)["delta_cenp"]
                    for h in res["history"][1:]
                ]
                out["trajectory"] = traj
            results.append(out)
        except Exception as e:
            print(f"    WARNING: run {i} failed ({e})")
    return results


# =========================================================================== #
#  FIGURE 1: c × tau_hat HEATMAP FOR TRIGGER RATE                             #
# =========================================================================== #


def plot_figure1() -> None:
    print("\n=== Figure 1: c x tau_hat heatmap ===")

    C_VALUES       = np.linspace(0.25, 3.0, 10)
    TAU_HAT_VALUES = np.linspace(0.5,  3.0, 10)

    params_heatmap = [
        {"c": c, "tau_hat": t, "K": K}
        for c in C_VALUES
        for t in TAU_HAT_VALUES
        for _ in range(N_REPS)
    ]

    df_hm = pd.DataFrame(run_batch(params_heatmap))
    df_hm.to_csv("fig1_heatmap_trigger_raw.csv", index=False)

    pivot = df_hm.groupby(["c", "tau_hat"])["trigger"].mean().unstack("tau_hat")

    fig, ax = plt.subplots(figsize=(7, 5.5))
    im = ax.imshow(
        pivot.values,
        aspect="auto", origin="lower",
        cmap="Spectral_r", vmin=0, vmax=pivot.values.max(),
    )
    fig.colorbar(im, ax=ax, label="Trigger rate")

    ax.set_xticks(range(len(TAU_HAT_VALUES)))
    ax.set_xticklabels([f"{v:.2f}" for v in TAU_HAT_VALUES],
                       rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(C_VALUES)))
    ax.set_yticklabels([f"{v:.2f}" for v in C_VALUES], fontsize=8)
    ax.set_xlabel(r"Normalised tolerance $\hat{\tau}$")
    ax.set_ylabel(r"Width factor $c$")
    ax.set_title(
        r"$\mathbf{Trigger\ rate}$ — $c \times \hat{\tau}$",
        fontsize=11, pad=4,
    )
    ax.text(
        0.5, -0.18,
        f"$K={K}$, $\\theta={THETA}$, $\\mu={MU}$, "
        r"$\hat{\tau}$ and $c$ varied",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=8.5, color="#555555",
    )

    for i, c_val in enumerate(C_VALUES):
        for j, t_val in enumerate(TAU_HAT_VALUES):
            ax.text(j, i, f"{pivot.loc[c_val, t_val]:.2f}",
                    ha="center", va="center", fontsize=6.5)

    plt.tight_layout()
    plt.savefig("fig1_heatmap_trigger.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  → fig1_heatmap_trigger.png saved")


# =========================================================================== #
#  FIGURE 2: TRIGGER RATE AND CONDITIONAL SWITCHING VARYING c                 #
# =========================================================================== #


def plot_figure2() -> None:
    print("\n=== Figure 2: trigger rate and cond. switching varying c ===")

    C_SWEEP    = np.linspace(0.25, 3.0, 10)
    TAU_HAT_FX = 1.75

    params_sweep = [
        {"c": c, "tau_hat": TAU_HAT_FX, "K": K}
        for c in C_SWEEP
        for _ in range(N_REPS)
    ]

    df_sw = pd.DataFrame(run_batch(params_sweep))
    agg_sw = df_sw.groupby("c").agg(
        trigger_mean=("trigger",  "mean"),
        trigger_se  =("trigger",  lambda x: x.std() / np.sqrt(len(x))),
        cond_sw_mean=("cond_sw",  "mean"),
        cond_sw_se  =("cond_sw",  lambda x: x.std() / np.sqrt(len(x))),
    ).reset_index()
    agg_sw.to_csv("fig2_trigger_condswitch_raw.csv", index=False)

    color_main = SPECTRAL(0.88)
    param_spec = (
        f"$K={K}$, $\\hat{{\\tau}}={TAU_HAT_FX}$, "
        f"$\\theta={THETA}$, $\\mu={MU}$ — mean $\\pm$ 1 SE "
        f"({N_REPS} runs per condition)"
    )

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=False)

    for ax, mean_col, se_col, ylabel, title in zip(
            axes,
            ["trigger_mean", "cond_sw_mean"],
            ["trigger_se",   "cond_sw_se"],
            ["Trigger rate", "Conditional switching (triggered voters)"],
            [r"(a) Trigger rate at $T_{\max}$",
             "(b) Conditional switching among triggered voters"],
    ):
        ax.plot(agg_sw["c"], agg_sw[mean_col],
                color=color_main, linewidth=2, marker="o", markersize=5)
        ax.fill_between(
            agg_sw["c"],
            agg_sw[mean_col] - agg_sw[se_col],
            agg_sw[mean_col] + agg_sw[se_col],
            alpha=0.3, color=color_main,
        )
        ax.set_xlabel(r"Width factor $c$")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.axhline(0, color="black", linewidth=0.5, linestyle="--")

    fig.text(0.5, -0.04, param_spec,
             ha="center", va="top", fontsize=8.5, color="#555555")
    plt.tight_layout()
    plt.savefig("fig2_trigger_condswitch_c.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  → fig2_trigger_condswitch_c.png saved")


# =========================================================================== #
#  FIGURE 3: DYNAMIC TRAJECTORY — ΔCENP ACROSS ITERATIONS                    #
# =========================================================================== #


def plot_figure3() -> None:
    print("\n=== Figure 3: dynamic trajectory ===")

    WIDTH_REGIMES = {
        "Low width ($c=0.5$)":     0.5,
        "Active width ($c=1.5$)":  1.5,
        "Diffuse width ($c=2.5$)": 2.5,
    }
    TAU_HAT_TRAJ = 1.75
    N_REPS_TRAJ  = 50

    regime_colors = [SPECTRAL(0.2), SPECTRAL(1.0), SPECTRAL(0.85)]
    param_spec = (
        f"$K={K}$, $\\hat{{\\tau}}={TAU_HAT_TRAJ}$, "
        f"$\\theta={THETA}$, $\\mu={MU}$ — single representative run"
    )

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=False)

    for ax, (label, c_val), color in zip(
            axes, WIDTH_REGIMES.items(), regime_colors):

        params_traj = [
            {"c": c_val, "tau_hat": TAU_HAT_TRAJ, "K": K}
            for _ in range(N_REPS_TRAJ)
        ]
        res_traj = run_batch(params_traj, collect_history=True)
        trajs = [r["trajectory"] for r in res_traj if "trajectory" in r]

        # Representative run: the one whose final ΔCENP is closest to median
        final_vals = np.array([t[-1] for t in trajs])
        rep_traj = trajs[int(np.argmin(np.abs(final_vals - np.median(final_vals))))]
        iters = np.arange(1, len(rep_traj) + 1)

        ax.plot(iters, rep_traj, color=color, linewidth=2.2)
        ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
        ax.set_xlabel("Iteration")
        ax.set_ylabel(r"$\Delta C_{\mathrm{ENP}}$")
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    fig.text(0.5, -0.04, param_spec,
             ha="center", va="top", fontsize=8.5, color="#555555")
    plt.tight_layout()
    plt.savefig("fig3_trajectory_deltacenp.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  → fig3_trajectory_deltacenp.png saved")


# =========================================================================== #
#  FIGURE 4 DATA LOADERS                                                       #
# =========================================================================== #


def load_empirical(filepath: str = "FR-electoral_data.csv") -> pd.DataFrame:
    """
    Load FR-electoral_data.csv and compute ΔCENP per election year.

    Parses French-locale comma decimals and normalises any stray percentage
    values > 1 (e.g. 41.45 → 0.4145). Only pre_electoral_share (poll) and
    electoral_share_R1 (result) are used; the R2 column is ignored.

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
            print(f"  Loaded {fname} ({len(dfs[-1])} rows)")
        except FileNotFoundError:
            print(f"  {fname} not found — skipping")

    if not dfs:
        print("  No Saltelli files found — model range band will be omitted.")
        return {}

    sal_vals = pd.concat(dfs, ignore_index=True)["delta_cenp"].dropna()
    result = {
        "mean": float(sal_vals.mean()),
        "p05":  float(sal_vals.quantile(0.05)),
        "p95":  float(sal_vals.quantile(0.95)),
    }
    print(f"  Model ΔCENP: mean={result['mean']:.4f}, "
          f"p05={result['p05']:.4f}, p95={result['p95']:.4f}")
    return result


# =========================================================================== #
#  FIGURE 4: EMPIRICAL VALIDATION — ΔCENP ACROSS FRENCH ELECTIONS             #
# =========================================================================== #


def plot_figure4(
        empirical_data: str = "FR-electoral_data.csv",
        saltelli_ks: tuple = (6, 8, 9),
) -> None:
    """
    Compare poll-to-result ΔCENP across French presidential elections
    with model mean and p05–p95 range overlaid.

    Parameters
    ----------
    empirical_data : path to FR-electoral_data.csv
                     (columns: election_year, pre_electoral_share,
                     electoral_share_R1)
    saltelli_ks    : K values for Saltelli CSVs (saltelli_results_K{k}.csv).
                     If a file is missing it is silently skipped; if none
                     are found the model range band is omitted entirely.
    """
    print("\n=== Figure 4: empirical ΔCENP vs model range ===")

    emp_df      = load_empirical(empirical_data)
    model_range = load_model_range(saltelli_ks)

    print("\nEmpirical ΔCENP:")
    print(emp_df.to_string(index=False))

    # ── Plot ──────────────────────────────────────────────────────────────
    years   = emp_df["year"].values
    dc_vals = emp_df["delta_cenp"].values

    fig, ax = plt.subplots(figsize=(5.8, 3.6))

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

    ax.axhline(0, color="0.15", linewidth=0.4, zorder=1)
    ax.vlines(years, 0, dc_vals, color="0.15", linewidth=0.9,
              zorder=2, label="_nolegend_")
    ax.scatter(years, dc_vals, color="0.05", s=24, zorder=3,
               label="Empirical values")

    for x, y in zip(years, dc_vals):
        offset, va = (0.006, "bottom") if y >= 0 else (-0.006, "top")
        ax.text(x, y + offset, f"{y:.3f}", ha="center", va=va, fontsize=7)

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

    plt.tight_layout()
    plt.savefig("fig4_empirical_range_cenp.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("  → fig4_empirical_range_cenp.png saved")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #


def main() -> None:
    plot_figure1()
    plot_figure2()
    plot_figure3()
    plot_figure4()
    print("\nAll main figures done.")


if __name__ == "__main__":
    main()

"""
appendix_figures.py
-------------------
Generate six appendix panels from existing data files and simulation runs.

Panel A — N robustness:                N_check.csv          (reads from disk)
Panel B — Tmax convergence:            tmax_summary.csv     (reads from disk)
Panel C — epsilon stability:           epsilon_check.csv    (reads from disk)
Panel D — xi analysis:                 Xi_check.csv         (reads from disk)
Panel E — mechanical theta effect:     computed analytically
Panel F — mu analysis:                 new simulation runs

Outputs:
    appendix_A_N_robustness.png
    appendix_B_Tmax_convergence.png
    appendix_C_epsilon_stability.png
    appendix_D_xi_analysis.png
    appendix_E_mechanical_theta.png
    appendix_F_mu_analysis.png / _raw.csv
    appendix_protocol_grid.png          (2x2 grid of A–D, requires Pillow)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from model import run_simulation
from signals import transform_signal

# =========================================================================== #
#  GLOBAL STYLE                                                                #
# =========================================================================== #

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linewidth": 0.5,
    "grid.alpha": 0.6,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#cccccc",
    "lines.linewidth": 1.8,
    "lines.markersize": 5,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

SPECTRAL = plt.cm.Spectral

# Shared width regime config
REGIME_MAP = {
    "baseline": ("Low ($c=0.5$)",       0.5,  SPECTRAL(0.15)),
    "width_A":  ("Active A ($c=1.25$)", 1.25, SPECTRAL(0.38)),
    "width_B":  ("Active B ($c=1.5$)",  1.5,  SPECTRAL(0.7)),
    "high_width": ("Diffuse ($c=2.5$)", 2.5,  SPECTRAL(0.85)),
}


# =========================================================================== #
#  HELPERS                                                                     #
# =========================================================================== #


def enp(shares) -> float:
    s = np.asarray(shares, dtype=float)
    s = s / s.sum()
    return 1.0 / (s ** 2).sum()


# =========================================================================== #
#  PANEL A: N ROBUSTNESS                                                       #
# =========================================================================== #


def panel_a() -> None:
    print("Panel A: N robustness...")
    df_n = pd.read_csv("N_check.csv")

    agg_n = df_n.groupby(["scenario_name", "N"]).agg(
        se=("delta_cenp", lambda x: x.std() / np.sqrt(len(x))),
    ).reset_index()

    n_vals  = sorted(agg_n["N"].unique())
    x_pos   = np.arange(len(n_vals))
    n_to_x  = {n: i for i, n in enumerate(n_vals)}
    chosen_x = n_to_x[2000]

    fig, ax = plt.subplots(figsize=(5.5, 4))

    for scenario, (label, c_val, color) in REGIME_MAP.items():
        sub = agg_n[agg_n["scenario_name"] == scenario].sort_values("N")
        if sub.empty:
            continue
        ax.plot([n_to_x[n] for n in sub["N"]], sub["se"],
                marker="o", color=color, label=label)

    ax.axvline(chosen_x, color="#aaaaaa", linewidth=0.9,
               linestyle="--", alpha=0.8, label="$N = 2000$")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{int(n):,}" for n in n_vals], fontsize=8)
    ax.set_xlabel("Number of voters")
    ax.set_ylabel(r"SE of $\Delta C_{\mathrm{ENP}}$")
    ax.set_title("$N$ robustness")
    ax.legend(fontsize=7.5, bbox_to_anchor=(1.02, 1),
              loc="upper left", borderaxespad=0)

    plt.tight_layout()
    plt.savefig("appendix_A_N_robustness.png")
    plt.close()
    print("  → appendix_A_N_robustness.png")


# =========================================================================== #
#  PANEL B: TMAX CONVERGENCE                                                   #
# =========================================================================== #


def panel_b() -> None:
    print("Panel B: Tmax convergence...")
    df_t = pd.read_csv("tmax_summary.csv")

    tmax_color_map = {
        "Baseline (c=0.5)":      SPECTRAL(0.15),
        "Sweet-spot A (c=1.25)": SPECTRAL(0.38),
        "Sweet-spot B (c=1.5)":  SPECTRAL(0.7),
        "High width (c=2.5)":    SPECTRAL(0.85),
    }

    x       = np.arange(len(df_t))
    bw      = 0.32
    colors  = [tmax_color_map.get(r, SPECTRAL(0.7)) for r in df_t["regime"]]

    fig, ax = plt.subplots(figsize=(5.5, 4))

    ax.bar(x - bw / 2, df_t["median_conv"], bw,
           label="Median", alpha=0.85, color=colors, zorder=3)
    ax.bar(x + bw / 2, df_t["p95_conv"], bw,
           label="$p_{95}$", alpha=0.4, color=colors,
           hatch="///", edgecolor="white", linewidth=0.4, zorder=3)

    for i, (_, row) in enumerate(df_t.iterrows()):
        if row["n_tmax_binding"] > 0:
            ax.text(i + bw / 2, row["p95_conv"] + 0.4,
                    f"{int(row['n_tmax_binding'])}/20 did not converge",
                    ha="center", fontsize=6.5, color="#333333", style="italic")

    ax.axhline(25, color="#aaaaaa", linewidth=0.9,
               linestyle="--", zorder=2, label=r"$T_{\max} = 25$")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [r.replace(" (", "\n(") for r in df_t["regime"]], fontsize=7.5)
    ax.set_ylabel("Convergence iteration")
    ax.set_title(r"$T_{\max}$ convergence diagnostic")
    ax.legend(fontsize=7.5, loc="upper left")

    plt.tight_layout()
    plt.savefig("appendix_B_Tmax_convergence.png")
    plt.close()
    print("  → appendix_B_Tmax_convergence.png")


# =========================================================================== #
#  PANEL C: EPSILON STABILITY                                                  #
# =========================================================================== #


def panel_c() -> None:
    print("Panel C: epsilon stability...")
    df_e = pd.read_csv("epsilon_check.csv")

    configs_to_plot = [
        ("Baseline, theta=0.3",   SPECTRAL(0.15), "-",  r"Baseline, $\theta=0.3$"),
        ("Baseline, theta=1.0",   SPECTRAL(0.38), "--", r"Baseline, $\theta=1.0$"),
        ("Sweet-spot, theta=0.3", SPECTRAL(0.7),  "-",  r"Active, $\theta=0.3$"),
        ("Sweet-spot, theta=1.0", SPECTRAL(0.85), "--", r"Active, $\theta=1.0$"),
    ]

    eps_vals = sorted(df_e["eps"].unique())
    x_eps    = np.arange(len(eps_vals))

    fig, ax = plt.subplots(figsize=(5.5, 4))

    for config, color, ls, label in configs_to_plot:
        sub = df_e[df_e["config"] == config].sort_values("eps")
        if sub.empty:
            continue
        ax.plot(x_eps, sub["delta_cenp_mean"].values,
                marker="o", color=color, linestyle=ls, label=label)
        ax.fill_between(
            x_eps,
            sub["delta_cenp_mean"].values - sub["delta_cenp_sd"].values,
            sub["delta_cenp_mean"].values + sub["delta_cenp_sd"].values,
            alpha=0.06, color=color,
        )

    try:
        chosen_idx = eps_vals.index(1e-4)
    except ValueError:
        chosen_idx = 1  # fallback
    ax.axvline(chosen_idx, color="#aaaaaa", linewidth=0.9,
               linestyle="--", alpha=0.9,
               label=r"Chosen $\varepsilon_s = 10^{-4}$")

    ax.set_xticks(x_eps)
    ax.set_xticklabels(
        [f"$10^{{{int(np.log10(e))}}}$" for e in eps_vals], fontsize=8.5)
    ax.set_xlabel(r"Signal offset $\varepsilon_s$")
    ax.set_ylabel(r"$\Delta C_{\mathrm{ENP}}$")
    ax.set_title(r"Signal offset $\varepsilon_s$ stability")
    ax.legend(fontsize=7.5, bbox_to_anchor=(1.02, 1),
              loc="upper left", borderaxespad=0)

    plt.tight_layout()
    plt.savefig("appendix_C_epsilon_stability.png")
    plt.close()
    print("  → appendix_C_epsilon_stability.png")


# =========================================================================== #
#  PANEL D: XI ANALYSIS                                                        #
# =========================================================================== #


def panel_d() -> None:
    print("Panel D: xi analysis...")
    df_xi = pd.read_csv("Xi_check.csv")

    sub_xi = df_xi[np.isclose(df_xi["theta"], 1.0)].copy()
    agg_xi = sub_xi.groupby("xi").agg(
        enp_final_mean  =("enp_final",   "mean"),
        enp_final_se    =("enp_final",   lambda x: x.std() / np.sqrt(len(x))),
        enp_sincere_mean=("enp_sincere", "mean"),
        enp_sincere_se  =("enp_sincere", lambda x: x.std() / np.sqrt(len(x))),
    ).reset_index().sort_values("xi")

    color_final   = SPECTRAL(0.15)
    color_sincere = SPECTRAL(0.85)

    fig, ax = plt.subplots(figsize=(5.5, 4))

    # Party position reference lines (background)
    party_positions = [-1 + (2 * j + 1) / 6 for j in range(6)]
    for xp in party_positions:
        ax.axvline(xp, color="#dddddd", linewidth=0.6, linestyle=":", zorder=1)

    # Sincere ENP — dashed, behind final
    ax.plot(agg_xi["xi"], agg_xi["enp_sincere_mean"],
            color=color_sincere, linewidth=1.5, marker="s",
            markersize=4, linestyle="--", label="Sincere ENP", zorder=2)
    ax.fill_between(
        agg_xi["xi"],
        agg_xi["enp_sincere_mean"] - agg_xi["enp_sincere_se"],
        agg_xi["enp_sincere_mean"] + agg_xi["enp_sincere_se"],
        alpha=0.1, color=color_sincere, zorder=2,
    )

    # Final ENP — solid, on top
    ax.plot(agg_xi["xi"], agg_xi["enp_final_mean"],
            color=color_final, linewidth=2, marker="o",
            markersize=5, label="Final ENP", zorder=3)
    ax.fill_between(
        agg_xi["xi"],
        agg_xi["enp_final_mean"] - agg_xi["enp_final_se"],
        agg_xi["enp_final_mean"] + agg_xi["enp_final_se"],
        alpha=0.15, color=color_final, zorder=3,
    )

    ax.set_xlabel(r"Electorate centre $\xi$")
    ax.set_ylabel("ENP")
    ax.set_title(r"ENP across $\xi$ ($\theta = 1$, $c = 0.5$)")
    ax.legend(fontsize=8, loc="lower center",
              bbox_to_anchor=(0.5, -0.32), ncol=2,
              borderaxespad=0)

    plt.tight_layout()
    plt.savefig("appendix_D_xi_analysis.png")
    plt.close()
    print("  → appendix_D_xi_analysis.png")


# =========================================================================== #
#  PANEL E: MECHANICAL EFFECT OF SIGNAL TEMPERATURE                           #
#  No simulation runs needed — computed analytically from transform_signal.   #
# =========================================================================== #


def panel_e() -> None:
    print("Panel E: mechanical theta effect...")

    baseline_shares = np.array([0.05, 0.07, 0.18, 0.25, 0.22, 0.13, 0.07, 0.03])
    baseline_shares = baseline_shares / baseline_shares.sum()
    K_e = len(baseline_shares)

    THETA_VALUES = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]
    show_thetas  = [0.3, 1.0, 3.0]
    show_colors  = [SPECTRAL(0.32), SPECTRAL(0.7), SPECTRAL(0.9)]

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(10, 4))

    # ── Left: transformed signal shares for 3 representative theta ────────
    x_parties = np.arange(K_e)
    bw        = 0.22
    offsets   = [-bw, 0, bw]

    for theta_s, color, offset in zip(show_thetas, show_colors, offsets):
        s_tilde = transform_signal(baseline_shares, theta=theta_s)
        label = (r"$\theta = 1.0$ (sincere shares)"
                 if theta_s == 1.0 else f"$\\theta = {theta_s}$")
        ax0.bar(x_parties + offset, s_tilde, bw,
                color=color, alpha=0.7, label=label)

    ax0.set_xticks(x_parties)
    ax0.set_xticklabels([f"$P_{j + 1}$" for j in range(K_e)], fontsize=8)
    ax0.set_xlabel("Party")
    ax0.set_ylabel(r"Transformed signal share $\tilde{s}$")
    ax0.set_title(r"Signal distortion by $\theta$")
    ax0.legend(fontsize=7.5, ncol=1)

    # ── Right: ΔENP = ENP(signal) − ENP(true shares) vs theta ────────────
    enp_original = enp(baseline_shares)
    delta_enp = [enp(transform_signal(baseline_shares, theta=t)) - enp_original
                 for t in THETA_VALUES]

    ax1.plot(THETA_VALUES, delta_enp,
             color=SPECTRAL(0.9), linewidth=2, marker="o", markersize=5)
    ax1.axhline(0, color="#aaaaaa", linewidth=0.9,
                linestyle="--", label=r"No distortion ($\theta = 1$)")
    ax1.axvline(1.0, color="#aaaaaa", linewidth=0.7,
                linestyle=":", alpha=0.7)
    ax1.set_xlabel(r"Signal temperature $\theta$")
    ax1.set_ylabel(
        r"$\Delta\mathrm{ENP} = \mathrm{ENP}(\tilde{s}) - \mathrm{ENP}(\delta)$")
    ax1.set_title("Signal ENP deviation from true shares")
    ax1.legend(fontsize=7.5)

    fig.suptitle(
        r"Mechanical effect of $\theta$ before any behavioral response",
        fontsize=9, color="#555555", y=1.02,
    )
    plt.tight_layout()
    plt.savefig("appendix_E_mechanical_theta.png")
    plt.close()
    print("  → appendix_E_mechanical_theta.png")


# =========================================================================== #
#  PANEL F: MU ANALYSIS — CONDITIONAL SWITCHING VS EXPRESSIVE COST            #
#  Requires new simulation runs (~600 total, fast).                           #
# =========================================================================== #


def panel_f() -> None:
    print("Panel F: mu analysis...")

    K_F       = 8
    N_F       = 1000
    TMAX_F    = 25
    ALPHA_F   = 0.0
    RHO_S_F   = 100.0
    RHO_PI_F  = 100.0
    THETA_F   = 1.0
    EPS_F     = 0.1
    XI_F      = 0.0
    TAU_HAT_F = 1.75
    TAU_ABS_F = TAU_HAT_F * (2.0 / K_F)
    N_REPS_F  = 30

    MU_VALUES = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
    REGIMES_F = {
        "Active ($c=1.5$)": (1.5, SPECTRAL(0.7)),
        "Low ($c=0.5$)":    (0.5, SPECTRAL(0.15)),
    }

    total_runs = len(MU_VALUES) * len(REGIMES_F) * N_REPS_F
    done = 0
    rows_f = []

    for regime_label, (c_val, _) in REGIMES_F.items():
        for mu_val in MU_VALUES:
            cond_sws = []
            for s in range(N_REPS_F):
                try:
                    res = run_simulation(
                        K=K_F, n_modes=1, width_factor=c_val,
                        mode_position=XI_F, floor_weight=EPS_F,
                        theta=THETA_F, rho=RHO_S_F, rho_pi=RHO_PI_F,
                        n_electors=N_F, tau=TAU_ABS_F,
                        mu=mu_val, alpha_prior=ALPHA_F,
                        K_runoff=2, max_iterations=TMAX_F,
                        seed=s, verbose=False,
                        collect_diagnostics=True,
                    )
                    cond_sws.append(
                        res["diagnostics"]["conditional_switching_given_triggered"]
                    )
                except Exception as e:
                    print(f"    WARNING: run failed ({e})")
                done += 1
                if done % 100 == 0:
                    print(f"    {done}/{total_runs} runs...")

            rows_f.append({
                "regime":       regime_label,
                "c":            c_val,
                "mu":           mu_val,
                "cond_sw_mean": np.mean(cond_sws) if cond_sws else np.nan,
                "cond_sw_se":   (np.std(cond_sws) / np.sqrt(len(cond_sws))
                                 if len(cond_sws) > 1 else np.nan),
            })

    df_f = pd.DataFrame(rows_f)
    df_f.to_csv("appendix_F_mu_analysis_raw.csv", index=False)

    fig, ax = plt.subplots(figsize=(5.5, 4))

    for regime_label, (c_val, color) in REGIMES_F.items():
        sub = df_f[df_f["regime"] == regime_label].sort_values("mu")
        ax.plot(sub["mu"], sub["cond_sw_mean"],
                color=color, linewidth=2, marker="o",
                markersize=5, label=regime_label)
        ax.fill_between(
            sub["mu"],
            sub["cond_sw_mean"] - sub["cond_sw_se"],
            sub["cond_sw_mean"] + sub["cond_sw_se"],
            alpha=0.2, color=color,
        )

    ax.set_xlabel(r"Expressive cost $\mu$")
    ax.set_ylabel("Conditional switching rate")
    ax.set_title(r"Conditional switching vs expressive cost $\mu$")
    ax.legend(fontsize=8)
    ax.text(
        0.98, 0.95,
        f"$K={K_F}$, $\\hat{{\\tau}}={TAU_HAT_F}$, "
        f"$\\theta={THETA_F}$\n({N_REPS_F} runs per condition)",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=7.5, color="#555555",
    )

    plt.tight_layout()
    plt.savefig("appendix_F_mu_analysis.png")
    plt.close()
    print("  → appendix_F_mu_analysis.png")


# =========================================================================== #
#  COMBINED 2x2 GRID (A–D)                                                    #
# =========================================================================== #


def assemble_grid() -> None:
    print("Assembling combined figures...")
    try:
        from PIL import Image

        imgs = [
            "appendix_A_N_robustness.png",
            "appendix_B_Tmax_convergence.png",
            "appendix_C_epsilon_stability.png",
            "appendix_D_xi_analysis.png",
        ]
        loaded = [Image.open(p) for p in imgs]
        w, h = loaded[0].size
        grid = Image.new("RGB", (w * 2, h * 2), "white")
        for img, pos in zip(loaded, [(0, 0), (w, 0), (0, h), (w, h)]):
            grid.paste(img, pos)
        grid.save("appendix_protocol_grid.png", dpi=(300, 300))
        print("  → appendix_protocol_grid.png (2x2: A–D)")
        print("  → appendix_E_mechanical_theta.png (standalone wide figure)")
        print("  → appendix_F_mu_analysis.png (standalone)")

    except ImportError:
        print("  Pillow not installed — skipping combined grid.")
        print("  Install with: pip install Pillow")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #


def main() -> None:
    panel_a()
    panel_b()
    panel_c()
    panel_d()
    panel_e()
    panel_f()
    assemble_grid()
    print("\nAll appendix figures done.")


if __name__ == "__main__":
    main()

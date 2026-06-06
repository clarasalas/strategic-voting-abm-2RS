"""
empirical_outcomes.py
---------------------
Outcome measures for the empirical 2002 / 2022 replay.

Given the result dict from ``model.run_simulation`` (run in empirical-override
mode with ``collect_diagnostics=True``) plus the actual result vector and the
first poll signal, ``compute_run_outcomes`` returns a flat dict of scalar
metrics together with per-candidate arrays.  The empirical runner aggregates
these across parameter draws.

Coordination statistics (ENP, ΔCENP, cliff magnitude/location/ratio) are
delegated to ``functions.coordination_measures`` so the definitions stay in one
place.
"""

import numpy as np

import functions


def _topk_set(shares: np.ndarray, k: int) -> set:
    """Indices of the k largest shares (ties broken by index)."""
    return set(int(i) for i in np.argsort(-np.asarray(shares, dtype=float))[:k])


def topk_accuracy(sim_shares: np.ndarray, actual: np.ndarray, k: int) -> float:
    """1.0 if the simulated top-k set equals the actual top-k set, else 0.0."""
    return float(_topk_set(sim_shares, k) == _topk_set(actual, k))


def topk_membership(sim_shares: np.ndarray, k: int) -> np.ndarray:
    """Boolean (K,) indicator of which candidates are in the simulated top-k."""
    members = _topk_set(sim_shares, k)
    return np.array([j in members for j in range(len(sim_shares))], dtype=float)


def compute_run_outcomes(result: dict, actual: np.ndarray,
                         first_signal: np.ndarray) -> dict:
    """
    Compute all outcome measures for a single simulation run.

    Parameters
    ----------
    result       : dict      -- return value of run_simulation (empirical mode,
                                collect_diagnostics=True recommended).
    actual       : array (K,) -- actual R1 result shares (sum 1).
    first_signal : array (K,) -- s^0, the first poll signal (sum 1).

    Returns
    -------
    dict with scalar metrics plus per-candidate arrays:

        Scalars
        -------
        rmse, mae                          : sim final vs actual
        top2_acc, top3_acc, top4_acc       : set-match accuracy
        enp_sincere, enp_final, delta_enp  : effective number of parties
        delta_cenp                         : coordination gain
        cliff_magnitude (d*), cliff_location (k*), cliff_ratio (r')
        trigger_rate                       : final-iteration trigger rate
        switching_rate                     : overall strategic switching rate
        conditional_switching_rate         : switching | triggered

        Per-candidate arrays (length K)
        -------------------------------
        final_shares                       : simulated final shares
        actual_shares                      : actual shares (echoed)
        change_from_first_signal           : final - s^0
        top2_member, top3_member, top4_member : 0/1 indicators
    """
    final = np.asarray(result["final_shares"], dtype=float)
    sincere = np.asarray(result["sincere_shares"], dtype=float)
    actual = np.asarray(actual, dtype=float)
    first_signal = np.asarray(first_signal, dtype=float)

    err = final - actual
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))

    coord = functions.coordination_measures(sincere, final)

    diag = result.get("diagnostics") or {}
    trigger_rate = float(diag.get("trigger_rate_final", np.nan))
    conditional_switching = float(
        diag.get("conditional_switching_given_triggered", np.nan)
    )
    switching = result.get("switching") or {}
    switching_rate = float(switching.get("pct_strategic", np.nan))

    return {
        # --- error vs actual ---
        "rmse": rmse,
        "mae": mae,
        # --- top-k set accuracy ---
        "top2_acc": topk_accuracy(final, actual, 2),
        "top3_acc": topk_accuracy(final, actual, 3),
        "top4_acc": topk_accuracy(final, actual, 4),
        # --- coordination / fragmentation ---
        "enp_sincere": coord["enp_sincere"],
        "enp_final": coord["enp_final"],
        "delta_enp": coord["enp_final"] - coord["enp_sincere"],
        "delta_cenp": coord["delta_cenp"],
        "cliff_magnitude": coord["d_star_final"],
        "cliff_location": coord["k_star_final"],
        "cliff_ratio": coord["r_prime_final"],
        # --- behavioural diagnostics ---
        "trigger_rate": trigger_rate,
        "switching_rate": switching_rate,
        "conditional_switching_rate": conditional_switching,
        # --- per-candidate arrays ---
        "final_shares": final,
        "actual_shares": actual,
        "change_from_first_signal": final - first_signal,
        "top2_member": topk_membership(final, 2),
        "top3_member": topk_membership(final, 3),
        "top4_member": topk_membership(final, 4),
    }

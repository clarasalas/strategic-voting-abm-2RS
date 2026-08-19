"""
Shared coordination metrics used across the analysis scripts.

These are model-level quantities (not specific to any one analysis), so they
live in ``core_model`` where both the empirical and synthetic analyses can
import them.

    ENP(δ)  = 1 / Σ_j δ_j²                  effective number of parties
    CENP(δ) = (K − ENP(δ)) / (K − 1)        coordination-scaled ENP, in [0, 1]
"""

import numpy as np


def enp(shares) -> float:
    """Effective number of parties for a share vector."""
    s = np.asarray(shares, dtype=float)
    s = s / s.sum()
    return 1.0 / (s ** 2).sum()


def cenp(shares, K: int) -> float:
    """Coordination-scaled ENP in [0, 1] for ``K`` candidates."""
    return (K - enp(shares)) / (K - 1)


def delta_cenp(poll, result) -> float:
    """Coordination gain from poll to result (same K, inferred from poll length)."""
    K = len(poll)
    return cenp(result, K) - cenp(poll, K)


# --------------------------------------------------------------------------- #
#  Tolerance-threshold units                                                   #
# --------------------------------------------------------------------------- #
#
# Two different quantities are both called "tau" in this project:
#
#   tau_hat  the NORMALISED tolerance threshold.  This is the design variable:
#            it is what the Saltelli problem, the empirical parameter design and
#            the behavioural sweep all draw, what every CSV records, and what the
#            paper reports.  It is measured in zone lengths, so it is comparable
#            across party systems of different size.
#
#   tau      the ABSOLUTE tolerance threshold, in ideological-space units on
#            [-1, 1].  This is what ``run_simulation(tau=...)`` and
#            ``Elector(tau=...)`` expect, and the only unit the model itself
#            understands.
#
# The two are related through the zone length 2/K, so the SAME tau_hat maps to a
# DIFFERENT absolute tau in each party system -- notably to a different value in
# each election year of the empirical replay (K = 15 in 2002, K = 12 in 2022).
# Converting is therefore not optional: passing a tau_hat straight into
# run_simulation silently reinterprets it as an absolute distance, which for
# tau_hat >= 2 makes every party a contender for every voter and disables the
# Ca/Oa distinction entirely.

def zone_length(K: int) -> float:
    """Width of one party zone on [-1, 1] for a K-party system."""
    return 2.0 / K


def tau_absolute(tau_hat: float, K: int) -> float:
    """
    Convert a normalised tolerance threshold to absolute ideological units.

        tau = tau_hat * (2 / K)

    Any experiment runner that draws ``tau_hat`` must pass the result of this
    function to ``run_simulation(tau=...)``, never ``tau_hat`` itself.
    """
    return tau_hat * zone_length(K)

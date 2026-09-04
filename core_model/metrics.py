"""
Coordination metrics, shared by both analysis lanes.

    ENP(δ)  = 1 / Σ_j δ_j²                  effective number of parties
    CENP(δ) = (K − ENP(δ)) / (K − 1)        coordination-scaled ENP, in [0, 1]

They sit in ``core_model`` because the empirical and synthetic scripts both
need them.
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
# Two quantities in this project are called "tau".
#
#   tau_hat  the NORMALISED threshold, measured in zone lengths.  Every design
#            draws it, every CSV records it, the paper reports it.  Being in
#            zone lengths, it compares across party systems of different size.
#
#   tau      the ABSOLUTE threshold, in ideological units on [-1, 1].  The only
#            unit the model itself understands: ``run_simulation(tau=...)`` and
#            ``Elector(tau=...)`` both expect this one.
#
# One zone is 2/K wide, so a single tau_hat becomes a different absolute tau in
# each party system, and so a different one in each year of the replay (K = 15
# in 2002, K = 12 in 2022).  Passing tau_hat straight into run_simulation
# silently reinterprets it as an absolute distance.  At tau_hat >= 2 that makes
# every party a contender for every voter, which switches the Ca/Oa distinction
# off altogether.

def zone_length(K: int) -> float:
    """Width of one party zone on [-1, 1] for a K-party system."""
    return 2.0 / K


def tau_absolute(tau_hat: float, K: int) -> float:
    """
    Convert a normalised tolerance threshold to absolute ideological units.

        tau = tau_hat * (2 / K)

    A runner that draws ``tau_hat`` passes this result to
    ``run_simulation(tau=...)``, never ``tau_hat`` itself.
    """
    return tau_hat * zone_length(K)

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

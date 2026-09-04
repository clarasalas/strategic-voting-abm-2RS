"""
signals.py
----------
Poll signal generation for the strategic voting ABM.

Entry points
------------
- generate_signal   : full draw, temperature transform plus Dirichlet noise.
- transform_signal  : the transform s̃ alone, no noise.  For diagnostics.
- rank_signal       : party indices by signal share, strongest first.

Signal model
------------
Each draw transforms the true support shares, then adds Dirichlet noise:

    s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)   (temperature transform)
    s   ~ Dirichlet(ρ · s̃)                            (Dirichlet draw)

θ shapes the signal and ρ sets its precision, independently of each other.

θ < 1  sharpens: front-runners look stronger than they are, viability gaps
       widen, and the signal helps coordination.
θ = 1  leaves the shares alone: a faithful signal.
θ > 1  flattens: the race looks more open than it is, viability gaps close,
       and the signal feeds fragmentation.

ρ      higher means closer to s̃ and less noise; lower means noisier and more
       diffuse.
"""

import numpy as np


def generate_signal(
        true_support: np.ndarray,
        theta: float = 1.0,
        rho: float = 100.0,
        eps: float = 1e-12,
        rng=None,
) -> np.ndarray:
    """
    Temperature-transformed Dirichlet poll signal for K parties.

        s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)
        s   ~ Dirichlet(ρ · s̃)

    Parameters
    ----------
    true_support : array (K,)
        True support shares δ.  Normalised internally; need not sum to 1.
    theta : float
        Temperature (default 1.0, a faithful signal).  Below 1 sharpens
        viability gaps, above 1 compresses them.
    rho : float
        Dirichlet precision (default 100.0, close to noiseless).  Higher is
        closer to s̃; lower is noisier.
    eps : float
        Numerical floor added before exponentiation, so a party on ZERO support
        still gets a strictly positive concentration ρ·s̃_i.  Without it that
        party stays pinned at zero signal share for the whole run.  An all-zero
        support vector is a separate case, caught by the uniform fallback
        below.  Default 1e-12, the fixed synthetic specification.
    rng : np.random.Generator or None

    Returns
    -------
    np.ndarray (K,)
        Dirichlet draw: non-negative, sums to 1, so it goes straight into the
        belief update with no clipping.
    """
    if rng is None:
        rng = np.random.default_rng()

    true_support = np.asarray(true_support, dtype=float)
    K = len(true_support)

    # Normalise true support to a valid probability vector
    total = true_support.sum()
    delta = true_support / total if total > 0 else np.ones(K) / K

    # ── Temperature transformation: (δ_i + ε)^(1/θ) ────────────────────────
    transformed = (delta + eps) ** (1.0 / theta)
    s_tilde = transformed / transformed.sum()

    # ── Dirichlet draw: s ~ Dirichlet(ρ · s̃) ────────────────────────────────
    concentration = rho * s_tilde
    return rng.dirichlet(concentration)


def transform_signal(
        true_support: np.ndarray,
        theta: float = 1.0,
        eps: float = 1e-12,
) -> np.ndarray:
    """
    The temperature transformation s̃ on its own, without the Dirichlet draw:
    the signal shape before any polling noise.

        s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)

    Comparing s̃ with the true support δ shows how much theta distorts the
    shape by itself, with the noise taken out of the picture.

    Parameters
    ----------
    true_support : array (K,)
        True support shares δ.  Normalised internally.
    theta : float
        Temperature.  Same meaning as in generate_signal.
    eps : float
        Numerical floor before exponentiation; see generate_signal.
        Default 1e-12.

    Returns
    -------
    np.ndarray (K,) of transformed shares, summing to 1.
    """
    true_support = np.asarray(true_support, dtype=float)
    K = len(true_support)
    total = true_support.sum()
    delta = true_support / total if total > 0 else np.ones(K) / K
    transformed = (delta + eps) ** (1.0 / theta)
    return transformed / transformed.sum()


def rank_signal(signal: np.ndarray) -> np.ndarray:
    """Party indices ordered by signal share, strongest first."""
    return np.argsort(-np.asarray(signal, dtype=float))

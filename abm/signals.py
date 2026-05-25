"""
signals.py
----------
Poll signal generation for the strategic voting ABM.

Entry points
------------
- generate_signal   : full signal draw (temperature transform + Dirichlet noise).
- transform_signal  : deterministic transform s̃ only, without Dirichlet noise.
                      Use for diagnostics to isolate θ-induced distortion.
- rank_signal       : party indices sorted by signal share, strongest first.

Signal model
------------
Each draw applies a temperature transformation to the true support shares
and then adds Dirichlet noise:

    s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)   (temperature transform)
    s   ~ Dirichlet(ρ · s̃)                            (Dirichlet draw)

θ and ρ control signal shape and precision independently.

θ < 1  sharpens the distribution: front-runners appear stronger than they
       are and viability gaps are amplified → coordination-enhancing signal.
θ = 1  leaves the distribution unchanged → faithful signal.
θ > 1  flattens the distribution: the race appears more open than it is
       and viability gaps are compressed → fragmentation-enhancing signal.

ρ      controls signal precision.  Higher ρ → signal closer to s̃ (less
       noise).  Lower ρ → noisier, more diffuse signal.
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
        Temperature parameter (default 1.0 = faithful signal).
        < 1  →  concentration-amplifying: sharpens viability gaps.
        = 1  →  no distortion.
        > 1  →  fragmentation-amplifying: compresses viability gaps.
    rho : float
        Dirichlet precision (default 100.0 ≈ near-noiseless signal).
        Higher values → signal closer to s̃ (less noise).
        Lower values  → noisier, more diffuse signal.
    eps : float
        Small constant added before exponentiation to avoid 0^(1/θ) issues
        when θ < 1 and a party has no support.  Default 1e-12.
    rng : np.random.Generator or None

    Returns
    -------
    np.ndarray (K,)
        Dirichlet draw — non-negative and sums to 1.
        Can be passed directly to the belief update without clipping.
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
    Return the deterministic temperature transformation s̃ without the
    Dirichlet draw.  This is the signal shape before polling noise is added.

        s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)

    Use this for diagnostics: compare s̃ directly to true support δ to
    understand how much theta distorts the signal shape independently of
    Dirichlet noise.

    Parameters
    ----------
    true_support : array (K,)
        True support shares δ.  Normalised internally.
    theta : float
        Temperature parameter.  Same semantics as generate_signal.
    eps : float
        Floor before exponentiation.  Default 1e-12.

    Returns
    -------
    np.ndarray (K,) — deterministic transformed shares, sums to 1.
    """
    true_support = np.asarray(true_support, dtype=float)
    K = len(true_support)
    total = true_support.sum()
    delta = true_support / total if total > 0 else np.ones(K) / K
    transformed = (delta + eps) ** (1.0 / theta)
    return transformed / transformed.sum()


def rank_signal(signal: np.ndarray) -> np.ndarray:
    """
    Return party indices sorted by signal descending (strongest first).

    Parameters
    ----------
    signal : array (K,)

    Returns
    -------
    np.ndarray (K,) of int
    """
    return np.argsort(-np.asarray(signal, dtype=float))
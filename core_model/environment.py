"""
environment.py
--------------
Ideological space construction for the strategic voting ABM.

Entry points
------------
- build_equal_zones        : K equal-length zones on [-1, 1]; party
                             positions at zone midpoints.
- build_voter_distribution : single Gaussian (or skew-normal) plus an
                             optional uniform floor.

Electorate types
----------------
n_modes = 0   Uniform electorate.
              Voters are drawn uniformly from [xmin, xmax].

n_modes = 1   Unimodal electorate.
              Voters cluster around a single mode following a Gaussian
              (skewness = 0) or skew-normal (skewness ≠ 0) distribution,
              with an optional uniform floor:

                  p(x) = (1 − ε) · SN(ξ, ω², α) + ε · U[−1, 1]

              Symmetric unimodal  :  mode_position = 0.0 (default), skewness = 0.
              Asymmetric unimodal :  shift mode_position or set skewness ≠ 0.
              Diffuse / cohesive  :  adjust width_factor (fraction of zone_length).

Design notes
------------
Width is expressed as a fraction of zone_length = 2/K so that the
distribution scales consistently as K varies.

The floor_weight parameter ε ensures a non-zero probability of voter
placement anywhere on the spectrum.  This prevents perfectly symmetric
configurations from mechanically suppressing strategic switching.
Recommended range: 0.05–0.15 for unimodal electorates.
"""

import numpy as np


# =========================================================================== #
#  PARTY POSITIONS                                                             #
# =========================================================================== #

def build_equal_zones(K: int, space: tuple = (-1.0, 1.0)) -> dict:
    """
    Build K equal-length contiguous zones on the ideological interval,
    with party kernels (positions) at the midpoint of each zone.

    Parameters
    ----------
    K     : int           — number of parties (>= 1)
    space : (float, float) — ideological interval, default (-1, 1)

    Returns
    -------
    dict with keys:
        party_intervals : list of (left, right) of length K
        party_positions : np.ndarray of shape (K,)
        zone_length     : float
        space           : (xmin, xmax)
    """
    if K < 1:
        raise ValueError("K must be at least 1.")

    xmin, xmax = space
    zone_length = (xmax - xmin) / K

    party_intervals = []
    party_positions = []

    for j in range(K):
        left = xmin + j * zone_length
        right = xmin + (j + 1) * zone_length
        party_intervals.append((left, right))
        party_positions.append(0.5 * (left + right))

    return {
        "party_intervals": party_intervals,
        "party_positions": np.array(party_positions),
        "zone_length": zone_length,
        "space": space,
    }


# =========================================================================== #
#  VOTER PLACEMENT — SINGLE ATTRACTOR + UNIFORM FLOOR                         #
# =========================================================================== #

def build_voter_distribution(
        K: int,
        n_modes: int,
        width_factor: float = 0.5,
        mode_position: float = None,
        floor_weight: float = 0.0,
        skewness: float = 0.0,
        space: tuple = (-1.0, 1.0),
) -> dict:
    """
    Build the voter placement distribution.

    Two electorate types are supported:

        n_modes = 0   Pure uniform U[xmin, xmax].
        n_modes = 1   Unimodal: skew-normal + optional uniform floor.

    Parameters
    ----------
    K : int
        Number of parties.  Determines zone_length = (xmax−xmin)/K.
    n_modes : int
        0  →  uniform electorate (all other parameters ignored).
        1  →  unimodal electorate.
    width_factor : float
        Mode width as a fraction of zone_length.
        0.2 = tight/cohesive, 1.0 = diffuse.
    mode_position : float or None
        Centre of the Gaussian mode.
        None  →  0.0 (ideological centre of [-1, 1]).
        Set to a non-zero value for a left- or right-leaning electorate.
    floor_weight : float in [0, 1)
        Weight of the uniform floor component.
        0.0 = pure Gaussian (no floor).
        Recommended 0.05–0.15 to prevent symmetry from pre-solving
        coordination and suppressing strategic switching.
    skewness : float
        Shape parameter α of the skew-normal distribution.
        0.0   →  symmetric Gaussian.
        > 0   →  right skew (tail toward the right).
        < 0   →  left skew (tail toward the left).
        Negative values are common for centre-left electorates.
    space : (float, float)
        Ideological interval, default (-1, 1).

    Returns
    -------
    dict with keys:
        n_modes        : int
        mode_positions : np.ndarray (1,) or None
        mode_widths    : np.ndarray (1,) or None
        mode_weights   : np.ndarray (1,) or None  (always [1.0])
        floor_weight   : float
        skewness       : float
        zone_length    : float
        space          : tuple
    """
    if K < 1:
        raise ValueError("K must be at least 1.")
    if n_modes not in (0, 1):
        raise ValueError(
            f"n_modes must be 0 (uniform) or 1 (unimodal); "
            f"got {n_modes}."
        )
    if not (0.0 <= floor_weight < 1.0):
        raise ValueError("floor_weight must be in [0, 1).")

    xmin, xmax = space
    zone_length = (xmax - xmin) / K

    # ── Uniform case ─────────────────────────────────────────────────────────
    if n_modes == 0:
        return {
            "n_modes": 0,
            "mode_positions": None,
            "mode_widths": None,
            "mode_weights": None,
            "floor_weight": 0.0,
            "skewness": 0.0,
            "zone_length": zone_length,
            "space": space,
        }

    # ── Unimodal case ────────────────────────────────────────────────────────
    if mode_position is None:
        mode_position = 0.0  # ideological centre

    if width_factor < 0:
        raise ValueError("width_factor must be non-negative.")

    return {
        "n_modes": 1,
        "mode_positions": np.array([mode_position]),
        "mode_widths": np.array([width_factor * zone_length]),
        "mode_weights": np.array([1.0]),
        "floor_weight": float(floor_weight),
        "skewness": float(skewness),
        "zone_length": zone_length,
        "space": space,
    }

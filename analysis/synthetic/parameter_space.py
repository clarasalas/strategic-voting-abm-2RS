"""
parameter_space.py
------------------
The synthetic model's parameter space, in one side-effect-free place.

Importing this module runs no experiment, touches no file, imports no plotting
backend and pulls in no simulation code.  That is the point: both
``saltelli_sensitivity.py`` and ``protocol_validation.py`` need the same eight
parameters with the same bounds, and a validation of the Saltelli protocol that
copied the bounds by hand would be validating something else the moment one of
them drifted.

Two different quantities are spelled "epsilon" in this project.  They are not
related and confusing them is easy:

    epsilon   (in PROBLEM, swept over [0.05, 0.5])
              The ELECTORATE FLOOR WEIGHT eps_F, passed to
              run_simulation(floor_weight=...).  This is the one the Saltelli
              design sweeps.  It is NOT signal_epsilon.

    eps_s     (NOT in PROBLEM, the fixed synthetic specification)
              run_simulation(signal_epsilon=...), fixed at 1e-12.  It gives
              zero-support components a strictly positive Dirichlet
              concentration so they are not pinned at zero signal share.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
#  Free parameters: the Saltelli problem definition                            #
# --------------------------------------------------------------------------- #

PROBLEM = {
    "num_vars": 8,
    "names": [
        "tau_hat",   # normalised tolerance threshold
        "c",         # electorate width factor
        "theta",     # signal temperature
        "rho_s",     # signal precision
        "rho_pi",    # prior precision
        "alpha",     # prior weight in the belief update
        "mu",        # expressive cost weight
        "epsilon",   # uniform FLOOR weight (eps_F), not the signal offset
    ],
    "bounds": [
        [0.5,   3.0],    # tau_hat
        [0.25,  3.0],    # c
        [0.3,   3.0],    # theta
        [10.0,  200.0],  # rho_s
        [5.0,   200.0],  # rho_pi
        [0.0,   0.9],    # alpha
        [0.0,   1.0],    # mu
        [0.05,  0.5],    # epsilon (floor weight)
    ],
}

# Structural values run separately: odd/even geometry distinction.
K_VALUES = [6, 8, 9]

# Outcome measures recorded for every evaluation.
OUTCOMES = [
    "delta_cenp",
    "trigger_rate",
    "cond_switching",
    "total_switching",
    "enp_final",
]

OUTCOME_LABELS = {
    "delta_cenp":      "ΔCENP",
    "trigger_rate":    "Trigger rate",
    "cond_switching":  "Cond. switching",
    "total_switching": "Total switching",
    "enp_final":       "Final ENP",
}

# --------------------------------------------------------------------------- #
#  Fixed protocol constants                                                    #
# --------------------------------------------------------------------------- #
#
# These are the choices protocol_validation.py exists to test.

N_ELECTORS = 2000     # population size
M_RUNOFF   = 2        # French two-round rule
TMAX       = 25       # iteration ceiling
XI         = 0.0      # electorate mode position (symmetric benchmark)
N_MODES    = 1        # unimodal electorate

# --------------------------------------------------------------------------- #
#  Electorate-width strata                                                     #
# --------------------------------------------------------------------------- #
#
# c is the parameter every protocol question turns on: panels B and G both show
# that behaviour at high width differs in kind, not just degree.  Validation
# designs stratify on it so no regime can be missed by chance.

C_STRATA = {
    "low":    (0.25, 1.25),   # [lo, hi)
    "medium": (1.25, 2.00),
    "high":   (2.00, 3.00),   # closed at the top
}


def c_stratum(c: float) -> str:
    """Name the electorate-width stratum a value of c falls in."""
    for name, (lo, hi) in C_STRATA.items():
        if lo <= c < hi:
            return name
    if c == C_STRATA["high"][1]:      # closed upper bound
        return "high"
    raise ValueError(f"c={c} is outside the Saltelli bound {bounds_for('c')}")


def bounds_for(name: str) -> list:
    """Bounds of one named parameter."""
    return PROBLEM["bounds"][PROBLEM["names"].index(name)]


def within_bounds(name: str, value: float) -> bool:
    lo, hi = bounds_for(name)
    return lo <= value <= hi


# --------------------------------------------------------------------------- #
#  Signal offset: what is ACTUALLY in force                                    #
# --------------------------------------------------------------------------- #

def signal_epsilon_in_force() -> float:
    """
    The signal offset eps_s the model actually applies, read from the default
    of ``signals.generate_signal`` rather than assumed.

    A lookup rather than a constant, so it cannot drift out of step with the
    function it describes.  This is the value a caller gets by NOT passing
    ``signal_epsilon``; a caller that passes one should record what it passed.
    """
    import inspect

    from core_model import signals as _signals

    return float(inspect.signature(_signals.generate_signal)
                 .parameters["eps"].default)


def signal_epsilon_is_settable() -> bool:
    """
    True when eps_s can be set through run_simulation.  It can, since the
    signal_epsilon parameter was added; kept so callers can check rather than
    assume.
    """
    import inspect

    from core_model.model import run_simulation

    params = inspect.signature(run_simulation).parameters
    return any(p in params for p in ("eps", "eps_signal", "signal_epsilon"))

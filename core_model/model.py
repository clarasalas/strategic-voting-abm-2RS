"""
model.py
--------
Main simulation loop for the strategic voting ABM.

Entry point
-----------
- run_simulation : run the full ABM for one parameter configuration and
                   return a results dict (see Returns section of its
                   docstring for the full key listing).

Execution flow
--------------
1.  Build K equal zones on [-1, 1]; party positions at zone midpoints.
2.  Build voter distribution (uniform or unimodal; see environment.py).
3.  Place N electors by sampling from the voter distribution.
4.  Iteration 0: sincere vote (argmax u_a); derive true support shares.
5.  Generate initial poll signal s^0 via temperature transform + Dirichlet draw.
6.  Generate fixed prior beliefs π_a ~ Dirichlet(ρ_π · s^0), once per elector.
7.  Strategic loop (t = 1 … T):
      a. t = 1: posterior m^0_{a,j} = π_{a,j}  (prior only, no signal mixing).
         t > 1: posterior m^t_{a,j} = α π_{a,j} + (1-α) s^t_j.
      b. All electors compute strategic utilities φ_a(j).
      c. Vote tallies recomputed via chooseCandidate.
      d. Signal refreshed from current vote shares starting at t = 2.
      e. Loop runs for exactly T iterations; there is no early stopping.

Signal model
------------
    s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)   (temperature transform)
    s   ~ Dirichlet(ρ · s̃)                            (Dirichlet draw)

θ < 1  →  coordination-enhancing signal (viability gaps amplified).
θ = 1  →  faithful signal (no distortion).
θ > 1  →  fragmentation-enhancing signal (viability gaps compressed).
ρ      →  signal precision; higher ρ means less noise.

Belief update
-------------
Priors are fixed at initialisation and do not evolve across iterations:

    π_a ~ Dirichlet(ρ_π · s^0)          (drawn once from the initial signal)

    m^0_{a,j} = π_{a,j}                  (first update = prior only)
    m^t_{a,j} = α π_{a,j} + (1-α) s^t_j  (t > 0: fixed-prior mixing rule)

α = 0  →  posterior equals the current signal (no prior inertia).
α = 1  →  posterior equals the fixed prior (signal ignored).
ρ_π < ρ (recommended)  →  prior less precise than the signal.

Diagnostics
-----------
Pass collect_diagnostics=True to instrument the run.  The return dict
will then include a "diagnostics" key with:

    s_tilde_0                                : np.ndarray (K,)
    iterations                               : list of dicts, one per strategic iter
    trigger_rate_final                       : float
    n_triggered_final                        : int
    conditional_switching_given_triggered    : float
    n_triggered_switched                     : int

Mu calibration
--------------
Pass collect_mu_calibration=True (with mu=0) to extract per-triggered-voter
data for calibrating the meaningful range of mu.  Adds a "mu_calibration" key:

    list of dicts, one per triggered voter, each containing:
        voter_id, j_star, j_alt, S_jstar, S_jalt, lambda_jalt, mu_crit

Only rows where lambda_jalt > 0 and S_jalt > S_jstar are included.
Should be run with mu=0 so strategic utilities equal raw strategic gains.
"""

import warnings

import numpy as np

from agents import Elector, Party
from environment import build_equal_zones, build_voter_distribution
from signals import generate_signal, rank_signal, transform_signal
import functions


def run_simulation(
        # --- Electoral environment ---
        K: int,
        party_ids: list = None,

        # --- Electorate distribution ---
        n_modes: int = 0,
        width_factor: float = 0.5,
        mode_position: float = None,
        floor_weight: float = 0.1,
        skewness: float = 0.0,

        # --- Signal ---
        theta: float = 1.0,
        rho: float = 100.0,

        # --- Prior ---
        rho_pi: float = 10.0,

        # --- Voter population ---
        n_electors: int = 1000,

        # --- Behaviour parameters ---
        tau: float = 2.0,
        mu: float = 0.0,
        alpha_prior: float = 0.0,
        K_runoff: int = 2,

        # --- ABM mechanics ---
        max_iterations: int = 10,
        seed: int = None,
        verbose: bool = True,

        # --- Diagnostics ---
        collect_diagnostics: bool = False,
        collect_mu_calibration: bool = False,

        # --- Empirical replay overrides (all default None = synthetic mode) ---
        party_positions_override: np.ndarray = None,
        voter_positions_override: np.ndarray = None,
        exogenous_signals: list = None,
) -> dict:
    """
    Run the strategic voting ABM for one parameter configuration.

    Parameters
    ----------
    K : int
        Number of parties.  Party positions are derived automatically
        as equally spaced kernels on [-1, 1].
    party_ids : list of str or None
        Labels used in reporting.  Defaults to ["0", "1", …].

    n_modes : int
        Voter placement type.
          0  →  uniform electorate.
          1  →  unimodal (single Gaussian or skew-normal).
    width_factor : float
        Mode width as a fraction of zone_length = 2/K.
        0.2 = cohesive bloc, 1.0 = diffuse.  Only used when n_modes=1.
    mode_position : float or None
        Centre of the unimodal mode.
        None  →  0.0 (ideological centre).
    floor_weight : float in [0, 1)
        Weight of the uniform floor component.  Recommended 0.05–0.15.
    skewness : float
        Skew-normal shape parameter α for the unimodal mode.
        0.0 = symmetric; < 0 = left-leaning; > 0 = right-leaning.

    theta : float
        Signal temperature.
    rho : float
        Dirichlet precision for the signal draw.
    rho_pi : float
        Dirichlet precision for the prior draw.
    n_electors : int
    tau : float
        Tolerance threshold for the Ca / Oa partition.
    mu : float
        Loyalty weight.  Use mu=0 with collect_mu_calibration=True.
    alpha_prior : float in [0, 1]
        Prior weight in Bayesian update.
    K_runoff : int
    max_iterations : int
        All simulations run the full T iterations; no early stopping.
    seed : int or None
    verbose : bool
    collect_diagnostics : bool
    collect_mu_calibration : bool
        Extract per-triggered-voter data for mu range calibration.
        Should be used with mu=0.

    Returns
    -------
    dict — see module docstring for full key listing.
    """
    if K < 1:
        raise ValueError("K must be at least 1.")
    if party_ids is None:
        party_ids = [str(i) for i in range(K)]

    # ------------------------------------------------------------------ #
    # Empirical replay mode                                               #
    # ------------------------------------------------------------------ #
    # When override arrays are supplied the model uses empirical party
    # positions, empirical voter positions, and/or an exogenous poll-signal
    # timeline instead of the synthetic generators.  All three default to
    # None, in which case behaviour is identical to the original model.
    if party_positions_override is not None:
        party_positions_override = np.asarray(party_positions_override,
                                              dtype=float)
        if len(party_positions_override) != K:
            raise ValueError(
                f"party_positions_override has length "
                f"{len(party_positions_override)} but K={K}."
            )
    if voter_positions_override is not None:
        voter_positions_override = np.asarray(voter_positions_override,
                                              dtype=float)
        # n_electors is driven by the empirical voter sample.
        n_electors = len(voter_positions_override)
    if exogenous_signals is not None:
        exogenous_signals = [np.asarray(s, dtype=float)
                             for s in exogenous_signals]
        if len(exogenous_signals) == 0:
            raise ValueError("exogenous_signals must be non-empty.")

    rng = np.random.default_rng(seed)
    signal_rng = np.random.default_rng(seed + 1 if seed is not None else None)

    if tau >= 2.0:
        warnings.warn(
            f"tau={tau:.2f} >= 2.0: every party is a contender for every "
            f"voter and the Ca/Oa distinction is disabled.  "
            f"Consider tau relative to zone_length 2/K = {2 / K:.3f}.",
            UserWarning,
            stacklevel=2,
        )

    # ------------------------------------------------------------------ #
    # 1. Equal-zone ideological space                                     #
    # ------------------------------------------------------------------ #
    env = build_equal_zones(K, space=(-1.0, 1.0))
    party_intervals = env["party_intervals"]
    party_positions = env["party_positions"]

    # Empirical positions replace the equal-zone kernels.  zone_length is
    # kept at 2/K so the mu expressive-cost normalisation stays comparable
    # to the synthetic experiments.
    if party_positions_override is not None:
        party_positions = party_positions_override

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Strategic Voting ABM  |  K={K}  N={n_electors}")
        print(f"  tau={tau:.3f}  mu={mu:.2f}  alpha_prior={alpha_prior:.2f}")
        print(f"  theta={theta}  rho={rho}  rho_pi={rho_pi}  K_runoff={K_runoff}")
        print(f"  n_modes={n_modes}  width_factor={width_factor}  "
              f"skewness={skewness}")
        print(f"{'=' * 60}")
        for j in range(K):
            l, r = party_intervals[j]
            print(f"  Party {party_ids[j]:>4s}: "
                  f"zone [{l:+.3f}, {r:+.3f}]  "
                  f"kernel {party_positions[j]:+.3f}")

    # ------------------------------------------------------------------ #
    # 2. Voter distribution for voter placement                           #
    # ------------------------------------------------------------------ #
    voter_dist = build_voter_distribution(
        K=K,
        n_modes=n_modes,
        width_factor=width_factor,
        mode_position=mode_position,
        floor_weight=floor_weight,
        skewness=skewness,
        space=(-1.0, 1.0),
    )

    if verbose and n_modes == 1:
        print(f"\n  Mode position : "
              f"{voter_dist['mode_positions'][0]:+.3f}")
        print(f"  Mode width    : "
              f"{voter_dist['mode_widths'][0]:.3f}  "
              f"(width_factor={width_factor}, zone_length={env['zone_length']:.3f})")
        print(f"  Skewness      : {skewness}")
        print(f"  Floor weight  : {floor_weight:.2f}  "
              f"({floor_weight * 100:.0f}% uniform draw)")
    elif verbose:
        print(f"\n  Voter placement: uniform on [-1, 1]")

    # ------------------------------------------------------------------ #
    # 3. Initialise parties and electors                                  #
    # ------------------------------------------------------------------ #
    allParties = [Party(j, party_positions[j]) for j in range(K)]
    allElectors = []
    for eid in range(n_electors):
        if voter_positions_override is not None:
            position = float(voter_positions_override[eid])
        else:
            position = functions.sample_from_distribution(voter_dist, rng)
        elector = Elector(eid, position, K, tau=tau)
        elector.calcSincereUtilities(allParties)
        allElectors.append(elector)

    # ------------------------------------------------------------------ #
    # 4. Iteration 0 — sincere vote                                       #
    # ------------------------------------------------------------------ #
    sincere_counts = functions.countVoteIntentions(
        allElectors, allParties, iteration=0
    )
    sincere_shares = functions.voteShares(sincere_counts, n_electors)
    true_support = np.array(sincere_shares, dtype=float)

    if verbose:
        functions.printElectionResults(
            allParties, sincere_counts, n_electors, iteration=0
        )

    # ------------------------------------------------------------------ #
    # 5. Initial poll signal                                              #
    # ------------------------------------------------------------------ #
    if exogenous_signals is not None:
        # s^0 is the first empirical poll signal; theta/rho are unused.
        signal = exogenous_signals[0].copy()
        if collect_diagnostics:
            s_tilde_0 = signal.copy()
    else:
        if collect_diagnostics:
            s_tilde_0 = transform_signal(true_support, theta=theta)

        signal = generate_signal(
            true_support,
            theta=theta,
            rho=rho,
            rng=signal_rng,
        )

    # ------------------------------------------------------------------ #
    # 6. Prior beliefs  π_a ~ Dirichlet(ρ_π · s^0)                       #
    # ------------------------------------------------------------------ #
    pi_priors = [
        functions.generate_prior(signal, rho_pi, signal_rng)
        for _ in range(n_electors)
    ]

    if verbose:
        ranking = rank_signal(signal)
        mean_prior = np.mean(pi_priors, axis=0)
        print(f"\n  True support   : "
              f"{dict(zip(party_ids, np.round(true_support, 3)))}")
        print(f"  Poll signal    : "
              f"{dict(zip(party_ids, np.round(signal, 3)))}")
        print(f"  Poll ranking   : {[party_ids[i] for i in ranking]}")
        print(f"  Mean prior (N={n_electors}): "
              f"{dict(zip(party_ids, np.round(mean_prior, 3)))}")

    # ------------------------------------------------------------------ #
    # 7. Strategic iteration loop                                         #
    # ------------------------------------------------------------------ #
    history = [sincere_counts[:]]
    sw_history = []
    current_counts = sincere_counts[:]

    # Track individual vote intentions at each iteration for convergence analysis.
    # intention_history[0] = sincere choices (iteration 0).
    # intention_history[t] = vote choices at strategic iteration t.
    sincere_intentions = np.array([
        e.sincereChoice for e in allElectors
    ], dtype=int)
    intention_history = [sincere_intentions.copy()]

    if collect_diagnostics:
        diag_iterations = []

    for iteration in range(1, max_iterations + 1):

        # Refresh signal each iteration.
        #   Empirical mode : pull the next exogenous poll signal s^t,
        #                    clamping to the last available signal once the
        #                    timeline is exhausted (hold-last behaviour).
        #   Synthetic mode : regenerate the signal from current vote shares.
        if exogenous_signals is not None:
            # iteration 1 is prior-only (belief_t=0), so the signal there is
            # never mixed; iteration t>=2 consumes exogenous_signals[t-1].
            # s0 (index 0) feeds the prior only.  Once the timeline is
            # exhausted the last signal is held (relevant only when
            # max_iterations exceeds the timeline length).
            idx = min(iteration - 1, len(exogenous_signals) - 1)
            signal = exogenous_signals[idx].copy()
        elif iteration > 1:
            cur = np.array(current_counts, dtype=float)
            total = cur.sum()
            cur_shares = cur / total if total > 0 else true_support
            signal = generate_signal(
                cur_shares, theta=theta, rho=rho, rng=signal_rng,
            )

        # Belief update:
        #   iteration=1  →  belief_t=0  →  m^0 = π_a  (no signal mixing)
        #   iteration>1  →  belief_t>0  →  m^t = α π + (1-α) s^t
        belief_t = iteration - 1
        for elector, pi_prior in zip(allElectors, pi_priors):
            elector.updateBeliefs(signal, alpha_prior, pi_prior,
                                  iteration=belief_t)
            elector.calcStrategicUtilities(
                allParties, mu=mu, K_runoff=K_runoff,
                zone_length=env["zone_length"],
            )

        current_counts = functions.countVoteIntentions(
            allElectors, allParties, iteration=iteration
        )
        history.append(current_counts[:])

        # Record individual intentions for fixed-point convergence detection.
        current_intentions = np.array([
            e.chooseCandidate(allParties, iteration).ID
            for e in allElectors
        ], dtype=int)
        intention_history.append(current_intentions)

        sw = functions.summariseStrategicSwitching(allElectors, allParties)
        sw_history.append(sw["pct_strategic"] * 100)

        if collect_diagnostics:
            n_triggered = sum(1 for e in allElectors if e.triggered)
            top_M_set = tuple(sorted(
                int(i) for i in np.argsort(-signal)[:K_runoff]
            ))
            diag_iterations.append({
                "t": iteration,
                "trigger_rate": n_triggered / n_electors,
                "n_triggered": n_triggered,
                "top_M_set": top_M_set,
                "signal": signal.copy(),
            })

        if verbose:
            functions.printElectionResults(
                allParties, current_counts, n_electors, iteration=iteration
            )

    # ------------------------------------------------------------------ #
    # 8. Summary                                                          #
    # ------------------------------------------------------------------ #
    switching = functions.summariseStrategicSwitching(allElectors, allParties)
    winner = functions.getWinner(allParties, current_counts)
    n_iters = len(history) - 1
    final_shares = functions.voteShares(current_counts, n_electors)

    if verbose:
        print(f"\n  Vote breakdown : {switching}")
        if winner:
            print(f"  First-round leader: Party '{party_ids[winner.ID]}' "
                  f"(pos={winner.position:+.3f})")
        print(f"  Completed {n_iters} strategic iteration(s).")

    # ── Diagnostics ──────────────────────────────────────────────────────
    diagnostics = None
    if collect_diagnostics:
        n_triggered_final = sum(1 for e in allElectors if e.triggered)
        n_triggered_switched = sum(
            1 for e in allElectors
            if e.triggered
            and e.chooseCandidate(allParties, iteration=1).ID != e.sincereChoice
        )
        diagnostics = {
            "s_tilde_0": s_tilde_0,
            "iterations": diag_iterations,
            "trigger_rate_final": n_triggered_final / n_electors,
            "n_triggered_final": n_triggered_final,
            "conditional_switching_given_triggered": (
                n_triggered_switched / n_triggered_final
                if n_triggered_final > 0 else 0.0
            ),
            "n_triggered_switched": n_triggered_switched,
        }

    # ── Mu calibration ───────────────────────────────────────────────────
    mu_calibration = None
    if collect_mu_calibration:
        ell_sq = env["zone_length"] ** 2
        rows = []
        for e in allElectors:
            if not e.triggered:
                continue
            j_star = e.sincereChoice
            alts = [j for j in e.contenders if j != j_star]
            if not alts:
                continue
            # best alternative by strategic gain (phi, which = sa when mu=0)
            j_alt = max(alts, key=lambda j: e.strategicUtilities[j])
            S_jstar = e.strategicUtilities[j_star]
            S_jalt = e.strategicUtilities[j_alt]
            lam = ((e.sincereUtilities[j_star] - e.sincereUtilities[j_alt])
                   / ell_sq)
            if lam > 0 and S_jalt > S_jstar:
                mu_crit = (S_jalt - S_jstar) / lam
                rows.append({
                    "voter_id": e.ID,
                    "j_star": j_star,
                    "j_alt": j_alt,
                    "S_jstar": float(S_jstar),
                    "S_jalt": float(S_jalt),
                    "S_diff": float(S_jalt - S_jstar),
                    "lambda_jalt": float(lam),
                    "mu_crit": float(mu_crit),
                })
        mu_calibration = rows

    return {
        "party_positions": party_positions,
        "voter_dist": voter_dist,
        "sincere_counts": sincere_counts,
        "sincere_shares": sincere_shares,
        "history": history,
        "intention_history": intention_history,
        "sw_history": sw_history,
        "final_counts": current_counts,
        "final_shares": final_shares,
        "iterations": n_iters,
        "winner_id": winner.ID if winner is not None else None,
        "signal": signal,
        "pi_priors": pi_priors,
        "switching": switching,
        "diagnostics": diagnostics,
        "mu_calibration": mu_calibration,
    }

"""
model.py
--------
Main simulation loop for the strategic voting ABM.

Entry point
-----------
- run_simulation : run the ABM for one parameter configuration and return a
                   results dict.  Its docstring lists every key.

Execution flow
--------------
1.  Build K equal zones on [-1, 1]; party positions at the zone midpoints.
2.  Build the voter distribution (uniform or unimodal; see environment.py).
3.  Place N electors by sampling from it.
4.  Iteration 0: sincere vote (argmax u_a), giving the true support shares.
5.  Draw the initial poll signal s^0: temperature transform, then Dirichlet.
6.  Draw fixed prior beliefs π_a ~ Dirichlet(ρ_π · s^0), once per elector.
7.  Strategic loop (t = 1 … T):
      a. t = 1: posterior m^0_{a,j} = π_{a,j}, prior only, no signal mixing.
         t > 1: posterior m^t_{a,j} = α π_{a,j} + (1-α) s^t_j.
      b. Every elector computes its strategic utilities φ_a(j).
      c. chooseCandidate retallies the votes.
      d. From t = 2 the signal is refreshed from the current vote shares.
      e. The loop always runs T iterations.  Nothing stops it early.

Signal model
------------
    s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)   (temperature transform)
    s   ~ Dirichlet(ρ · s̃)                            (Dirichlet draw)

θ shapes the signal and ρ sets its precision.  signals.py says what each
value does.

Belief update
-------------
Priors are drawn once at initialisation and never move:

    π_a ~ Dirichlet(ρ_π · s^0)          (drawn from the initial signal)

    m^0_{a,j} = π_{a,j}                  (first update, prior only)
    m^t_{a,j} = α π_{a,j} + (1-α) s^t_j  (t > 0, fixed-prior mixing)

At α = 0 the posterior is the current signal; at α = 1 it is the fixed prior
and the campaign is ignored.  ρ_π < ρ keeps the prior less precise than the
signal, which is the intended regime.

Diagnostics
-----------
collect_diagnostics=True instruments the run and adds a "diagnostics" key:

    s_tilde_0                                : np.ndarray (K,)
    iterations                               : list of dicts, one per strategic iter
    trigger_rate_final                       : float
    n_triggered_final                        : int
    conditional_switching_given_triggered    : float
    n_triggered_switched                     : int

Mu calibration
--------------
collect_mu_calibration=True, with mu=0, adds a "mu_calibration" key holding
one row per triggered voter, for working out the useful range of mu:

    list of dicts, one per triggered voter, each containing:
        voter_id, j_star, j_alt, S_jstar, S_jalt, lambda_jalt, mu_crit

Rows appear only where lambda_jalt > 0 and S_jalt > S_jstar.  Run it with
mu=0, so the strategic utilities are the raw strategic gains.
"""

import warnings

import numpy as np

from .agents import Elector, Party
from .environment import build_equal_zones, build_voter_distribution
from .signals import generate_signal, rank_signal, transform_signal
from . import functions


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
        signal_epsilon: float = 1e-12,

        # --- Prior ---
        rho_pi: float = 10.0,

        # --- Voter population ---
        n_electors: int = 1000,

        # --- Behaviour parameters ---
        tau: float = 2.0,
        mu: float = 0.0,
        alpha_prior: float = 0.0,
        K_runoff: int = 2,

        # --- Sincere initialization rule ---
        sincere_init_mode: str = "nearest",
        beta: float = 0.0,
        salience_source: str = "signal",

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
        Weight of the uniform floor component.  Recommended 0.05-0.15.
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
    sincere_init_mode : {"nearest", "probabilistic"}
        Rule for each voter's initial expressive party (iteration 0).
          "nearest"       : deterministic argmax_j u_a(j).  The default.
          "probabilistic" : draw the initial party from the contender set Ca,
                            with P_a(j) ∝ salience_{a,j} · exp(-beta·(x_a-x_j)^2).
        The drawn party becomes the iteration-0 vote, the switching reference,
        and the anchor of the expressive cost.
    beta : float >= 0
        Ideological sharpness inside Ca for probabilistic initialization.
        Ignored when sincere_init_mode == "nearest".  beta = 0 → salience-only
        draw; large beta → collapses onto the nearest contender.
    salience_source : {"signal", "prior"}
        Salience used in the probabilistic draw.
          "signal" (default) : the shared first public signal s^0_j.
          "prior"            : the voter's own prior pi_{a,j}.
        Ignored when sincere_init_mode == "nearest".
    K_runoff : int
    max_iterations : int
        All simulations run the full T iterations; no early stopping.
    seed : int or None
    verbose : bool
    collect_diagnostics : bool
    collect_mu_calibration : bool
        Extract per-triggered-voter data for mu range calibration.
        Should be used with mu=0.
    signal_epsilon : float, default 1e-12
        Numerical FLOOR added to each share before the temperature
        exponentiation in the signal transform:

            s~_i = (delta_i + signal_epsilon)^(1/theta) / sum_j (...)

        It gives ZERO-SUPPORT COMPONENTS a strictly positive Dirichlet
        concentration.  The signal is drawn as s ~ Dirichlet(rho*s~), so
        without the floor a party at zero support has concentration exactly
        zero, its sampled share stays pinned at zero however the race moves,
        and it can never be reported as viable.  (0^(1/theta) is finite, so
        that is not the failure being guarded against.)  An ALL-zero support
        vector is a separate case, caught by generate_signal's uniform
        fallback (delta = ones/K when the total is zero).

        Must be finite and non-negative.  1e-12 is the fixed synthetic
        specification, the value every committed result was produced under,
        and changing it changes the signal and so the run.  It is not a
        behavioural parameter, and it is NOT the Saltelli parameter named
        ``epsilon``, which is the electorate floor weight eps_F passed as
        ``floor_weight``.

        Synthetic runs only.  With ``exogenous_signals`` the polls are given,
        nothing is generated, and this has no effect.

    Returns
    -------
    dict.  The module docstring lists every key.
    """
    if K < 1:
        raise ValueError("K must be at least 1.")
    if party_ids is None:
        party_ids = [str(i) for i in range(K)]

    if sincere_init_mode not in ("nearest", "probabilistic"):
        raise ValueError(
            f"sincere_init_mode must be 'nearest' or 'probabilistic', "
            f"got {sincere_init_mode!r}."
        )
    if salience_source not in ("signal", "prior"):
        raise ValueError(
            f"salience_source must be 'signal' or 'prior', "
            f"got {salience_source!r}."
        )
    if sincere_init_mode == "probabilistic" and beta < 0:
        raise ValueError(f"beta must be >= 0, got {beta}.")

    # ------------------------------------------------------------------ #
    # Empirical replay mode                                               #
    # ------------------------------------------------------------------ #
    # Override arrays swap in empirical party positions, empirical voter
    # positions and an exogenous poll timeline, in any combination, in place
    # of the synthetic generators.  All three default to None.
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
    # Its own stream for the probabilistic initialization draws, kept apart
    # from voter placement (rng) and signal/prior draws (signal_rng), so a
    # fixed seed reproduces the initialization exactly.
    init_rng = np.random.default_rng(seed + 2 if seed is not None else None)

    if not np.isfinite(signal_epsilon) or signal_epsilon < 0:
        raise ValueError(
            f"signal_epsilon must be finite and non-negative, got "
            f"{signal_epsilon!r}. It is a numerical floor on the signal "
            f"transform, not a behavioural parameter."
        )

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
    # 4. Nearest-party support (basis for the signal in synthetic mode)   #
    # ------------------------------------------------------------------ #
    # No expressive attachment has been drawn yet, so this tally is the
    # deterministic nearest-party vote.  In synthetic mode it is the true
    # support that seeds the poll signal.  Under probabilistic init the
    # official iteration-0 shares are recomputed in step 6b, once the
    # attachments exist.
    nearest_counts = functions.countVoteIntentions(
        allElectors, allParties, iteration=0
    )
    true_support = np.array(
        functions.voteShares(nearest_counts, n_electors), dtype=float
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
            s_tilde_0 = transform_signal(true_support, theta=theta,
                                         eps=signal_epsilon)

        signal = generate_signal(
            true_support,
            theta=theta,
            rho=rho,
            eps=signal_epsilon,
            rng=signal_rng,
        )

    # ------------------------------------------------------------------ #
    # 6. Prior beliefs  π_a ~ Dirichlet(ρ_π · s^0)                       #
    # ------------------------------------------------------------------ #
    pi_priors = [
        functions.generate_prior(signal, rho_pi, signal_rng)
        for _ in range(n_electors)
    ]

    # ------------------------------------------------------------------ #
    # 6b. Probabilistic sincere initialization (optional)                 #
    # ------------------------------------------------------------------ #
    # Draw each voter's initial expressive party from Ca with probabilities
    #     P_a(j) ∝ salience_{a,j} · exp(-beta · (x_a - x_j)^2).
    # The drawn party replaces the nearest one as the iteration-0 vote and as
    # the anchor of the expressive cost.  "nearest" mode leaves
    # expressiveChoice unset.
    if sincere_init_mode == "probabilistic":
        for idx, elector in enumerate(allElectors):
            salience = signal if salience_source == "signal" else pi_priors[idx]
            elector.drawInitialAttachment(
                party_positions, salience, beta, init_rng
            )

    # ------------------------------------------------------------------ #
    # 6c. Iteration 0: the official initial (expressive) vote              #
    # ------------------------------------------------------------------ #
    # Follows whichever initialization rule is active: nearest-party, or the
    # drawn attachments.
    sincere_counts = functions.countVoteIntentions(
        allElectors, allParties, iteration=0
    )
    sincere_shares = functions.voteShares(sincere_counts, n_electors)

    if verbose:
        functions.printElectionResults(
            allParties, sincere_counts, n_electors, iteration=0
        )

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

    # Per-voter intentions each iteration, for convergence analysis.
    #   intention_history[0] = sincere choices (iteration 0)
    #   intention_history[t] = vote choices at strategic iteration t
    sincere_intentions = np.array([
        e.sincereChoice for e in allElectors
    ], dtype=int)
    intention_history = [sincere_intentions.copy()]

    if collect_diagnostics:
        diag_iterations = []

    for iteration in range(1, max_iterations + 1):

        # Refresh the signal.
        #   Empirical : take the next exogenous poll s^t, holding the last one
        #               once the timeline runs out.
        #   Synthetic : regenerate it from the current vote shares.
        if exogenous_signals is not None:
            # Iteration 1 is prior-only (belief_t=0), so nothing is mixed
            # there; from t>=2 the update takes exogenous_signals[t-1].
            # Index 0 feeds the prior alone.  Holding the last signal matters
            # only when max_iterations runs past the timeline.
            idx = min(iteration - 1, len(exogenous_signals) - 1)
            signal = exogenous_signals[idx].copy()
        elif iteration > 1:
            cur = np.array(current_counts, dtype=float)
            total = cur.sum()
            cur_shares = cur / total if total > 0 else true_support
            signal = generate_signal(
                cur_shares, theta=theta, rho=rho,
                eps=signal_epsilon, rng=signal_rng,
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

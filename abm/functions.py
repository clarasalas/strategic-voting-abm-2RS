"""
functions.py
------------
Utility functions for the strategic voting ABM.

Covers:
  - Voter placement (sample_from_distribution)
  - Prior generation
  - Vote counting
  - Output / reporting
  - Coordination outcome measures
"""

import numpy as np
from scipy.stats import skewnorm as _skewnorm


# =========================================================================== #
#  VOTER PLACEMENT                                                             #
# =========================================================================== #

def sample_from_distribution(attractor_dist: dict, rng) -> float:
    """
    Sample one voter position from a voter distribution dict.

    n_modes = 0  ->  pure uniform draw on [xmin, xmax].
    n_modes = 1  ->  single Gaussian (or skew-normal) + optional
                     uniform floor:
        p(x) = (1 - floor_weight) * SN(x) + floor_weight * U[xmin, xmax]
    """
    xmin, xmax = attractor_dist["space"]
    floor_weight = attractor_dist.get("floor_weight", 0.0)

    if attractor_dist["n_modes"] == 0:
        return float(rng.uniform(xmin, xmax))

    if floor_weight > 0.0 and rng.random() < floor_weight:
        return float(rng.uniform(xmin, xmax))

    mu = attractor_dist["mode_positions"][0]
    sigma = attractor_dist["mode_widths"][0]
    skewness = attractor_dist.get("skewness", 0.0)

    if skewness != 0.0:
        pos = float(_skewnorm.rvs(a=skewness, loc=mu, scale=sigma,
                                  random_state=rng))
    else:
        pos = float(rng.normal(mu, sigma)) if sigma > 0.0 else mu

    return float(np.clip(pos, xmin, xmax))


# =========================================================================== #
#  PRIOR GENERATION                                                            #
# =========================================================================== #

def generate_prior(
        signal: np.ndarray,
        rho_pi: float,
        rng,
) -> np.ndarray:
    """
    Generate a heterogeneous prior belief from the initial poll signal.

        pi_a ~ Dirichlet(rho_pi * s^0)

    Parameters
    ----------
    signal : array (K,)  -- initial poll signal s^0 (Dirichlet centre).
    rho_pi : float        -- prior precision (> 0).
    rng    : np.random.Generator

    Returns
    -------
    np.ndarray (K,)  -- normalised prior belief vector summing to 1.
    """
    signal = np.asarray(signal, dtype=float)
    K = len(signal)

    s = np.clip(signal, 0.0, None)
    s = s / s.sum() if s.sum() > 0 else np.ones(K) / K

    concentration = np.maximum(rho_pi * s, 1e-8)
    return rng.dirichlet(concentration)


# =========================================================================== #
#  VOTE COUNTING                                                               #
# =========================================================================== #

def countVoteIntentions(electors, parties, iteration):
    for party in parties:
        party.voteIntention = 0
    for elector in electors:
        elector.chooseCandidate(parties, iteration).voteIntention += 1
    return [p.voteIntention for p in parties]


def voteShares(vote_counts, n_electors):
    if n_electors == 0:
        return [0.0] * len(vote_counts)
    return [v / n_electors for v in vote_counts]


# =========================================================================== #
#  REPORTING                                                                   #
# =========================================================================== #

def printElectionResults(parties, vote_counts, n_electors, iteration):
    print(f"\n{'─' * 52}")
    print(f"  Iteration {iteration}")
    print(f"{'─' * 52}")
    for party, count in zip(parties, vote_counts):
        share = count / n_electors * 100 if n_electors > 0 else 0.0
        print(f"  Party {party.ID}  (pos={party.position:+.3f}): "
              f"{count:5d}  ({share:5.1f}%)")
    print(f"{'─' * 52}")


def getWinner(parties, vote_counts):
    if not vote_counts or max(vote_counts) == 0:
        return None
    return parties[int(np.argmax(vote_counts))]


def summariseStrategicSwitching(electors, parties) -> dict:
    """
    Compare each elector's sincere choice to their strategic choice.
    Delegates to chooseCandidate(iteration=1) so the choice rule is
    never duplicated.
    """
    sincere = strategic = 0
    for e in electors:
        best_j = e.chooseCandidate(parties, iteration=1).ID
        if best_j == e.sincereChoice:
            sincere += 1
        else:
            strategic += 1
    n = sincere + strategic
    return {
        "sincere": sincere,
        "strategic": strategic,
        "pct_strategic": strategic / n if n > 0 else 0.0,
    }


# =========================================================================== #
#  COORDINATION OUTCOME MEASURES                                               #
# =========================================================================== #

def coordination_measures(sincere_shares, final_shares) -> dict:
    """
    Compute coordination outcome measures as defined in the paper.

    Parameters
    ----------
    sincere_shares : array-like (K,)
        Vote shares from the sincere-voting benchmark (iteration 0).
    final_shares : array-like (K,)
        Vote shares from the final strategic iteration.

    Returns
    -------
    dict with keys:
        enp_sincere   : float  — ENP under sincere voting
        enp_final     : float  — ENP under final strategic voting
        cenp_sincere  : float  — CENP = (K - ENP) / (K-1) under sincere voting
        cenp_final    : float  — CENP under final strategic voting
        delta_cenp    : float  — coordination gain = cenp_final - cenp_sincere
                                 = (enp_sincere - enp_final) / (K - 1)
                                 Positive → strategic voting increased concentration.
        k_star_final  : int    — cliff location in final distribution
        d_star_final  : float  — largest consecutive drop in final distribution
        r_prime_final : float  — bounded cliff ratio in final distribution
        delta_d_star  : float  — change in cliff magnitude (final - sincere)
        delta_r_prime : float  — change in cliff ratio (final - sincere)
    """
    sincere_shares = np.asarray(sincere_shares, dtype=float)
    final_shares = np.asarray(final_shares, dtype=float)

    K = len(final_shares)

    # Normalise to valid probability vectors
    if sincere_shares.sum() > 0:
        sincere_shares = sincere_shares / sincere_shares.sum()
    if final_shares.sum() > 0:
        final_shares = final_shares / final_shares.sum()

    # ── ENP and CENP ─────────────────────────────────────────────────────
    def _enp(shares):
        sq = (shares ** 2).sum()
        return 1.0 / sq if sq > 0 else np.nan

    def _cenp(shares):
        """CENP = (K - ENP) / (K - 1): 0 under uniform, 1 under full concentration."""
        e = _enp(shares)
        return (K - e) / (K - 1) if K > 1 else np.nan

    enp_sincere = _enp(sincere_shares)
    enp_final = _enp(final_shares)
    cenp_sincere = _cenp(sincere_shares)
    cenp_final = _cenp(final_shares)
    delta_cenp = cenp_final - cenp_sincere  # = (enp_sincere - enp_final) / (K-1)

    # ── Cliff statistics ─────────────────────────────────────────────────
    def _cliff_stats(shares):
        """
        k_star : number of parties above the largest consecutive drop
        d_star : magnitude of that drop
        r_prime: bounded cliff ratio = d_star / (d_star + mean of other drops)
                 Values close to 1 → sharp cliff; close to 0.5 → diffuse.
        """
        sorted_sh = np.sort(shares)[::-1]
        if len(sorted_sh) < 2:
            return 1, 0.0, 0.5
        drops = sorted_sh[:-1] - sorted_sh[1:]
        idx = int(np.argmax(drops))
        k_star = idx + 1
        d_star = drops[idx]
        rest = np.concatenate([drops[:idx], drops[idx + 1:]])
        rest_mean = rest.mean() if len(rest) > 0 else 0.0
        r_prime = (d_star / (d_star + rest_mean)
                   if (d_star + rest_mean) > 0 else 0.5)
        return k_star, d_star, r_prime

    k_sincere, d_sincere, r_sincere = _cliff_stats(sincere_shares)
    k_final, d_final, r_final = _cliff_stats(final_shares)

    return {
        "enp_sincere": enp_sincere,
        "enp_final": enp_final,
        "cenp_sincere": cenp_sincere,
        "cenp_final": cenp_final,
        "delta_cenp": delta_cenp,
        "k_star_final": k_final,
        "d_star_final": d_final,
        "r_prime_final": r_final,
        "delta_d_star": d_final - d_sincere,
        "delta_r_prime": r_final - r_sincere,
    }

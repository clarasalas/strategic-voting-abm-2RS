import numpy as np


class Party:
    """
    A political party with a fixed ideological position.

    Attributes
    ----------
    ID            : int
    position      : float  — ideological position x_j in [-1, 1]
    voteIntention : int    — vote count in the current iteration
    """

    def __init__(self, partyID: int, position: float):
        self.ID = partyID
        self.position = float(position)
        self.voteIntention = 0

    def __repr__(self):
        return f"Party(id={self.ID}, pos={self.position:.3f})"


class Elector:
    """
    A voter on the ideological interval [-1, 1].

    Decision pipeline (per iteration t > 0)
    ----------------------------------------
    1. calcSincereUtilities   — u_a(j) = -(x_a - x_j)^2 ; build Ca / Oa
    2. updateBeliefs          — m_{a,j} = alpha*pi_{a,j} + (1-alpha)*s^0_j
    3. calcStrategicUtilities — phi_a(j) = S_a(j) - mu*lambda_a(j*)
    4. chooseCandidate        — argmax_{j in Ca} phi_a(j)

    Parameters
    ----------
    electorID : int
    position  : float
    nParty    : int
    tau       : float
        Tolerance threshold.  Parties with |x_j - x_a| <= tau are
        contenders (Ca); those beyond are opponents (Oa).
        Default 2.0 puts every party in Ca for any voter on [-1, 1].
    """

    def __init__(self, electorID: int, position: float,
                 nParty: int, tau: float = 2.0):
        self.ID = electorID
        self.position = float(position)
        self.nParty = nParty
        self.tau = tau

        self.sincereUtilities = np.zeros(nParty)
        self.posteriorBeliefs = np.ones(nParty) / nParty  # m_{a,j}
        self.strategicUtilities = np.full(nParty, -np.inf)

        self.contenders: list[int] = []  # Ca
        self.opponents: list[int] = []  # Oa

        # ── Diagnostic attribute ─────────────────────────────────────────────
        # Set by calcStrategicUtilities each iteration.
        # True  ↔  G_a = 1: Ca ∩ T_R = ∅, voter has a strategic incentive.
        # False ↔  G_a = 0: Ca ∩ T_R ≠ ∅, voter votes sincerely.
        self.triggered: bool = False

    # ------------------------------------------------------------------ #
    # Step 1 — Sincere utilities and Ca / Oa partition                    #
    # ------------------------------------------------------------------ #

    def calcSincereUtilities(self, parties: list) -> None:
        """
        u_a(j) = -(x_a - x_j)^2  for every party j.
        Also builds Ca and Oa from self.tau.
        """
        for j, party in enumerate(parties):
            self.sincereUtilities[j] = -(self.position - party.position) ** 2
        self._updatePartition(parties)

    def _updatePartition(self, parties: list) -> None:
        """
        Ca = { j : |x_a - x_j| <= tau }
        Oa = { j : |x_a - x_j| >  tau }

        Invariant: sincere choice j* is always in Ca.
        """
        self.contenders = [
            j for j, p in enumerate(parties)
            if abs(self.position - p.position) <= self.tau
        ]
        self.opponents = [
            j for j, p in enumerate(parties)
            if abs(self.position - p.position) > self.tau
        ]

        # Guarantee j* in Ca
        j_star = int(np.argmax(self.sincereUtilities))
        if j_star not in self.contenders:
            self.contenders.append(j_star)
            if j_star in self.opponents:
                self.opponents.remove(j_star)

        if not self.contenders:  # degenerate safety
            self.contenders = list(range(self.nParty))
            self.opponents = []

    # ------------------------------------------------------------------ #
    # Step 2 — Bayesian belief update                                     #
    # ------------------------------------------------------------------ #

    def updateBeliefs(
            self,
            signal: np.ndarray,
            alpha_prior: float,
            pi_prior: np.ndarray,
            iteration: int = 1,
    ) -> None:
        """
        Posterior belief update with fixed prior (Section 3.2):

            t = 0:  m^0_{a,j} = pi_{a,j}
            t > 0:  m^t_{a,j} = alpha_a * pi_{a,j} + (1 - alpha_a) * s^t_j

        At t = 0 the posterior is set directly to the voter's fixed prior
        pi_a, avoiding a double-mixing of the initial signal (pi_a is already
        derived from s^0 via generate_prior, so blending s^0 in again would
        count it twice).

        At t > 0 the posterior is formed by mixing the voter's fixed prior
        pi_a with the *current* public signal s^t.  The previous posterior
        m^{t-1} is never reused — prior inertia is anchored to pi_a, not to
        the evolving belief state.

        s^t is clipped to non-negative and normalised before mixing.
        Because Dirichlet signal draws are already non-negative and sum
        to 1, clipping is a no-op under the current signal model but is
        kept for robustness.

        Parameters
        ----------
        signal      : array (K,) — current poll signal s^t (Dirichlet draw)
        alpha_prior : float in [0, 1]
            Weight on the fixed prior pi_a.
            0 = ignore prior, trust signal fully.
            1 = ignore signal, keep prior unchanged.
        pi_prior    : array (K,) — voter's fixed prior beliefs pi_a
                      (normalised internally).
        iteration   : int
            Current iteration index.  When 0, posterior is set to pi_a
            directly and the signal is ignored.
        """
        pi_prior = np.asarray(pi_prior, dtype=float)
        pi = pi_prior / pi_prior.sum() if pi_prior.sum() > 0 \
            else np.ones(self.nParty) / self.nParty

        if iteration == 0:
            self.posteriorBeliefs = pi
            return

        signal = np.asarray(signal, dtype=float)
        s = np.clip(signal, 0.0, None)
        s = s / s.sum() if s.sum() > 0 else np.ones(self.nParty) / self.nParty

        self.posteriorBeliefs = alpha_prior * pi + (1.0 - alpha_prior) * s

    # ------------------------------------------------------------------ #
    # Step 3 — Strategic utilities                                        #
    # ------------------------------------------------------------------ #

    def _perceived_runoff_share(self, j: int, k: int, parties: list) -> float:
        """
        R_a(j | k): perceived share of the vote going to j in a j-vs-k runoff,
        given posterior beliefs m_{a,r} and party positions.

        Eliminated voters redistribute to whichever finalist is ideologically
        closest.  Exact ties split 50/50.

        Because posteriorBeliefs sums to 1, R_a(j|k) + R_a(k|j) = 1 always,
        so NV_{a,j,k} = R_a(j|k) directly.
        """
        K = len(parties)
        ra_j = self.posteriorBeliefs[j]
        ra_k = self.posteriorBeliefs[k]

        for r in range(K):
            if r == j or r == k:
                continue
            xr = parties[r].position
            d_j = abs(xr - parties[j].position)
            d_k = abs(xr - parties[k].position)
            if d_j < d_k:
                ra_j += self.posteriorBeliefs[r]
            elif d_k < d_j:
                ra_k += self.posteriorBeliefs[r]
            else:
                ra_j += 0.5 * self.posteriorBeliefs[r]
                ra_k += 0.5 * self.posteriorBeliefs[r]

        return ra_j  # in [0, 1]

    def calcStrategicUtilities(
            self,
            parties: list,
            mu: float = 0.0,
            K_runoff: int = 2,
            zone_length: float = None,
    ) -> None:
        """
        Compute phi_a(j) for every j in Ca, gated by the coordination
        indicator G_a from Section 3 of the paper.

        G_a = 1 iff Ca ∩ T_R = ∅
        --------------------------
        Let T_R = the R candidates with highest posterior poll support.
        If Ca ∩ T_R ≠ ∅, the voter's bloc already has a representative
        heading to the second round and no coordination is needed —
        the voter votes sincerely.
        If Ca ∩ T_R = ∅, no contender is projected to qualify and the
        voter has a genuine strategic incentive to deviate.

        Sets self.triggered = True when G_a = 1 (strategic incentive active),
        False otherwise.  This attribute is read by external diagnostics.

        Strategic utilities (when G_a = 1)
        -----------------------------------
        For j in Ca:
            phi_a(j)  = LV_{a,j} * NV_{a,j,k*} - mu * lambda_hat_a(j)
                                                        [j != j*]
            phi_a(j*) = LV_{a,j*} * NV_{a,j*,k*}

        where:
            LV_{a,j}        = m_{a,j} / sum_{r in Ca} m_{a,r}
            NV_{a,j,k*}     = R_a(j | k*)
            lambda_hat_a(j) = (u_a(j*) - u_a(j)) / ell^2  >= 0
            k*              = argmax_{k in Oa} m_{a,k}
            ell             = zone_length = 2/K

        The expressive cost is normalized by ell^2 to make mu comparable
        across simulations with different numbers of parties.

        Parameters
        ----------
        parties     : list of Party
        mu          : float  — loyalty weight (0 = no expressive cost)
        K_runoff    : int    — number of candidates advancing to round 2.
                               2 for presidential elections (default).
                               3 for legislative elections (triangulaires).
        zone_length : float  — inter-party spacing ell = 2/K, used to
                               normalize the expressive cost.
                               Defaults to 2/K if not supplied.
        """
        N = len(parties)
        j_star = int(np.argmax(self.sincereUtilities))
        phi = np.full(N, -np.inf)

        # Reset trigger flag at the start of each call.
        self.triggered = False

        # Normalisation factor: ell^2 = zone_length^2. Defaults to 2/K.
        if zone_length is None:
            zone_length = 2.0 / N
        ell_sq = zone_length ** 2

        # --- No opponents → sincere vote (G_a vacuously 0) ---
        if not self.opponents:
            phi[j_star] = 1.0
            self.strategicUtilities = phi
            return

        k_star = max(self.opponents, key=lambda k: self.posteriorBeliefs[k])

        sorted_by_belief = sorted(range(N), key=lambda j: -self.posteriorBeliefs[j])
        top_R = set(sorted_by_belief[:K_runoff])

        # ── G_a indicator: Ca ∩ T_R = ∅ ───────────────────────────────────
        if top_R & set(self.contenders):
            # G_a = 0: a contender is projected to qualify → sincere vote.
            phi[j_star] = 1.0
            self.strategicUtilities = phi
            return

        # ── G_a = 1: no contender projected to qualify → strategic vote ────
        self.triggered = True

        contender_mass = sum(self.posteriorBeliefs[j] for j in self.contenders)
        if contender_mass <= 0:
            contender_mass = 1.0

        for j in self.contenders:
            lv = self.posteriorBeliefs[j] / contender_mass
            nv = self._perceived_runoff_share(j, k_star, parties)
            sa = lv * nv
            penalty = (
                mu * (self.sincereUtilities[j_star] - self.sincereUtilities[j]) / ell_sq
                if j != j_star else 0.0
            )
            phi[j] = sa - penalty

        self.strategicUtilities = phi

    # ------------------------------------------------------------------ #
    # Step 4 — Vote choice                                                #
    # ------------------------------------------------------------------ #

    def chooseCandidate(self, parties: list, iteration: int) -> "Party":
        """
        t = 0  →  sincere vote: argmax_{j} u_a(j)
        t > 0  →  strategic vote: argmax_{j in Ca} phi_a(j)
        """
        if iteration == 0:
            return parties[int(np.argmax(self.sincereUtilities))]

        best_j = max(self.contenders, key=lambda j: self.strategicUtilities[j])
        return parties[best_j]

    # ------------------------------------------------------------------ #
    # Convenience properties                                              #
    # ------------------------------------------------------------------ #

    @property
    def sincereChoice(self) -> int:
        return int(np.argmax(self.sincereUtilities))

    @property
    def leastPreferred(self) -> int:
        return int(np.argmin(self.sincereUtilities))

    def __repr__(self) -> str:
        return (f"Elector(id={self.ID}, pos={self.position:.3f}, "
                f"tau={self.tau:.2f})")
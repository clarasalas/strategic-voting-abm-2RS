"""
test_decision_rule.py
---------------------
Direct, deterministic tests of the strategic decision rule and the contender
set -- the two pieces of Section 3 that every empirical number rests on and
that nothing in the suite exercised on their own.

Existing coverage stops at the ends of a run: tests/test_empirical.py checks
that final shares sum to one and that a repeat run is identical, and
tests/test_metrics.py checks ENP/CENP. Between them sat the rule itself:
whether G_a fires when it should, what the expressive cost does at its
boundary, and how Ca is built. A rule that triggered on the wrong condition
would still produce shares summing to one.

Everything here runs at the Elector level with beliefs supplied directly, so
there is no RNG anywhere and no simulation loop: each assertion is a closed-form
consequence of the equations in agents.py.

Fixture: five parties at -1, -0.5, 0, 0.5, 1 and one voter, chosen so no
distance and no belief is tied.

Run with:  pytest tests/test_decision_rule.py
"""

import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))

from agents import Party, Elector
from metrics import tau_absolute

POSITIONS = [-1.0, -0.5, 0.0, 0.5, 1.0]
K = len(POSITIONS)
ELL = 2.0 / K

# Distinct, summing to one: the top two are the parties at +0.5 and +1.0, both
# outside the left-hand voter's tolerance, which is what makes G_a fire.
BELIEFS_FAR = np.array([0.05, 0.10, 0.15, 0.30, 0.40])

# Same total, but the voter's own neighbour at -0.5 is now a front-runner, so a
# contender is projected to qualify and the voter has no reason to deviate.
BELIEFS_NEAR = np.array([0.05, 0.40, 0.10, 0.15, 0.30])

VOTER = -0.55          # distances 0.45, 0.05, 0.55, 1.05, 1.55 -- all distinct
TAU = 0.6              # Ca = {-1.0, -0.5, 0.0}
MU = 0.3


def _decide(positions=POSITIONS, beliefs=BELIEFS_FAR, voter=VOTER,
            tau=TAU, mu=MU, ids=None):
    """Build one elector, run the rule, and return (elector, parties, choice)."""
    ids = ids if ids is not None else range(len(positions))
    parties = [Party(i, p) for i, p in zip(ids, positions)]
    e = Elector(0, voter, len(parties), tau=tau)
    e.posteriorBeliefs = np.asarray(beliefs, dtype=float)
    e.calcSincereUtilities(parties)
    e.calcStrategicUtilities(parties, mu=mu, K_runoff=2, zone_length=ELL)
    return e, parties, e.chooseCandidate(parties, iteration=1)


def _runoff_share(j, k, positions, beliefs):
    """
    R_a(j | k), re-derived from the definition rather than called.

    Eliminated candidates go to whichever finalist is ideologically closer;
    exact ties split. Written out here so the boundary test below checks the
    model against the equation, not against itself.
    """
    rj, rk = beliefs[j], beliefs[k]
    for r in range(len(positions)):
        if r in (j, k):
            continue
        dj = abs(positions[r] - positions[j])
        dk = abs(positions[r] - positions[k])
        if dj < dk:
            rj += beliefs[r]
        elif dk < dj:
            rk += beliefs[r]
        else:
            rj += 0.5 * beliefs[r]
            rk += 0.5 * beliefs[r]
    return rj


# --------------------------------------------------------------------------- #
#  G_a: when the rule fires                                                    #
# --------------------------------------------------------------------------- #

def test_viable_sincere_choice_does_not_trigger():
    """Ca meets the projected top two, so the voter votes sincerely."""
    e, parties, choice = _decide(beliefs=BELIEFS_NEAR)

    top2 = set(np.argsort(-BELIEFS_NEAR)[:2])
    assert top2 & set(e.contenders), "fixture is wrong: Ca must meet T_R here"
    assert e.triggered is False
    assert choice.position == pytest.approx(-0.5)      # the attachment itself


def test_non_viable_sincere_choice_with_a_viable_contender_triggers():
    """No contender is projected to qualify, so G_a = 1."""
    e, parties, choice = _decide(beliefs=BELIEFS_FAR)

    top2 = set(np.argsort(-BELIEFS_FAR)[:2])
    assert not (top2 & set(e.contenders)), "fixture is wrong: Ca must miss T_R"
    assert e.triggered is True


def test_trigger_depends_on_the_projection_not_on_the_voter():
    """
    The same voter, the same Ca, two belief vectors: the trigger follows the
    projection alone. This is the property that makes trigger_rate a measure of
    the informational environment rather than of the electorate.
    """
    far, _, _ = _decide(beliefs=BELIEFS_FAR)
    near, _, _ = _decide(beliefs=BELIEFS_NEAR)
    assert far.contenders == near.contenders
    assert far.triggered != near.triggered


def test_no_opponents_means_no_strategic_incentive():
    """With tau wide enough to make every party a contender, G_a is vacuous."""
    e, parties, choice = _decide(tau=2.0)
    assert e.opponents == []
    assert e.triggered is False
    assert choice.position == pytest.approx(-0.5)


# --------------------------------------------------------------------------- #
#  The expressive cost at its boundary                                         #
# --------------------------------------------------------------------------- #

def test_expressive_cost_flips_the_choice_at_the_computed_boundary():
    """
    Solve for mu* by hand, then check the model turns over there.

        phi(j)  = LV_j * NV_j - mu * lambda_j        (j != j*)
        phi(j*) = LV_j* * NV_j*
        mu*     = (S_alt - S_j*) / lambda_alt

    For this fixture mu* = 1/15. Below it the voter deserts to the party at 0.0;
    above it the expressive cost outweighs the strategic gain and the voter
    stays with the attachment at -0.5.
    """
    u = np.array([-(VOTER - p) ** 2 for p in POSITIONS])
    Ca = [j for j, p in enumerate(POSITIONS) if abs(VOTER - p) <= TAU]
    Oa = [j for j in range(K) if j not in Ca]
    j_star = int(np.argmax(u))
    k_star = max(Oa, key=lambda k: BELIEFS_FAR[k])

    mass = sum(BELIEFS_FAR[j] for j in Ca)
    S = {j: (BELIEFS_FAR[j] / mass) * _runoff_share(j, k_star, POSITIONS,
                                                    BELIEFS_FAR) for j in Ca}
    lam = {j: (u[j_star] - u[j]) / ELL ** 2 for j in Ca}

    alt = max((j for j in Ca if j != j_star), key=lambda j: S[j])
    mu_star = (S[alt] - S[j_star]) / lam[alt]

    assert mu_star == pytest.approx(1.0 / 15.0, abs=1e-12)

    below = _decide(mu=mu_star - 1e-6)[2]
    above = _decide(mu=mu_star + 1e-6)[2]
    assert below.position == pytest.approx(POSITIONS[alt])
    assert above.position == pytest.approx(POSITIONS[j_star])


def test_zero_expressive_cost_takes_the_best_strategic_option():
    assert _decide(mu=0.0)[2].position == pytest.approx(0.0)


def test_large_expressive_cost_pins_the_voter_to_the_attachment():
    assert _decide(mu=50.0)[2].position == pytest.approx(-0.5)


def test_expressive_cost_is_never_charged_on_the_attachment_itself():
    """lambda(j*) = 0 by construction, so mu cannot move phi(j*)."""
    a, _, _ = _decide(mu=0.0)
    b, _, _ = _decide(mu=7.5)
    j_star = int(np.argmax(a.sincereUtilities))
    assert a.strategicUtilities[j_star] == pytest.approx(
        b.strategicUtilities[j_star], abs=1e-12)


# --------------------------------------------------------------------------- #
#  The contender set                                                           #
# --------------------------------------------------------------------------- #

def test_contender_set_is_the_tolerance_ball():
    e, parties, _ = _decide()
    got = sorted(parties[j].position for j in e.contenders)
    assert got == [-1.0, -0.5, 0.0]


def test_tolerance_boundary_is_inclusive():
    """
    |x_a - x_j| <= tau, so a party at exactly tau is a contender.

    The voter sits at 0.0 and tau is exactly the distance to the parties at
    +/-0.5, which are therefore in Ca while +/-1.0 are not.
    """
    e, parties, _ = _decide(voter=0.0, tau=0.5)
    got = sorted(parties[j].position for j in e.contenders)
    assert got == [-0.5, 0.0, 0.5]

    tighter, parties2, _ = _decide(voter=0.0, tau=0.5 - 1e-9)
    assert sorted(parties2[j].position for j in tighter.contenders) == [0.0]


@pytest.mark.parametrize("K_test", [6, 8, 9, 12, 15])
def test_contender_set_at_several_K_uses_the_converted_tolerance(K_test):
    """
    tau_hat = 1.0 is one zone length, so the ball has radius 2/K.

    Parties are evenly spaced with gap 2/(K-1); the voter sits on one of them,
    so exactly the party itself and its immediate neighbours fall inside.
    """
    pos = list(np.linspace(-1.0, 1.0, K_test))
    tau = tau_absolute(1.0, K_test)
    assert tau == pytest.approx(2.0 / K_test)

    mid = K_test // 2
    beliefs = np.full(K_test, 1.0 / K_test)
    e, parties, _ = _decide(positions=pos, beliefs=beliefs,
                            voter=pos[mid], tau=tau)

    expected = [j for j, p in enumerate(pos) if abs(pos[mid] - p) <= tau]
    assert sorted(e.contenders) == sorted(expected)


def test_partition_is_a_partition_of_valid_indices():
    for tau in (0.01, 0.3, 0.6, 1.2, 2.0):
        e, _, _ = _decide(tau=tau)
        ca, oa = set(e.contenders), set(e.opponents)
        assert ca | oa == set(range(K))
        assert ca & oa == set()
        assert all(0 <= j < K for j in ca | oa)


def test_contender_set_is_never_empty_and_always_holds_the_attachment():
    """
    The singleton case, and the guarantee that makes the empty case impossible.

    _updatePartition appends j* when the tolerance ball excludes it, so however
    small tau gets, Ca is a singleton rather than empty -- and chooseCandidate,
    which maxes over Ca, therefore always has something to return.
    """
    for tau in (1e-9, 0.0, -1.0):
        e, parties, choice = _decide(tau=tau)
        j_star = int(np.argmax(e.sincereUtilities))
        assert e.contenders, f"Ca empty at tau={tau}"
        assert j_star in e.contenders
        assert len(e.contenders) == 1
        assert choice.position == pytest.approx(parties[j_star].position)


def test_contender_set_does_not_depend_on_candidate_labels():
    """Party IDs are labels; only positions and beliefs may matter."""
    plain, parties_a, choice_a = _decide()
    odd, parties_b, choice_b = _decide(ids=[97, 3, 41, 12, 66])

    assert sorted(parties_a[j].position for j in plain.contenders) == \
        sorted(parties_b[j].position for j in odd.contenders)
    assert plain.triggered == odd.triggered
    assert choice_a.position == pytest.approx(choice_b.position)


# --------------------------------------------------------------------------- #
#  Metamorphic properties                                                      #
# --------------------------------------------------------------------------- #
#
# Both are derived, not assumed.  Every quantity in the rule is a function of
# squared distances -(x_a - x_j)^2, absolute distances |x_a - x_j| and the
# belief vector.  None of them reads an index except to break ties, and the
# fixture has no ties.  So:
#
#   * permuting the party list (with beliefs permuted alongside) must leave the
#     chosen party, the trigger and Ca unchanged as sets of positions;
#   * negating every position must map the whole decision to its mirror image.
#
# Both were checked exhaustively before being written down: all 120
# permutations, and reflection at five voter positions.

def test_decision_is_invariant_to_party_relabelling():
    base_e, base_parties, base_choice = _decide()
    base_contenders = sorted(base_parties[j].position for j in base_e.contenders)

    for perm in itertools.permutations(range(K)):
        pos = [POSITIONS[i] for i in perm]
        bel = BELIEFS_FAR[list(perm)]
        e, parties, choice = _decide(positions=pos, beliefs=bel)

        assert choice.position == pytest.approx(base_choice.position), \
            f"relabelling {perm} changed the chosen party"
        assert e.triggered == base_e.triggered
        assert sorted(parties[j].position
                      for j in e.contenders) == base_contenders


@pytest.mark.parametrize("voter", [-0.93, -0.55, -0.2, 0.31, 0.77])
def test_decision_is_symmetric_under_left_right_reflection(voter):
    """
    x -> -x everywhere, with the party list reversed so it stays ordered
    left to right and the beliefs reversed with it.
    """
    base_e, _, base_choice = _decide(voter=voter)

    pos_r = [-p for p in POSITIONS][::-1]
    bel_r = BELIEFS_FAR[::-1]
    e, _, choice = _decide(positions=pos_r, beliefs=bel_r, voter=-voter)

    assert choice.position == pytest.approx(-base_choice.position, abs=1e-12)
    assert e.triggered == base_e.triggered

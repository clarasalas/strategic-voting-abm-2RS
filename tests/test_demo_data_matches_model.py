"""
test_demo_data_matches_model.py
-------------------------------
The demo's JSON must be what the model actually produces.

docs/demo/ claims that every trajectory it animates was computed by
core_model.model.run_simulation rather than reimplemented in JavaScript.  That
claim is the whole reason the demo is allowed to exist alongside the paper: if
it can drift from the model, it is a second model with a nicer interface.

Nothing enforced it. The JSON is generated once by demo/precompute.py and
committed, so it can go stale in two ways that no other test would catch: the
model changes and the data is not regenerated, or precompute.py's baseline is
edited and the data is not regenerated. Either leaves a page that looks fine and
shows numbers the model no longer produces.

These re-run the model at the parameters the JSON says it used and compare
against the stored values, exactly, after the same per-mille rounding the file
uses. Parameters come from the file's own metadata rather than being repeated
here, so this stays correct if the grid is ever recomputed on a different one.

Cost: four runs at n = 2000, a few seconds. Deliberately a spot check and not
the whole grid, which is 5 280 runs.

If this fails, regenerate the data:  python demo/precompute.py --force

Run with:  pytest tests/test_demo_data_matches_model.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "demo"))

from core_model.model import run_simulation                      # noqa: E402
from core_model.metrics import tau_absolute, enp                 # noqa: E402
import precompute                                                # noqa: E402

GRID = REPO / "docs" / "demo" / "data" / "grid.json"

# Corners and middle: a quiet cell, a heavily-switching cell, and one between.
# Indices, not parameter values, so they stay valid under the stored grid.
SPOT_CELLS = [(0, 0, 0), (6, 5, 0), (11, 10, 4)]


@pytest.fixture(scope="module")
def data():
    if not GRID.exists():                       # pragma: no cover
        pytest.skip(f"{GRID.relative_to(REPO)} not generated")
    return json.loads(GRID.read_text())


def _permille(a):
    """Exactly the rounding demo/precompute.py applies before writing."""
    return np.round(np.asarray(a, dtype=float) * 1000).astype(int).tolist()


def _params(meta, ic, it, im):
    g = meta["grid"]
    return g["c"][ic], g["tau_hat"][it], g["mu"][im]


def _run(meta, c, tau_hat, mu, seed):
    """The baseline the file records, not a copy of it kept in this test."""
    b = meta["baseline"]
    return run_simulation(
        K=b["K"], n_modes=b["n_modes"], width_factor=c,
        floor_weight=b["floor_weight"], theta=b["theta"], rho=b["rho_s"],
        rho_pi=b["rho_pi"], n_electors=b["n_electors"],
        tau=tau_absolute(tau_hat, b["K"]), mu=mu, alpha_prior=b["alpha"],
        K_runoff=b["K_runoff"], max_iterations=b["max_iterations"],
        seed=seed, verbose=False, collect_diagnostics=True,
    )


@pytest.mark.parametrize("cell", SPOT_CELLS, ids=lambda c: "cell_%d_%d_%d" % c)
def test_animated_trajectory_is_real_model_output(data, cell):
    """
    The animated run must reproduce from the canonical seed.

    This is the series a visitor actually watches: vote shares and the poll
    signal at every iteration.
    """
    meta = data["meta"]
    ic, it, im = cell
    stored = data["cells"]["%d_%d_%d" % cell]
    c, tau_hat, mu = _params(meta, ic, it, im)

    r = _run(meta, c, tau_hat, mu, meta["canonical_seed"])

    counts = np.array(r["history"], dtype=float)
    shares = counts / counts.sum(axis=1, keepdims=True)
    assert [_permille(row) for row in shares] == stored["sh"], (
        f"vote-share trajectory at c={c}, tau_hat={tau_hat}, mu={mu} does not "
        f"match the model; regenerate with python demo/precompute.py --force")

    signal = [d["signal"] for d in r["diagnostics"]["iterations"]]
    assert [_permille(row) for row in signal] == stored["sg"], (
        f"poll-signal trajectory at c={c}, tau_hat={tau_hat}, mu={mu} does not "
        f"match the model; regenerate with python demo/precompute.py --force")


def test_bars_and_readouts_are_the_seed_mean(data):
    """
    The bars and readouts must be the mean over every seed, not one run.

    Checked on a single cell, because it costs one run per seed.  The page says
    "one run animated, eight averaged"; this is the second half of that claim.
    """
    meta = data["meta"]
    cell = SPOT_CELLS[1]
    stored = data["cells"]["%d_%d_%d" % cell]
    c, tau_hat, mu = _params(meta, *cell)

    sincere, final, switched, gain = [], [], [], []
    for seed in meta["seeds"]:
        r = _run(meta, c, tau_hat, mu, seed)
        sincere.append(np.asarray(r["sincere_shares"], dtype=float))
        final.append(np.asarray(r["final_shares"], dtype=float))
        switched.append(r["switching"]["pct_strategic"])
        gain.append(enp(r["sincere_shares"]) - enp(r["final_shares"]))

    assert _permille(np.mean(sincere, axis=0)) == stored["sinc"]
    assert _permille(np.mean(final, axis=0)) == stored["fin"]
    assert int(round(float(np.mean(switched)) * 1000)) == stored["sw"]
    assert int(round(float(np.mean(gain)) * 1000)) == stored["gain"]


def test_metadata_matches_the_generating_script(data):
    """
    The file's recorded baseline must be the one precompute.py would use now.

    Catches an edit to the script that was never followed by a regeneration,
    which would leave the data correct for a baseline nobody runs any more.
    """
    b = data["meta"]["baseline"]
    assert b["K"] == precompute.K
    assert b["n_electors"] == precompute.N_ELECTORS
    assert b["max_iterations"] == precompute.MAX_ITERATIONS
    assert b["theta"] == precompute.THETA
    assert b["rho_s"] == precompute.RHO_S
    assert b["rho_pi"] == precompute.RHO_PI
    assert b["alpha"] == precompute.ALPHA
    assert b["K_runoff"] == precompute.K_RUNOFF
    assert b["n_modes"] == precompute.N_MODES
    assert b["floor_weight"] == precompute.FLOOR_WEIGHT
    assert data["meta"]["seeds"] == precompute.SEEDS
    assert data["meta"]["canonical_seed"] == precompute.CANONICAL_SEED
    assert data["meta"]["grid"]["c"] == precompute.C_VALUES
    assert data["meta"]["grid"]["tau_hat"] == precompute.TAU_VALUES
    assert data["meta"]["grid"]["mu"] == precompute.MU_VALUES


def test_every_grid_position_has_a_cell(data):
    """A slider position with no cell behind it is a blank page, not a bug the
    visitor can diagnose."""
    g = data["meta"]["grid"]
    missing = [
        (ic, it, im)
        for ic in range(len(g["c"]))
        for it in range(len(g["tau_hat"]))
        for im in range(len(g["mu"]))
        if "%d_%d_%d" % (ic, it, im) not in data["cells"]
    ]
    assert not missing, f"{len(missing)} grid positions have no cell"
    assert len(data["cells"]) == (
        len(g["c"]) * len(g["tau_hat"]) * len(g["mu"]))


# --------------------------------------------------------------------------- #
#  The page's claims about the data                                            #
# --------------------------------------------------------------------------- #
# The two above check that the stored numbers are the model's.  These check that
# the sentences wrapped around them are still true.  Both guard the same failure:
# the mechanism is revised, the grid is regenerated, every test still passes, and
# the page goes on asserting something about a distribution that has moved.

PAGE = REPO / "docs" / "demo" / "index.html"

# The note beside the sliders reads: "two thirds of the combinations move under
# 2% of voters".  Bounds on what "two thirds" can honestly describe.
QUIET_THRESHOLD = 0.02
QUIET_FRACTION_RANGE = (0.60, 0.72)

# The opening slider position, set by the rule stated in the page: c and the
# tolerance at their grid midpoints, expressive cost at its minimum.
OPENING_MIN_SWITCHING = 0.05


def _switching(data):
    return [c["sw"] / 1000 for c in data["cells"].values()]


def test_quiet_cell_claim_still_holds(data):
    """
    The page tells the visitor most settings coordinate little.  That is a claim
    about this grid, and a revised mechanism could move it without breaking
    anything visible.
    """
    sw = _switching(data)
    frac = sum(1 for v in sw if v < QUIET_THRESHOLD) / len(sw)
    lo, hi = QUIET_FRACTION_RANGE
    assert lo <= frac <= hi, (
        f"{PAGE.relative_to(REPO)} says two thirds of settings move under "
        f"{QUIET_THRESHOLD:.0%} of voters; it is now {frac:.1%}. "
        f"Update the sentence beside the sliders.")


def test_page_still_makes_the_claim_this_test_checks(data):
    """
    Guards the other direction: if the sentence is reworded, the numbers above
    stop describing anything and this test would pass while checking nothing.
    """
    text = PAGE.read_text()
    assert "two thirds" in text, (
        "the quiet-cell sentence was reworded; revisit QUIET_FRACTION_RANGE")
    assert "2%" in text, (
        "the quiet-cell threshold was reworded; revisit QUIET_THRESHOLD")


def test_opening_position_shows_the_mechanism(data):
    """
    Two thirds of the grid is quiet, so the cell the page opens on is load
    bearing: land on a dull one and a visitor who touches nothing concludes the
    model does nothing.  The rule is fixed, but what it selects depends on the
    mechanism.
    """
    g = data["meta"]["grid"]
    ic, it, im = len(g["c"]) // 2, len(g["tau_hat"]) // 2, 0
    cell = data["cells"]["%d_%d_%d" % (ic, it, im)]
    sw = cell["sw"] / 1000
    assert sw >= OPENING_MIN_SWITCHING, (
        f"the demo opens at c={g['c'][ic]}, tau_hat={g['tau_hat'][it]}, "
        f"mu={g['mu'][im]}, where only {sw:.1%} of voters switch. The page "
        f"would autoplay a run in which nothing happens; choose a different "
        f"opening rule in docs/demo/index.html and update it here.")

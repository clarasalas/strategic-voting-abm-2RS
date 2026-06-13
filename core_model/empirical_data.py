"""
empirical_data.py
-----------------
Loaders and constructors for the empirical 2002 / 2022 replay protocol.

Everything in this module turns the raw European-decimal CSVs in ``data/``
into the arrays the ABM consumes through the empirical-override kwargs of
``model.run_simulation``:

    - party positions  : rescaled from the raw [0, 10] left-right scale to the
                         model's [-1, 1] ideological space, ordered left->right.
    - voter positions  : N samples drawn from the empirical ideology histogram
                         (already on [-1, 1]).
    - signal timeline  : a chronological list of normalised poll-share vectors
                         (weekly means by default; individual polls optionally).

Canonical ordering
------------------
For each year a single canonical, **left-to-right** party order is derived from
the (rescaled) party positions and reused everywhere: positions, voters'
utilities, poll columns, results, plots and colours.  Use
``load_year(...)`` to get a consistent bundle.

Scale convention
----------------
Raw positions live on [0, 10]; voters on [-1, 1].  Positions are mapped with
``x -> x / 5 - 1`` so both share the model's [-1, 1] space.
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# =========================================================================== #
#  LOW-LEVEL PARSING                                                           #
# =========================================================================== #

def _to_float(value) -> float:
    """Parse a European-decimal string ('0,080') to float; '' / NaN -> nan."""
    if value is None:
        return np.nan
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return np.nan
    return float(s.replace(",", "."))


def rescale_position(raw: float) -> float:
    """Map a raw [0, 10] left-right position onto the model's [-1, 1] space."""
    return float(raw) / 5.0 - 1.0


# =========================================================================== #
#  PARTY POSITIONS                                                             #
# =========================================================================== #

def load_party_positions(year: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """
    Load party positions for a year, rescaled to [-1, 1] and ordered
    left-to-right (ascending position).

    Returns
    -------
    DataFrame with columns:
        party     : str
        block     : str
        raw       : float  -- original [0, 10] position
        position  : float  -- rescaled [-1, 1] position
    indexed 0..K-1 in left-to-right order.
    """
    path = data_dir / f"party_positions_{year}.csv"
    df = pd.read_csv(path, dtype=str)
    df["raw"] = df["left_right_position"].map(_to_float)
    df["position"] = df["raw"].map(rescale_position)
    df = df.rename(columns={"block": "block"})[
        ["party", "block", "raw", "position"]
    ]
    df = df.sort_values("position", kind="stable").reset_index(drop=True)
    return df


# =========================================================================== #
#  RESULTS                                                                     #
# =========================================================================== #

def load_results(year: int, party_order: list,
                 data_dir: Path = DATA_DIR) -> np.ndarray:
    """
    Load first-round actual result shares, aligned to ``party_order`` and
    normalised to sum to 1.

    Returns
    -------
    np.ndarray (K,) of actual R1 shares.
    """
    path = data_dir / f"results_{year}.csv"
    df = pd.read_csv(path, dtype=str)
    shares = {row["party"]: _to_float(row["electoral_share_R1"])
              for _, row in df.iterrows()}
    vec = np.array([shares.get(p, np.nan) for p in party_order], dtype=float)
    if np.isnan(vec).any():
        missing = [p for p, v in zip(party_order, vec) if np.isnan(v)]
        raise ValueError(f"Results {year}: missing R1 share for {missing}.")
    return vec / vec.sum()


# =========================================================================== #
#  VOTER IDEOLOGY                                                              #
# =========================================================================== #

def _map_voter_scale(raw: np.ndarray, year: int) -> np.ndarray:
    """
    Map a raw voter ideology scale onto the model's [-1, 1] space.

    The two voter files use different raw scales:
        2002 : scale 1-10  ->  x = 2 * (scale - 1) / 9 - 1
        2022 : scale 0-10  ->  x = scale / 5 - 1
    """
    raw = np.asarray(raw, dtype=float)
    if year == 2002:
        return 2.0 * (raw - 1.0) / 9.0 - 1.0
    if year == 2022:
        return raw / 5.0 - 1.0
    raise ValueError(f"No voter-scale mapping defined for year {year}.")


def load_voter_histogram(year: int,
                         data_dir: Path = DATA_DIR) -> tuple:
    """
    Load the empirical voter ideology histogram and map it to [-1, 1].

    The files are raw-scale, with a year-specific ideology range:
        voters_ideology_2002.csv : ideological_scale (1-10), share
        voters_ideology_2022.csv : ideological_scale (0-10), share

    Columns are read **positionally** to tolerate header naming:
        column 0 -> raw ideology bin centre (mapped to [-1, 1])
        column 1 -> share / frequency
    Shares are normalised to sum to 1.

    Returns
    -------
    (positions, probs) : two np.ndarrays; positions on [-1, 1] and sorted,
                         probs sums to 1.
    """
    path = data_dir / f"voters_ideology_{year}.csv"
    df = pd.read_csv(path, dtype=str)
    raw = df.iloc[:, 0].map(_to_float).to_numpy(dtype=float)
    share = df.iloc[:, 1].map(_to_float).to_numpy(dtype=float)
    pos = _map_voter_scale(raw, year)
    order = np.argsort(pos)
    pos, share = pos[order], share[order]
    share = share / share.sum()
    return pos, share


def sample_voters(year: int, n: int, rng,
                  data_dir: Path = DATA_DIR) -> np.ndarray:
    """
    Draw ``n`` voter positions from the empirical ideology distribution by
    sampling ideology bin centres directly, using the histogram shares as
    sampling probabilities.

    Direct bin-centre sampling is unbiased: the sample mean converges to the
    histogram mean sum(pos * probs).  This is simpler and more transparent than
    inverse-CDF interpolation (which mapped mass below the first bin onto the
    leftmost point and biased the mean leftward).

    Parameters
    ----------
    year : int
    n    : int                         -- number of voters (e.g. 2000)
    rng  : np.random.Generator

    Returns
    -------
    np.ndarray (n,) of bin-centre positions in [-1, 1].
    """
    pos, probs = load_voter_histogram(year, data_dir)
    return rng.choice(pos, size=n, p=probs)


# =========================================================================== #
#  POLL SIGNALS                                                                #
# =========================================================================== #

def _load_polls(year: int, party_order: list,
                data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """
    Load the raw poll table, parse dates and candidate shares, and reindex
    the candidate columns to the canonical ``party_order``.

    Returns
    -------
    DataFrame with a 'date' (datetime) column plus one float column per party
    in ``party_order``, sorted chronologically.
    """
    path = data_dir / f"polls_{year}.csv"
    df = pd.read_csv(path, dtype=str)
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
    for p in party_order:
        if p not in df.columns:
            raise ValueError(f"Polls {year}: missing candidate column '{p}'.")
        df[p] = df[p].map(_to_float)
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    return df[["date"] + list(party_order)]


def _normalise_rows(mat: np.ndarray) -> np.ndarray:
    """Normalise each row to sum to 1 (rows summing to 0 -> uniform)."""
    mat = np.asarray(mat, dtype=float)
    totals = mat.sum(axis=1, keepdims=True)
    safe = np.where(totals > 0, totals, 1.0)
    out = mat / safe
    out[totals[:, 0] <= 0] = 1.0 / mat.shape[1]
    return out


def weekly_signal_timeline(year: int, party_order: list,
                           data_dir: Path = DATA_DIR) -> list:
    """
    Build the chronological weekly-mean poll-signal timeline.

    Polls are grouped by ISO (year, week); within each week the candidate
    shares are averaged across pollsters, then each weekly vector is
    normalised to sum to 1.

    Returns
    -------
    list of np.ndarray (K,), one per week, chronologically ordered.
    Element 0 (s^0) feeds the voter prior; later elements drive the
    strategic iterations.
    """
    df = _load_polls(year, party_order, data_dir)
    iso = df["date"].dt.isocalendar()
    df = df.assign(_yw=list(zip(iso["year"], iso["week"])))
    weekly = (df.groupby("_yw", sort=True)[list(party_order)]
              .mean())
    mat = _normalise_rows(weekly.to_numpy(dtype=float))
    return [row.copy() for row in mat]


def individual_signal_timeline(year: int, party_order: list,
                               data_dir: Path = DATA_DIR) -> list:
    """
    Robustness variant: every individual poll is its own signal, in
    chronological order, each normalised to sum to 1.

    Returns
    -------
    list of np.ndarray (K,).
    """
    df = _load_polls(year, party_order, data_dir)
    mat = _normalise_rows(df[list(party_order)].to_numpy(dtype=float))
    return [row.copy() for row in mat]


# =========================================================================== #
#  POSITION PERTURBATION (robustness)                                          #
# =========================================================================== #

def perturb_positions(positions: np.ndarray, size: float, rng,
                      space: tuple = (-1.0, 1.0)) -> np.ndarray:
    """
    Add an equal-magnitude uniform perturbation U[-size, size] to every party
    position, clipped to ``space``.

    ``size`` is on the model's [-1, 1] scale and should stay small (e.g. 0.05)
    so the broad left/centre/right bloc structure is preserved.

    Returns
    -------
    np.ndarray (K,) perturbed positions.
    """
    positions = np.asarray(positions, dtype=float)
    noise = rng.uniform(-size, size, size=positions.shape)
    return np.clip(positions + noise, space[0], space[1])


# =========================================================================== #
#  CONVENIENCE BUNDLE                                                          #
# =========================================================================== #

def load_year(year: int, signal_mode: str = "weekly",
              data_dir: Path = DATA_DIR) -> dict:
    """
    Load a complete, canonically-ordered empirical bundle for one year.

    Parameters
    ----------
    year        : 2002 or 2022
    signal_mode : 'weekly' (default) or 'individual'

    Returns
    -------
    dict with keys:
        year         : int
        K            : int
        parties      : list[str]            -- canonical left->right order
        blocks       : list[str]
        positions    : np.ndarray (K,)      -- rescaled [-1, 1]
        positions_raw: np.ndarray (K,)      -- original [0, 10]
        results      : np.ndarray (K,)      -- actual R1 shares (sum 1)
        signals      : list[np.ndarray]     -- signal timeline (sum-1 vectors)
    """
    pos_df = load_party_positions(year, data_dir)
    parties = pos_df["party"].tolist()
    positions = pos_df["position"].to_numpy(dtype=float)

    if signal_mode == "weekly":
        signals = weekly_signal_timeline(year, parties, data_dir)
    elif signal_mode == "individual":
        signals = individual_signal_timeline(year, parties, data_dir)
    else:
        raise ValueError("signal_mode must be 'weekly' or 'individual'.")

    return {
        "year": year,
        "K": len(parties),
        "parties": parties,
        "blocks": pos_df["block"].tolist(),
        "positions": positions,
        "positions_raw": pos_df["raw"].to_numpy(dtype=float),
        "results": load_results(year, parties, data_dir),
        "signals": signals,
    }

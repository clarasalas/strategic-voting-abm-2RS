"""
behavioral_targets.py
----------------------
Real poll→result coordination targets, one per election year.  No simulation.

For each year:
    s⁰            = bundle["signals"][0]          (exogenous baseline poll)
    actual_result = bundle["results"]             (actual R1 shares)
    cenp_s0       = CENP(s⁰)
    cenp_real     = CENP(actual_result)
    delta_cenp_real = CENP(actual_result) − CENP(s⁰)

ΔCENP_real is the SAME baseline (s⁰) used by the behavioral sweep, so the sweep
violins and these targets are directly comparable.

CENP reused from analysis/main_results.py (ENP = 1/Σδ², CENP = (K−ENP)/(K−1)).

Output
------
    data/behavioral_targets.csv
        year, K, cenp_s0, cenp_real, delta_cenp_real

Usage
-----
    python analysis/behavioral_targets.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(ROOT))

from empirical_data import load_year
from main_results import cenp                  # reuse existing CENP

YEARS = (2002, 2022)
OUT = REPO / "data" / "behavioral_targets.csv"


def main() -> None:
    rows = []
    for year in YEARS:
        bundle = load_year(year, signal_mode="weekly")
        K = len(bundle["positions"])
        s0 = np.asarray(bundle["signals"][0], dtype=float)     # baseline poll
        actual = np.asarray(bundle["results"], dtype=float)    # actual R1 result
        cenp_s0 = cenp(s0, K)
        cenp_real = cenp(actual, K)
        delta_real = cenp_real - cenp_s0
        rows.append({
            "year": year,
            "K": K,
            "cenp_s0": cenp_s0,
            "cenp_real": cenp_real,
            "delta_cenp_real": delta_real,
        })
        print(f"[targets] {year}: K={K}  CENP(s⁰)={cenp_s0:+.4f}  "
              f"CENP(real)={cenp_real:+.4f}  ΔCENP_real={delta_real:+.4f}")

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"[targets] wrote -> {OUT}")


if __name__ == "__main__":
    main()
